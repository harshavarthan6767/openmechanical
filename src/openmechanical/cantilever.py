#!/usr/bin/env python3
"""Real CadQuery -> STEP -> Gmsh -> CalculiX cantilever proof (mm, N, MPa)."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import shutil
import subprocess
import time
import uuid
from collections.abc import Sequence
from pathlib import Path

import cadquery as cq
import gmsh
import numpy as np
from pydantic import ValidationError

from openmechanical.contracts import BoxGeometry, validate_problem
from openmechanical.units import canonical_problem_si, to_si, validate_problem_units


class InvalidProblemError(ValueError):
    """A user-provided problem cannot be handled by the M0 workflow."""


class DependencyError(RuntimeError):
    """A required external engineering tool is unavailable."""


class SolverError(RuntimeError):
    """The solver failed or did not produce the expected evidence."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def in_box(bb: tuple[float, ...], axis: int, target: float, tol: float) -> bool:
    return abs(bb[axis] - target) <= tol and abs(bb[axis + 3] - target) <= tol


def make_geometry(path: Path, length: float, width: float, height: float) -> None:
    shape = cq.Workplane("XY").box(length, width, height, centered=(False, False, False)).val()
    if not shape.isValid() or len(shape.Solids()) != 1:
        raise RuntimeError("CadQuery produced an invalid solid")
    cq.exporters.export(shape, str(path), exportType="STEP", unit="MM")
    check = cq.importers.importStep(str(path)).val()
    if not check.isValid() or len(check.Solids()) != 1:
        raise RuntimeError("STEP round trip did not produce a valid solid")
    delta = abs(check.Volume() - shape.Volume()) / shape.Volume()
    if delta > 1e-8:
        raise RuntimeError(f"STEP round trip volume changed by {delta:.3g}")


def gather_nodes(tags: list[int]) -> set[int]:
    return {int(node) for node in tags}


def consistent_triangle_load(
    nodes: tuple[int, ...], coordinates: dict[int, np.ndarray], traction: np.ndarray
) -> dict[int, np.ndarray]:
    """Integrate constant traction on a flat six-node quadratic triangle."""
    corner = [coordinates[int(node)] for node in nodes[:3]]
    area = 0.5 * float(np.linalg.norm(np.cross(corner[1] - corner[0], corner[2] - corner[0])))
    if not math.isfinite(area) or area <= 0.0:
        raise ValueError("degenerate load-surface triangle")
    # Three-point symmetric degree-two rule. Gmsh tri6 order is corners 1-3,
    # then edges 1-2, 2-3, 3-1 (verified from getElementProperties(9)).
    barycentric_points = (
        (2 / 3, 1 / 6, 1 / 6),
        (1 / 6, 2 / 3, 1 / 6),
        (1 / 6, 1 / 6, 2 / 3),
    )
    contribution = {int(node): np.zeros(3, dtype=float) for node in nodes}
    for l1, l2, l3 in barycentric_points:
        shape = (
            l1 * (2 * l1 - 1),
            l2 * (2 * l2 - 1),
            l3 * (2 * l3 - 1),
            4 * l1 * l2,
            4 * l2 * l3,
            4 * l3 * l1,
        )
        for node, weight in zip(nodes, shape, strict=True):
            contribution[int(node)] += traction * area * weight / 3.0
    return contribution


