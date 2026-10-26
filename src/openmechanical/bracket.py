"""Parametric filleted mounting-bracket CAD and mesh preparation."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import cadquery as cq
import gmsh
import matplotlib
import numpy as np
from matplotlib.patches import Patch
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from .contracts import MountingBracketGeometry, ProblemSpec
from .units import canonical_problem_si, to_si, validate_problem_units


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _close(left: float, right: float, tolerance: float) -> bool:
    return abs(left - right) <= tolerance


def _write_preview(
    path: Path,
    coordinates: dict[int, np.ndarray],
    surfaces: list[int],
    fixed_surfaces: set[int],
    loaded_surfaces: set[int],
    dimensions_mm: tuple[float, float, float],
) -> None:
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    polygons: list[list[np.ndarray]] = []
    colors: list[str] = []
    for surface in surfaces:
        types, _, node_blocks = gmsh.model.mesh.getElements(2, surface)
        for element_type, block in zip(types, node_blocks, strict=True):
            if int(element_type) != 9:
                continue
            for row in np.asarray(block, dtype=np.int64).reshape((-1, 6)):
                polygons.append([coordinates[int(node)] for node in row[:3]])
                if surface in fixed_surfaces:
                    colors.append("#2878b5")
                elif surface in loaded_surfaces:
                    colors.append("#d9534f")
                else:
                    colors.append("#c8cdd3")

    figure = plt.figure(figsize=(8, 6))
    axis = figure.add_subplot(111, projection="3d")
    collection = Poly3DCollection(
        polygons, facecolors=colors, edgecolors="#59636e", linewidths=0.08
    )
    axis.add_collection3d(collection)
    base_length, width, height = dimensions_mm
    axis.set_xlim(0, base_length)
    axis.set_ylim(0, width)
    axis.set_zlim(0, height)
    axis.set_box_aspect((base_length, width, height))
    axis.set_xlabel("X [mm]")
    axis.set_ylabel("Y [mm]")
    axis.set_zlabel("Z [mm]")
    axis.set_title("Mounting bracket boundary preview\nBlue: fixed support | Red: loaded face")
    axis.view_init(elev=23, azim=125)
    axis.legend(
        handles=[
            Patch(facecolor="#2878b5", label="fixed support"),
            Patch(facecolor="#d9534f", label="loaded face"),
            Patch(facecolor="#c8cdd3", label="other surfaces"),
        ],
        loc="upper left",
    )
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    plt.close(figure)


def prepare_bracket_mesh(
    problem: ProblemSpec, output_dir: Path, *, partition_stress_roi: bool = False
) -> dict[str, Any]:
    """Build STEP, resolve stable semantic faces, mesh, and write evidence.

    This prepares geometry and mesh only. It does not run FEA or make a design
    assessment.
    """
    validate_problem_units(problem)
    geometry = problem.geometry
    if not isinstance(geometry, MountingBracketGeometry):
        raise ValueError("mounting-bracket preparation requires mounting_bracket geometry")
    if len(problem.constraints) != 1 or problem.constraints[0].region != "mount_face":
        raise ValueError("the bracket example requires one fixed 'mount_face' constraint")
    if len(problem.loads) != 1 or problem.loads[0].region != "loaded_pad":
        raise ValueError("the bracket example requires one load on the 'loaded_pad' region")
    if problem.loads[0].kind != "traction" or problem.loads[0].direction is None:
        raise ValueError("the bracket example currently requires one vector traction")
    load_direction = np.asarray(problem.loads[0].direction, dtype=float)
    load_direction /= np.linalg.norm(load_direction)
    if not np.allclose(load_direction, [0.0, 0.0, -1.0], atol=1e-12, rtol=0.0):
        raise ValueError("the bracket preview workflow currently supports downward -Z traction")

    output_dir = output_dir.resolve()
    if output_dir.exists() and (not output_dir.is_dir() or any(output_dir.iterdir())):
        raise FileExistsError(f"refusing to overwrite nonempty output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    def mm(field: str) -> float:
        return to_si(getattr(geometry, field), "meter") * 1000.0

    base_length, width, height, thickness, root_radius = (
        mm("base_length"),
        mm("width"),
        mm("height"),
        mm("thickness"),
        mm("root_radius"),
    )
    mesh_size = to_si(problem.mesh.size, "meter") * 1000.0
    analytic_volume = width * (
        base_length * thickness
        + height * thickness
        - thickness**2
        + (1 - math.pi / 4) * root_radius**2
    )
    if not math.isfinite(analytic_volume) or analytic_volume <= 0 or not math.isfinite(mesh_size):
        raise ValueError("nonfinite geometry or mesh scale")
    log_estimate = math.log(12) + math.log(analytic_volume) - 3 * math.log(mesh_size)
    if log_estimate > math.log(500000):
        raise ValueError("requested mesh exceeds the conservative 500k-element preparation budget")
    element_budget_estimate = math.exp(log_estimate)
    step_path = output_dir / "bracket.step"
    msh_path = output_dir / "bracket.msh"
    preview_path = output_dir / "boundary-preview.png"
    boundary_path = output_dir / "boundary-manifest.json"
    mesh_path = output_dir / "mesh-manifest.json"
    canonical_path = output_dir / "problem.canonical.json"

    root_center = thickness + root_radius
    arc_mid = root_center - root_radius / math.sqrt(2.0)
    section = (
        cq.Workplane("XZ")
        .moveTo(0, 0)
        .lineTo(base_length, 0)
        .lineTo(base_length, thickness)
        .lineTo(root_center, thickness)
        .threePointArc((arc_mid, arc_mid), (thickness, root_center))
        .lineTo(thickness, height)
        .lineTo(0, height)
        .close()
        .extrude(width)
    )
    shape = section.val().translate((0, width, 0))
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise RuntimeError("CadQuery did not create one valid mounting-bracket solid")
    cq.exporters.export(shape, str(step_path), exportType="STEP", unit="MM")
    roundtrip = cq.importers.importStep(str(step_path)).val()
    if not roundtrip.isValid() or len(roundtrip.Solids()) != 1:
        raise RuntimeError("STEP round trip did not preserve one valid bracket solid")
    volume_error = abs(roundtrip.Volume() - shape.Volume()) / shape.Volume()
    if volume_error > 1e-8:
        raise RuntimeError(f"STEP round trip changed volume by {volume_error:.3g}")

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("Mesh.MeshSizeMin", to_si(problem.mesh.size, "meter") * 1000.0)
        gmsh.option.setNumber("Mesh.MeshSizeMax", to_si(problem.mesh.size, "meter") * 1000.0)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
        gmsh.option.setNumber("Mesh.ElementOrder", 2)
        gmsh.option.setNumber("Mesh.SecondOrderLinear", 0)
        gmsh.model.add("mounting_bracket")
        gmsh.model.occ.importShapes(str(step_path), highestDimOnly=True)
        gmsh.model.occ.synchronize()
        volumes = gmsh.model.getEntities(3)
        if len(volumes) != 1:
            raise RuntimeError(f"expected one bracket volume, found {len(volumes)}")
        volume = volumes[0][1]
        if partition_stress_roi:
            if thickness + root_radius >= 0.55 * base_length:
                raise ValueError("regular stress partition overlaps root fillet")
            roi_box = gmsh.model.occ.addBox(
                0.55 * base_length,
                0.2 * width,
                0,
                0.2 * base_length,
                0.6 * width,
                thickness,
            )
            gmsh.model.occ.fragment([(3, volume)], [(3, roi_box)])
            gmsh.model.occ.synchronize()
            volumes = gmsh.model.getEntities(3)
            total_volume = sum(gmsh.model.occ.getMass(3, tag) for _, tag in volumes)
            if not math.isclose(total_volume, shape.Volume(), rel_tol=1e-8):
                raise RuntimeError("ROI partition changed the physical solid volume")
        tolerance = max(base_length, width, height) * 1e-8
        surfaces = [
            tag
            for _, tag in gmsh.model.getBoundary(
                volumes, combined=True, oriented=False, recursive=False
            )
        ]
        fixed_surfaces: list[int] = []
        loaded_surfaces: list[int] = []
        for surface in surfaces:
            box = gmsh.model.getBoundingBox(2, surface)
            area = gmsh.model.occ.getMass(2, surface)
            if (
                _close(box[0], 0.0, tolerance)
                and _close(box[3], 0.0, tolerance)
                and _close(box[1], 0.0, tolerance)
                and _close(box[4], width, tolerance)
                and _close(box[2], 0.0, tolerance)
                and _close(box[5], height, tolerance)
                and math.isclose(area, width * height, rel_tol=1e-7, abs_tol=tolerance)
            ):
                fixed_surfaces.append(surface)
            expected_loaded_area = (base_length - root_center) * width
            if (
                _close(box[2], thickness, tolerance)
                and _close(box[5], thickness, tolerance)
                and box[0] >= root_center - tolerance
                and box[3] <= base_length + tolerance
                and box[1] >= -tolerance
                and box[4] <= width + tolerance
            ):
                loaded_surfaces.append(surface)
        selected_load_area = sum(gmsh.model.occ.getMass(2, tag) for tag in loaded_surfaces)
        if (
            len(fixed_surfaces) != 1
            or not loaded_surfaces
            or not math.isclose(selected_load_area, expected_loaded_area, rel_tol=1e-8)
        ):
            raise RuntimeError(
                "semantic surface resolution was empty or ambiguous: "
                f"mount_face={fixed_surfaces}, loaded_pad={loaded_surfaces}"
            )

        gmsh.model.addPhysicalGroup(3, [tag for _, tag in volumes], 1)
        gmsh.model.setPhysicalName(3, 1, "SOLID")
        gmsh.model.addPhysicalGroup(2, fixed_surfaces, 2)
        gmsh.model.setPhysicalName(2, 2, "MOUNT_FACE")
        gmsh.model.addPhysicalGroup(2, loaded_surfaces, 3)
        gmsh.model.setPhysicalName(2, 3, "LOADED_PAD")
        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.setOrder(2)
        gmsh.model.mesh.optimize("HighOrder")

        types, element_tags, element_blocks = gmsh.model.mesh.getElements(3)
        if list(types) != [11]:
            raise RuntimeError(f"expected Gmsh type 11 tetra10, received {types}")
        elements = np.asarray(element_blocks[0], dtype=np.int64).reshape((-1, 10))
        quality = np.asarray(
            gmsh.model.mesh.getElementQualities(element_tags[0], "minSICN"), dtype=float
        )
        minimum_quality = float(np.min(quality))
        if not math.isfinite(minimum_quality) or minimum_quality <= 0:
            raise RuntimeError(f"invalid or inverted second-order element: {minimum_quality}")
        if minimum_quality < problem.mesh.minimum_minsicn:
            raise RuntimeError(
                "mesh quality is below the declared minimum: "
                f"{minimum_quality:.6g} < {problem.mesh.minimum_minsicn:.6g}"
            )

        node_tags, raw_coordinates, _ = gmsh.model.mesh.getNodes()
        coordinates = {
            int(tag): point
            for tag, point in zip(
                node_tags, np.asarray(raw_coordinates).reshape((-1, 3)), strict=True
            )
        }
        region_records: dict[str, dict[str, Any]] = {}
        for name, selected in (
            ("mount_face", fixed_surfaces),
            ("loaded_pad", loaded_surfaces),
        ):
            region_node_tags = set()
            tri6_count, selected_area = 0, 0.0
            weighted_center = np.zeros(3)
            boxes = []
            for surface in selected:
                tags, _, _ = gmsh.model.mesh.getNodes(2, surface, includeBoundary=True)
                region_node_tags.update(map(int, tags))
                boundary_types, _, boundary_blocks = gmsh.model.mesh.getElements(2, surface)
                if list(boundary_types) != [9]:
                    raise RuntimeError("selected boundary is not entirely triangle6")
                tri6_count += len(boundary_blocks[0]) // 6
                area = gmsh.model.occ.getMass(2, surface)
                selected_area += area
                weighted_center += area * np.array(gmsh.model.occ.getCenterOfMass(2, surface))
                boxes.append(gmsh.model.getBoundingBox(2, surface))
            boxes = np.array(boxes)
            box = np.r_[boxes[:, :3].min(axis=0), boxes[:, 3:].max(axis=0)]
            center = weighted_center / selected_area
            region_records[name] = {
                "area_mm2": float(selected_area),
                "centroid_mm": list(map(float, center)),
                "bounding_box_mm": list(map(float, box)),
                "surface_tags_diagnostic_only": list(map(int, selected)),
                "boundary_nodes_including_edges_and_corners": len(set(map(int, region_node_tags))),
                "triangle6_elements": tri6_count,
            }
        gmsh.write(str(msh_path))
        _write_preview(
            preview_path,
            coordinates,
            surfaces,
            set(fixed_surfaces),
            set(loaded_surfaces),
            (base_length, width, height),
        )
        mesh_manifest = {
            "conservative_element_budget_estimate": element_budget_estimate,
            "conforming_regular_stress_partition": partition_stress_roi,
            "gmsh_version": gmsh.__version__,
            "element_order": 2,
            "volume_element": "Gmsh type 11 / 10-node tetrahedron",
            "nodes": len(coordinates),
            "elements_tetra10": len(elements),
            "minimum_minsicn": minimum_quality,
            "minimum_required_minsicn": problem.mesh.minimum_minsicn,
            "mesh_size_mm": to_si(problem.mesh.size, "meter") * 1000.0,
            "calculix_c3d10_mapping": "swap Gmsh positions 9 and 10 (verified by M0 cantilever)",
            "calculated_boundaries": {
                "mount_face_nodes": region_records["mount_face"][
                    "boundary_nodes_including_edges_and_corners"
                ],
                "loaded_pad_nodes": region_records["loaded_pad"][
                    "boundary_nodes_including_edges_and_corners"
                ],
            },
        }
    finally:
        gmsh.finalize()

    canonical_path.write_text(
        json.dumps(canonical_problem_si(problem), indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    boundary_manifest = {
        "selection_basis": (
            "geometric predicates on coordinates, extents, and area; face tags are diagnostics only"
        ),
        "geometry_mm": {
            "base_length": base_length,
            "width": width,
            "height": height,
            "thickness": thickness,
            "root_radius": root_radius,
        },
        "regions": region_records,
    }
    boundary_path.write_text(
        json.dumps(boundary_manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    mesh_path.write_text(
        json.dumps(mesh_manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return {
        "preparation_status": "prepared_for_solver",
        "analysis_status": "not_run",
        "design_status": "unassessed",
        "problem_name": problem.name,
        "geometry": {
            "kind": "filleted_l_section_bracket",
            "volume_mm3": float(roundtrip.Volume()),
            "step_sha256": _sha256(step_path),
            "step_roundtrip_relative_volume_error": volume_error,
        },
        "mesh": mesh_manifest,
        "regions": region_records,
        "artifacts": {
            path.name: _sha256(path)
            for path in (
                step_path,
                msh_path,
                preview_path,
                canonical_path,
                boundary_path,
                mesh_path,
            )
        },
        "limitations": [
            "geometry and mesh preparation only; solver analysis not run",
            "full rear mounting face is idealized as fixed",
            "entire horizontal base top face is the loaded region",
            "no material allowable or design assessment supplied",
        ],
    }
