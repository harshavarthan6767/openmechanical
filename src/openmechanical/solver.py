"""Auditable single-step C3D10 linear-static solver adapter (mm, N, MPa)."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import gmsh
import numpy as np

from .cantilever import consistent_triangle_load


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class Mesh:
    coordinates: dict[int, np.ndarray]
    elements: dict[int, tuple[int, ...]]  # Gmsh ordering until deck boundary
    volumes: dict[int, float]
    fixed: set[int]
    triangles: list[tuple[int, ...]]
    quality: dict


def read_mesh(path: Path, fixed_name: str, loaded_name: str) -> Mesh:
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.open(str(path))
        tags, xyz, _ = gmsh.model.mesh.getNodes()
        coordinates = dict(zip(map(int, tags), np.asarray(xyz).reshape(-1, 3), strict=True))
        types, ids, blocks = gmsh.model.mesh.getElements(3)
        if list(types) != [11]:
            raise ValueError("only quadratic tetrahedra are supported")
        elements = dict(zip(map(int, ids[0]), map(tuple, blocks[0].reshape(-1, 10)), strict=True))
        if not elements or any(len(set(row)) != 10 for row in elements.values()):
            raise ValueError("empty mesh or repeated element nodes")
        if len({tuple(sorted(row)) for row in elements.values()}) != len(elements):
            raise ValueError("duplicate volume elements")
        if set(coordinates) != {int(n) for row in elements.values() for n in row}:
            raise ValueError("missing or orphan volume nodes")
        if not np.isfinite(np.array(list(coordinates.values()))).all():
            raise ValueError("nonfinite mesh coordinates")
        determinants = np.asarray(gmsh.model.mesh.getElementQualities(ids[0], "minDetJac"))
        quality = np.asarray(gmsh.model.mesh.getElementQualities(ids[0], "minSICN"))
        volumes = np.asarray(gmsh.model.mesh.getElementQualities(ids[0], "volume"))
        if not all(
            np.isfinite(a).all() and np.min(a) > 0 for a in (determinants, quality, volumes)
        ):
            raise ValueError("invalid element Jacobian, quality, or volume")
        groups = {}
        for dim, tag in gmsh.model.getPhysicalGroups(2):
            name = gmsh.model.getPhysicalName(dim, tag)
            if name in groups:
                raise ValueError("duplicate physical group name")
            groups[name] = gmsh.model.getEntitiesForPhysicalGroup(dim, tag)
        fixed = set()
        triangles = []
        for name in (fixed_name, loaded_name):
            if name not in groups:
                raise ValueError(f"missing named boundary: {name}")
            for face in groups[name]:
                surface_types, _, surface_blocks = gmsh.model.mesh.getElements(2, int(face))
                if list(surface_types) != [9]:
                    raise ValueError("boundary must contain triangle6 elements only")
                rows = [tuple(map(int, row)) for row in surface_blocks[0].reshape(-1, 6)]
                if name == fixed_name:
                    fixed.update(n for row in rows for n in row)
                else:
                    triangles.extend(rows)
        loaded = {n for tri in triangles for n in tri}
        if not fixed or not loaded or fixed & loaded:
            raise ValueError("empty or overlapping fixed and loaded regions")
        points = np.array([coordinates[n] for n in fixed])
        if np.linalg.matrix_rank(points - points.mean(axis=0)) < 2:
            raise ValueError("fixed support does not constrain all rigid motions")
        # All volume nodes must be connected to the fixed component.
        parent = {n: n for n in coordinates}

        def find(n):
            while parent[n] != n:
                parent[n] = parent[parent[n]]
                n = parent[n]
            return n

        for row in elements.values():
            for node in row[1:]:
                parent[find(node)] = find(row[0])
        if len({find(n) for n in coordinates}) != 1:
            raise ValueError("disconnected solid mesh")
        return Mesh(
            coordinates,
            elements,
            dict(zip(elements, map(float, volumes), strict=True)),
            fixed,
            triangles,
            {
                "minimum_minsicn": float(quality.min()),
                "minimum_jacobian_determinant": float(determinants.min()),
                "jacobian_method": "Gmsh adaptive minDetJac on quadratic geometry",
            },
        )
    finally:
        gmsh.finalize()


def assemble_traction(mesh: Mesh, traction: np.ndarray):
    """Exact constant-traction integration for planar straight-sided triangle6 faces."""
    loads = {}
    area_sum, area_center = 0.0, np.zeros(3)
    for triangle in mesh.triangles:
        xyz = [mesh.coordinates[n] for n in triangle]
        scale = max(np.linalg.norm(xyz[1] - xyz[0]), np.linalg.norm(xyz[2] - xyz[0]))
        for midpoint, (a, b) in zip(xyz[3:], ((0, 1), (1, 2), (2, 0)), strict=True):
            if np.linalg.norm(midpoint - (xyz[a] + xyz[b]) / 2) > 1e-8 * scale:
                raise ValueError(
                    "curved/non-midpoint load triangles require isoparametric quadrature"
                )
        area = np.linalg.norm(np.cross(xyz[1] - xyz[0], xyz[2] - xyz[0])) / 2
        if area <= 0 or not math.isfinite(area):
            raise ValueError("degenerate load triangle")
        area_sum += area
        area_center += area * np.mean(xyz[:3], axis=0)
        for node, force in consistent_triangle_load(triangle, mesh.coordinates, traction).items():
            loads.setdefault(node, np.zeros(3))
            loads[node] += force
    centroid = area_center / area_sum
    expected = area_sum * traction
    actual = np.sum(list(loads.values()), axis=0)
    moment = sum((np.cross(mesh.coordinates[n], f) for n, f in loads.items()), np.zeros(3))
    expected_moment = np.cross(centroid, expected)
    length = float(np.linalg.norm(np.ptp(np.array(list(mesh.coordinates.values())), axis=0)))
    force_scale = np.linalg.norm(expected)
    if not math.isfinite(force_scale) or force_scale <= 0:
        raise ValueError("zero or nonfinite load")
    moment_scale = max(force_scale * length, np.linalg.norm(expected_moment))
    force_error = float(np.linalg.norm(actual - expected) / force_scale)
    moment_error = float(np.linalg.norm(moment - expected_moment) / moment_scale)
    if max(force_error, moment_error) > 1e-10:
        raise ValueError("load force/moment integration failed")
    return loads, {
        "area_mm2": float(area_sum),
        "centroid_mm": centroid.tolist(),
        "force_N": expected.tolist(),
        "moment_Nmm": expected_moment.tolist(),
        "force_assembly_error": force_error,
        "moment_assembly_error": moment_error,
        "moment_scale_Nmm": float(moment_scale),
    }


def _dat_lines(path: Path):
    with path.open(encoding="ascii") as stream:
        yield from stream


def parse_dat(path: Path, nodes: set[int], fixed: set[int], elements: set[int]):
    """Reject unknown/truncated/repeated DAT tables for one static increment at time 1."""
    tables = {"u": {}, "rf": {}, "s": {}}
    seen = set()
    mode = None
    steps, increments = [], []
    for line in _dat_lines(path):
        stripped = line.strip()
        if not stripped:
            continue
        if re.search(r"S\s+T\s+E\s+P", line):
            steps.append(int(stripped.split()[-1]))
            mode = None
            continue
        if stripped.startswith("INCREMENT"):
            increments.append(int(stripped.split()[-1]))
            mode = None
            continue
        if " for set " in line and " and time " in line:
            header = line.lower()
            if "displacements (vx,vy,vz)" in header and "set nall " in header:
                mode = "u"
            elif "forces (fx,fy,fz)" in header and "set fix " in header:
                mode = "rf"
            elif (
                "stresses (elem, integ.pnt.,sxx,syy,szz,sxy,sxz,syz)" in header
                and "set eall " in header
            ):
                mode = "s"
            else:
                raise ValueError(f"unsupported DAT table: {stripped}")
            if mode in seen or not math.isclose(float(stripped.split()[-1]), 1.0, abs_tol=1e-8):
                raise ValueError("duplicate table or unexpected output time")
            seen.add(mode)
            continue
        if mode is None:
            raise ValueError(f"unexpected DAT record: {stripped}")
        fields = stripped.replace("D", "E").split()
        width = 8 if mode == "s" else 4
        if len(fields) != width:
            raise ValueError("malformed or truncated DAT record")
        key = (int(fields[0]), int(fields[1])) if mode == "s" else int(fields[0])
        values = np.array(list(map(float, fields[2:] if mode == "s" else fields[1:])))
        if not np.isfinite(values).all() or key in tables[mode]:
            raise ValueError("nonfinite or duplicate DAT result")
        tables[mode][key] = values
    if steps != [1] or increments != [1] or seen != {"u", "rf", "s"}:
        raise ValueError("missing or unsupported step/increment/tables")
    if set(tables["u"]) != nodes or set(tables["rf"]) != fixed:
        raise ValueError("incomplete displacement/reaction node coverage")
    if set(tables["s"]) != {(e, i) for e in elements for i in range(1, 5)}:
        raise ValueError("incomplete C3D10 integration-point stress coverage")
    return tables


def von_mises(stress):
    xx, yy, zz, xy, xz, yz = stress
    return float(
        np.sqrt(
            ((xx - yy) ** 2 + (yy - zz) ** 2 + (zz - xx) ** 2) / 2 + 3 * (xy**2 + xz**2 + yz**2)
        )
    )


def solve(
    mesh: Mesh,
    youngs: float,
    poisson: float,
    traction: np.ndarray,
    out: Path,
    stress_roi: tuple[float, float, float, float] | None = None,
    timeout: float = 300,
) -> dict:
    out.mkdir(parents=True, exist_ok=False)
    if len(mesh.coordinates) > 1000000 or len(mesh.elements) > 500000:
        raise ValueError("mesh exceeds the configured 1M-node/500k-element solver budget")
    if not math.isfinite(youngs) or youngs <= 0 or not -1 < poisson < 0.5:
        raise ValueError("invalid elastic properties")
    loads, load_info = assemble_traction(mesh, traction)
    write_json(
        out / "analysis-policy.json",
        {
            "units": "mm, N, MPa",
            "youngs_modulus_MPa": youngs,
            "poisson_ratio": poisson,
            "traction_MPa": traction.tolist(),
            "stress_roi_xy_mm": stress_roi,
            "stress_quantity": (
                "volume-weighted RMS integration-point von Mises in centroid-selected ROI"
            ),
            "stress_location": "C3D10 integration points; not extrapolated or nodally averaged",
            "equilibrium_relative_tolerance": 0.001,
            "solver_timeout_seconds": timeout,
        },
    )
    lines = ["*HEADING", "OpenMechanical audited linear static; mm N MPa", "*NODE, NSET=NALL"]
    for node, xyz in sorted(mesh.coordinates.items()):
        lines.append(f"{node}, " + ", ".join(f"{x:.15g}" for x in xyz))
    lines.append("*ELEMENT, TYPE=C3D10, ELSET=EALL")
    for element, row in sorted(mesh.elements.items()):
        ccx = row[:8] + (row[9], row[8])
        lines.append(f"{element}, " + ", ".join(map(str, ccx)))
    lines.append("*NSET, NSET=FIX")
    ordered = sorted(mesh.fixed)
    lines.extend(", ".join(map(str, ordered[i : i + 12])) for i in range(0, len(ordered), 12))
    lines.extend(
        [
            "*MATERIAL, NAME=MAT",
            "*ELASTIC",
            f"{youngs:.15g}, {poisson:.15g}",
            "*SOLID SECTION, ELSET=EALL, MATERIAL=MAT",
            ",",
            "*STEP",
            "*STATIC",
            "*BOUNDARY",
            "FIX, 1, 3, 0.",
            "*CLOAD",
        ]
    )
    for node, force in sorted(loads.items()):
        for dof, component in enumerate(force, 1):
            if abs(component) > 1e-14:
                lines.append(f"{node}, {dof}, {component:.15g}")
    lines.extend(
        [
            "*NODE PRINT, NSET=NALL",
            "U",
            "*NODE PRINT, NSET=FIX",
            "RF",
            "*EL PRINT, ELSET=EALL",
            "S",
            "*NODE FILE",
            "U, RF",
            "*EL FILE",
            "S",
            "*END STEP",
        ]
    )
    (out / "analysis.inp").write_text("\n".join(lines) + "\n", encoding="ascii")
    command = shutil.which("ccx")
    if command is None:
        raise RuntimeError("CalculiX executable is missing")
    start = time.monotonic()
    with (
        (out / "solver.stdout.txt").open("w") as stdout,
        (out / "solver.stderr.txt").open("w") as stderr,
    ):
        try:
            process = subprocess.run(
                [command, "analysis"],
                cwd=out,
                stdout=stdout,
                stderr=stderr,
                timeout=timeout,
                check=False,
                env={**os.environ, "OMP_NUM_THREADS": "2"},
            )
        except subprocess.TimeoutExpired:
            write_json(
                out / "failure.json", {"execution_status": "failed", "error": "solver_timeout"}
            )
            raise
    output = (out / "solver.stdout.txt").read_text()
    diagnostics = output + "\n" + (out / "solver.stderr.txt").read_text()
    warnings = [line.strip() for line in diagnostics.splitlines() if "WARNING" in line.upper()]
    if process.returncode or "Job finished" not in output or "*ERROR" in diagnostics.upper():
        write_json(out / "failure.json", {"execution_status": "failed", "error": "solver_failure"})
        raise RuntimeError("CalculiX failed; inspect retained logs")
    results = parse_dat(out / "analysis.dat", set(mesh.coordinates), mesh.fixed, set(mesh.elements))
    reactions = results["rf"]
    reaction = np.sum(list(reactions.values()), axis=0)
    moment = sum((np.cross(mesh.coordinates[n], f) for n, f in reactions.items()), np.zeros(3))
    force_error = float(
        np.linalg.norm(reaction + load_info["force_N"]) / np.linalg.norm(load_info["force_N"])
    )
    moment_error = float(
        np.linalg.norm(moment + load_info["moment_Nmm"]) / load_info["moment_scale_Nmm"]
    )
    # Consistent surface weights produce the integral of interpolated displacement.
    unit_loads, _ = assemble_traction(mesh, np.array([0.0, 0.0, 1.0]))
    mean_u = (
        sum((f[2] * results["u"][n] for n, f in unit_loads.items()), np.zeros(3))
        / load_info["area_mm2"]
    )
    stress = {key: von_mises(value) for key, value in results["s"].items()}
    maximum_strain = 0.0
    for values in results["s"].values():
        xx, yy, zz, xy, xz, yz = values
        tensor = np.array([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]])
        strain = ((1 + poisson) * tensor - poisson * np.trace(tensor) * np.eye(3)) / youngs
        maximum_strain = max(maximum_strain, float(np.max(np.abs(np.linalg.eigvalsh(strain)))))
    peak = max(stress, key=stress.get)
    roi_elements = []
    if stress_roi is not None:
        xmin, xmax, ymin, ymax = stress_roi
        for element, nodes in mesh.elements.items():
            center = np.mean([mesh.coordinates[n] for n in nodes[:4]], axis=0)
            if xmin <= center[0] <= xmax and ymin <= center[1] <= ymax:
                # The RMS quadrature below assumes straight-sided tetrahedra.
                xyz = [mesh.coordinates[n] for n in nodes]
                for mid, (a, b) in zip(
                    xyz[4:], ((0, 1), (1, 2), (2, 0), (0, 3), (2, 3), (1, 3)), strict=True
                ):
                    if not np.allclose(mid, (xyz[a] + xyz[b]) / 2, rtol=0, atol=1e-7):
                        raise ValueError("stress ROI includes curved tetrahedra")
                roi_elements.append(element)
        if not roi_elements:
            raise ValueError("predeclared stress ROI contains no elements")
    roi_volume = sum(mesh.volumes[e] for e in roi_elements)
    rms = (
        math.sqrt(
            sum(
                mesh.volumes[e] * sum(stress[(e, i)] ** 2 for i in range(1, 5)) / 4
                for e in roi_elements
            )
            / roi_volume
        )
        if roi_elements
        else None
    )
    version = subprocess.run([command, "-v"], capture_output=True, text=True, timeout=10)
    version_match = re.search(r"This is Version\s+(\S+)", version.stdout + version.stderr)
    summary = {
        "execution_status": "completed",
        "numerical_status": "incomplete",
        "design_status": "unassessed",
        "physical_validation": "not_performed",
        "mesh": {"nodes": len(mesh.coordinates), "elements": len(mesh.elements), **mesh.quality},
        "load": load_info,
        "result": {
            "area_mean_loaded_displacement_mm": mean_u.tolist(),
            "maximum_nodal_displacement_mm": float(
                max(np.linalg.norm(u) for u in results["u"].values())
            ),
            "support_reaction_N": reaction.tolist(),
            "support_moment_Nmm": moment.tolist(),
        },
        "stress": {
            "maximum_absolute_principal_elastic_strain": maximum_strain,
            "location": "integration_point",
            "components": "sxx syy szz sxy sxz syz",
            "raw_peak_von_mises_MPa": stress[peak],
            "peak_element_id": peak[0],
            "peak_integration_point": peak[1],
            "roi_rms_von_mises_MPa": rms,
            "roi_elements": len(roi_elements),
            "roi_volume_mm3": roi_volume,
            "roi_bounds_xy_mm": stress_roi,
        },
        "checks": {
            "force_balance": force_error <= 0.001,
            "moment_balance": moment_error <= 0.001,
            "complete_displacements_reactions_stresses": True,
            "no_unreviewed_solver_warnings": not warnings,
        },
        "force_residual_relative": force_error,
        "moment_residual_relative": moment_error,
        "solver": {
            "version": version_match.group(1) if version_match else "unknown",
            "binary_sha256": sha256(Path(command).resolve()),
            "command": [command, "analysis"],
            "elapsed_seconds": time.monotonic() - start,
        },
        "warnings": warnings,
        "artifacts": {p.name: sha256(p) for p in out.iterdir() if p.is_file()},
    }
    if not all(summary["checks"].values()):
        summary["numerical_status"] = "failed"
    write_json(out / "result.json", summary)
    return summary