def parse_dat(
    path: Path, fix: set[int], tip: set[int]
) -> tuple[dict[int, np.ndarray], dict[int, np.ndarray]]:
    lines = path.read_text(errors="replace").splitlines()
    mode: str | None = None
    pending: dict[str, dict[int, np.ndarray]] = {"u": {}, "rf": {}}
    for line in lines:
        low = line.lower()
        if "displacements" in low:
            mode = "u"
            continue
        if "forces (fx,fy,fz)" in low or "forces (fx, fy, fz)" in low:
            mode = "rf"
            continue
        if not line.strip():
            continue
        if mode:
            match = re.match(r"^\s*(\d+)\s+([-+0-9.Ee]+)\s+([-+0-9.Ee]+)\s+([-+0-9.Ee]+)\s*$", line)
            if match:
                node = int(match.group(1))
                pending[mode][node] = np.array([float(match.group(i)) for i in (2, 3, 4)])
    if not pending["u"]:
        raise RuntimeError(f"could not parse displacement output in {path}")
    u_tip = {node: value for node, value in pending["u"].items() if node in tip}
    # CalculiX often prints a separate table per NSET; merge each reaction block.
    rf = {node: value for node, value in pending["rf"].items() if node in fix}
    if not u_tip:
        # If the DAT writer only emitted the requested print set, TIP was printed.
        raise RuntimeError("no end-face displacements found in CalculiX DAT output")
    if not rf:
        raise RuntimeError("no clamp reactions found in CalculiX DAT output")
    return u_tip, rf


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value!r} is not allowed")


def _run(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--spec", type=Path, help="ProblemSpec JSON for a traction-loaded box")
    parser.add_argument("--mesh-size", type=float, help="characteristic length in mm")
    parser.add_argument("--length", type=float, help="beam length in mm")
    parser.add_argument("--width", type=float, help="beam width in mm")
    parser.add_argument("--height", type=float, help="beam height in mm")
    parser.add_argument("--force", type=float, help="resultant load magnitude in N")
    parser.add_argument("--youngs-modulus", type=float, help="Young's modulus in MPa")
    parser.add_argument("--poisson-ratio", type=float)
    args = parser.parse_args(argv)

    length, width, height = 200.0, 20.0, 10.0
    mesh_size, force, youngs_modulus, poisson_ratio = 5.0, 100.0, 210000.0, 0.3
    load_direction = np.array([0.0, 0.0, -1.0])
    spec_digest = None
    if args.spec:
        if any(
            value is not None
            for value in (
                args.mesh_size,
                args.length,
                args.width,
                args.height,
                args.force,
                args.youngs_modulus,
                args.poisson_ratio,
            )
        ):
            raise InvalidProblemError(
                "numeric overrides cannot be combined with --spec; edit the spec instead"
            )
        try:
            spec_bytes = args.spec.read_bytes()
            problem = validate_problem(json.loads(spec_bytes, parse_constant=_reject_constant))
            validate_problem_units(problem)
        except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise InvalidProblemError(f"invalid problem specification: {exc}") from exc
        if not isinstance(problem.geometry, BoxGeometry):
            raise InvalidProblemError(
                "M0 supports box geometry; STEP import has not been implemented yet"
            )
        if len(problem.loads) != 1 or problem.loads[0].kind != "traction":
            raise InvalidProblemError("M0 requires exactly one vector traction load")
        if len(problem.constraints) != 1 or problem.constraints[0].kind != "fixed":
            raise InvalidProblemError("M0 requires exactly one fixed support")
        if problem.loads[0].region != "loaded_end" or problem.constraints[0].region != "fixed_end":
            raise InvalidProblemError("M0 regions must be named 'fixed_end' and 'loaded_end'")
        direction = np.asarray(problem.loads[0].direction, dtype=float)
        direction /= np.linalg.norm(direction)
        if not np.allclose(direction, [0.0, 0.0, -1.0], atol=1e-12, rtol=0.0):
            raise InvalidProblemError(
                "M0's Timoshenko reference requires a downward -Z traction direction"
            )
        length = to_si(problem.geometry.length, "meter") * 1000
        width = to_si(problem.geometry.width, "meter") * 1000
        height = to_si(problem.geometry.height, "meter") * 1000
        mesh_size = to_si(problem.mesh.size, "meter") * 1000
        youngs_modulus = to_si(problem.material.youngs_modulus, "pascal") / 1e6
        poisson_ratio = problem.material.poisson_ratio
        load_direction = direction
        traction_mpa = to_si(problem.loads[0].magnitude, "pascal") / 1e6
        force = traction_mpa * width * height
        spec_digest = hashlib.sha256(spec_bytes).hexdigest()

    length = args.length if args.length is not None else length
    width = args.width if args.width is not None else width
    height = args.height if args.height is not None else height
    mesh_size = args.mesh_size if args.mesh_size is not None else mesh_size
    force = args.force if args.force is not None else force
    youngs_modulus = args.youngs_modulus if args.youngs_modulus is not None else youngs_modulus
    poisson_ratio = args.poisson_ratio if args.poisson_ratio is not None else poisson_ratio
    if min(mesh_size, length, width, height, force, youngs_modulus) <= 0:
        raise InvalidProblemError(
            "mesh and geometry dimensions, force, and Young's modulus must be positive"
        )
    if not -1 < poisson_ratio < 0.5:
        raise InvalidProblemError("Poisson ratio must be in (-1, 0.5)")

    requested_out = args.out.resolve()
    out = requested_out
    if requested_out.exists() and not requested_out.is_dir():
        raise InvalidProblemError(f"output path exists and is not a directory: {requested_out}")
    if requested_out.exists() and any(requested_out.iterdir()):
        suffix = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:8]}"
        out = requested_out.with_name(f"{requested_out.name}-{suffix}")
    out.mkdir(parents=True, exist_ok=True)
    step_path = out / "cantilever.step"
    inp_path = out / "cantilever.inp"
    original_spec_path = out / "problem.original.json"
    canonical_spec_path = out / "problem.canonical.json"
    if spec_digest is not None:
        original_spec_path.write_bytes(spec_bytes)
        canonical_spec_path.write_text(
            json.dumps(canonical_problem_si(problem), indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    make_geometry(step_path, length, width, height)

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.option.setNumber("Mesh.MeshSizeMin", mesh_size)
        gmsh.option.setNumber("Mesh.MeshSizeMax", mesh_size)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)
        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
        gmsh.option.setNumber("Mesh.ElementOrder", 2)
        gmsh.option.setNumber("Mesh.SecondOrderLinear", 0)
        gmsh.model.add("cantilever")
        gmsh.model.occ.importShapes(str(step_path), highestDimOnly=True)
        gmsh.model.occ.synchronize()
        volumes = gmsh.model.getEntities(3)
        if len(volumes) != 1:
            raise RuntimeError(f"expected one solid volume, found {len(volumes)}")
        volume = volumes[0][1]
        tol = max(length, width, height) * 1e-8
        surfaces = gmsh.model.getEntities(2)
        fix_surfaces = [
            tag for dim, tag in surfaces if in_box(gmsh.model.getBoundingBox(dim, tag), 0, 0.0, tol)
        ]
        tip_surfaces = [
            tag
            for dim, tag in surfaces
            if in_box(gmsh.model.getBoundingBox(dim, tag), 0, length, tol)
        ]
        if len(fix_surfaces) != 1 or len(tip_surfaces) != 1:
            raise RuntimeError(
                f"end-face selection ambiguous: fixed={fix_surfaces}, tip={tip_surfaces}"
            )
        gmsh.model.addPhysicalGroup(3, [volume], 1)
        gmsh.model.setPhysicalName(3, 1, "SOLID")
        gmsh.model.addPhysicalGroup(2, fix_surfaces, 2)
        gmsh.model.setPhysicalName(2, 2, "FIXED_END")
        gmsh.model.addPhysicalGroup(2, tip_surfaces, 3)
        gmsh.model.setPhysicalName(2, 3, "LOADED_END")
        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.setOrder(2)
        gmsh.model.mesh.optimize("HighOrder")
        gmsh.write(str(out / "cantilever.msh"))

        node_tags_raw, xyz_raw, _ = gmsh.model.mesh.getNodes()
        node_tags = [int(tag) for tag in node_tags_raw]
        xyz = np.asarray(xyz_raw, dtype=float).reshape((-1, 3))
        coordinates = {tag: point for tag, point in zip(node_tags, xyz, strict=True)}
        to_label = {tag: index + 1 for index, tag in enumerate(sorted(node_tags))}

        element_types, element_tags, element_nodes = gmsh.model.mesh.getElements(3, volume)
        if list(element_types) != [11]:
            raise RuntimeError(
                f"expected only Gmsh type 11 (10-node tetrahedra), received {element_types}"
            )
        tet_nodes = np.asarray(element_nodes[0], dtype=np.int64).reshape((-1, 10))
        element_rows = [tuple(map(int, row)) for row in tet_nodes]
        element_labels = {row_index: row_index + 1 for row_index in range(len(element_rows))}
        quality = np.asarray(
            gmsh.model.mesh.getElementQualities(element_tags[0], "minSICN"), dtype=float
        )
        min_quality = float(np.min(quality))
        if not math.isfinite(min_quality) or min_quality <= 0:
            raise RuntimeError(
                f"mesh contains an invalid or inverted high-order element (minSICN={min_quality})"
            )

        fix_nodes = set()
        for surface in fix_surfaces:
            tags, _, _ = gmsh.model.mesh.getNodes(2, surface, includeBoundary=True)
            fix_nodes |= gather_nodes(tags)
        tip_nodes = set()
        for surface in tip_surfaces:
            tags, _, _ = gmsh.model.mesh.getNodes(2, surface, includeBoundary=True)
            tip_nodes |= gather_nodes(tags)
        if not fix_nodes or not tip_nodes:
            raise RuntimeError("support/load face resolved to an empty node set")

        area = width * height
        force_vector = force * load_direction
        traction = force_vector / area
        nodal_loads: dict[int, np.ndarray] = {}
        loaded_tri6_count = 0
        for surface in tip_surfaces:
            types, _, element_node_blocks = gmsh.model.mesh.getElements(2, surface)
            for elem_type, elem_block in zip(types, element_node_blocks, strict=True):
                if int(elem_type) != 9:
                    raise RuntimeError(
                        f"unsupported end-face element type {elem_type}; expected Gmsh triangle6"
                    )
                triangles = np.asarray(elem_block, dtype=np.int64).reshape((-1, 6))
                loaded_tri6_count += len(triangles)
                for tri in triangles:
                    add = consistent_triangle_load(tuple(map(int, tri)), coordinates, traction)
                    for node, nodal_force in add.items():
                        nodal_loads.setdefault(node, np.zeros(3, dtype=float))
                        nodal_loads[node] += nodal_force
        assembled_force = np.sum(list(nodal_loads.values()), axis=0)
        force_error = float(np.linalg.norm(assembled_force - force_vector) / force)
        if force_error > 1e-10:
            raise RuntimeError(
                f"consistent load integration failed resultant check: {force_error:.3g}"
            )

        # Gmsh tetrahedron10 node 9/10 are edges 3-4 / 2-4; CalculiX C3D10
        # orders these edge midsides as 2-4 / 3-4. This explicit swap is the
        # documented interoperability mapping under test in this proof.
        deck_lines = ["*HEADING", "OpenMechanical M0 cantilever; units mm, N, MPa", "*NODE"]
        for tag, point in sorted(coordinates.items(), key=lambda item: to_label[item[0]]):
            deck_lines.append(f"{to_label[tag]}, {point[0]:.12g}, {point[1]:.12g}, {point[2]:.12g}")
        deck_lines.extend(["*ELEMENT, TYPE=C3D10, ELSET=EALL"])
        for row_index, row in enumerate(element_rows):
            ccx_nodes = row[:8] + (row[9], row[8])
            deck_lines.append(
                f"{element_labels[row_index]}, " + ", ".join(str(to_label[n]) for n in ccx_nodes)
            )
        for name, node_set in (("FIX", fix_nodes), ("TIP", tip_nodes)):
            deck_lines.append(f"*NSET, NSET={name}")
            labels = [to_label[node] for node in sorted(node_set)]
            deck_lines.extend(
                ", ".join(map(str, labels[i : i + 12])) for i in range(0, len(labels), 12)
            )
        deck_lines.extend(
            [
                "*MATERIAL, NAME=MAT",
                "*ELASTIC",
                f"{youngs_modulus:.12g}, {poisson_ratio:.12g}",
                "*SOLID SECTION, ELSET=EALL, MATERIAL=MAT",
                ",",
                "*STEP",
                "*STATIC",
                "*BOUNDARY",
                "FIX, 1, 3, 0.",
                "*CLOAD",
            ]
        )
        for node, nodal_force in sorted(nodal_loads.items(), key=lambda item: to_label[item[0]]):
            for dof, component in enumerate(nodal_force, start=1):
                if abs(component) > 1e-14:
                    deck_lines.append(f"{to_label[node]}, {dof}, {component:.15g}")
        deck_lines.extend(
            [
                "*NODE PRINT, NSET=FIX",
                "RF",
                "*NODE PRINT, NSET=TIP",
                "U",
                "*NODE FILE",
                "U, RF",
                "*EL FILE",
                "S",
                "*END STEP",
            ]
        )
        inp_path.write_text("\n".join(deck_lines) + "\n", encoding="ascii")
        mesh_info = {
            "gmsh_version": gmsh.__version__,
            "gmsh_tetra_ordering": "corner 1-4; edge midsides 1-2, 2-3, 3-1, 1-4, 3-4, 2-4",
            "calculix_mapping": "C3D10: swap Gmsh positions 9 and 10",
            "nodes": len(node_tags),
            "elements_c3d10": len(element_rows),
            "fixed_end_nodes": len(fix_nodes),
            "loaded_end_nodes": len(tip_nodes),
            "loaded_end_tri6": loaded_tri6_count,
            "min_element_quality_minsicn": min_quality,
            "mesh_size_mm": mesh_size,
        }
    finally:
        gmsh.finalize()

    command = shutil.which("ccx")
    if command is None:
        raise DependencyError("CalculiX executable 'ccx' was not found on PATH")
    start = time.time()
    result = subprocess.run(
        [command, "cantilever"], cwd=out, capture_output=True, text=True, timeout=300
    )
    (out / "solver.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (out / "solver.stderr.txt").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0 or "Job finished" not in result.stdout:
        raise SolverError(
            f"CalculiX failed (exit {result.returncode}); "
            "inspect solver.stdout.txt and solver.stderr.txt"
        )
    version_result = subprocess.run([command, "-v"], capture_output=True, text=True, timeout=10)
    version_text = version_result.stdout + version_result.stderr
    version_match = re.search(r"This is Version\s+([^\s]+)", version_text)
    fix_labels = {to_label[node] for node in fix_nodes}
    tip_labels = {to_label[node] for node in tip_nodes}
    u_tip, reactions = parse_dat(out / "cantilever.dat", fix_labels, tip_labels)
    tip_u = np.mean(list(u_tip.values()), axis=0)
    reaction = np.sum(list(reactions.values()), axis=0)
    expected_force = force_vector
    equilibrium_error = float(np.linalg.norm(reaction + expected_force) / force)
    label_to_tag = {label: tag for tag, label in to_label.items()}
    reaction_moment = np.zeros(3, dtype=float)
    for node, reaction_force in reactions.items():
        reaction_moment += np.cross(coordinates[label_to_tag[node]], reaction_force)
    loaded_centroid = np.array([length, width / 2, height / 2])
    applied_moment = np.cross(loaded_centroid, expected_force)
    moment_scale = max(float(np.linalg.norm(applied_moment)), force * length)
    moment_equilibrium_error = float(
        np.linalg.norm(reaction_moment + applied_moment) / moment_scale
    )

    E = youngs_modulus
    nu = poisson_ratio
    G = E / (2 * (1 + nu))
    area = width * height
    second_moment = width * height**3 / 12
    kappa = 5 / 6
    euler_bernoulli_mm = force * length**3 / (3 * E * second_moment)
    timoshenko_mm = euler_bernoulli_mm + force * length / (kappa * G * area)
    relative_error = abs(abs(float(tip_u[2])) - timoshenko_mm) / timoshenko_mm
    summary = {
        "execution_status": "completed",
        "numerical_status": "incomplete",
        "design_status": "unassessed",
        "model": "3D isotropic linear-elastic fixed-free cantilever, C3D10",
        "problem_name": problem.name if spec_digest is not None else "default cantilever proof",
        "units": {
            "geometry": "mm",
            "force": "N",
            "stress": "MPa",
            "youngs_modulus": "MPa",
            "displacement": "mm",
        },
        "material": {"youngs_modulus_MPa": E, "poisson_ratio": nu},
        "load": {
            "end_resultant_N": expected_force.tolist(),
            "surface_area_mm2": area,
            "traction_MPa": traction.tolist(),
        },
        "mesh": mesh_info,
        "result": {
            "mean_tip_displacement_mm": tip_u.tolist(),
            "support_reaction_N": reaction.tolist(),
        },
        "verification": {
            "integrated_load_resultant_relative_error": force_error,
            "force_equilibrium_relative_error": equilibrium_error,
            "reaction_moment_Nmm": reaction_moment.tolist(),
            "applied_moment_about_origin_Nmm": applied_moment.tolist(),
            "moment_equilibrium_relative_error": moment_equilibrium_error,
            "timoshenko_tip_deflection_mm": timoshenko_mm,
            "euler_bernoulli_tip_deflection_mm": euler_bernoulli_mm,
            "fea_tip_deflection_relative_error": relative_error,
            "reference_scope": (
                "Timoshenko beam estimate for slender rectangular beam; "
                "not an experimental validation"
            ),
            "mesh_convergence": "not_run",
            "stress_assessment": "not_run",
        },
        "solver": {
            "name": "CalculiX",
            "version": version_match.group(1) if version_match else "unknown",
            "executable_sha256": sha256(Path(command).resolve()),
            "runtime_seconds": time.time() - start,
            "command": [command, "cantilever"],
        },
        "run_directory": str(out),
        "problem_spec_sha256": spec_digest,
        "input_files": (
            {
                "original": original_spec_path.name,
                "canonical": canonical_spec_path.name,
            }
            if spec_digest is not None
            else None
        ),
        "runtime": {
            "python": platform.python_version(),
            "cadquery": cq.__version__,
            "gmsh": gmsh.__version__,
        },
        "artifacts": {
            path.name: sha256(path)
            for path in (
                step_path,
                out / "cantilever.msh",
                inp_path,
                out / "cantilever.dat",
                out / "cantilever.frd",
                original_spec_path,
                canonical_spec_path,
            )
            if path.is_file()
        },
        "limitations": [
            "M0 integration proof only",
            "mesh convergence not run",
            "no material allowable supplied",
            "not suitable as a design safety determination",
        ],
    }
    (out / "m0_summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, allow_nan=False))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return _run(argv)
    except InvalidProblemError as exc:
        print(
            json.dumps(
                {"execution_status": "failed", "error_type": "invalid_input", "error": str(exc)}
            )
        )
        return 2
    except DependencyError as exc:
        print(
            json.dumps(
                {
                    "execution_status": "failed",
                    "error_type": "dependency_missing",
                    "error": str(exc),
                }
            )
        )
        return 3
    except SolverError as exc:
        print(
            json.dumps(
                {"execution_status": "failed", "error_type": "solver_failure", "error": str(exc)}
            )
        )
        return 4
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "execution_status": "failed",
                    "error_type": "execution_failure",
                    "error": str(exc),
                }
            )
        )
        return 5


if __name__ == "__main__":
    raise SystemExit(main())
