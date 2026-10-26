#!/usr/bin/env python3
"""Run the controlled C3D10 mesh-quality and cantilever-response pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import gmsh
import numpy as np


LENGTH_MM = 200.0
WIDTH_MM = 20.0
HEIGHT_MM = 10.0
FORCE_N = 100.0
YOUNGS_MODULUS_MPA = 210000.0
POISSON_RATIO = 0.3
REFERENCE_MM = 0.7633904761904763
RESPONSE_TOLERANCE = 0.02
QUALITY_THRESHOLDS = (0.05, 0.10, 0.20)
DEFAULT_SIZES_MM = (5.0, 5.0 / math.sqrt(2), 2.5)
DEFAULT_AMPLITUDES = (0.0, 0.0025, 0.005, 0.01)
DEFAULT_SEEDS = (11, 23, 37)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_MESH_DIR = PROJECT_ROOT / "data" / "base-meshes"
BASE_MESH_FILES = (
    "cantilever-5.0mm.msh",
    "cantilever-3.535533906mm.msh",
    "cantilever-2.5mm.msh",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def start_gmsh() -> None:
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)


def perturb_mesh(
    base_mesh: Path,
    variant_mesh: Path,
    mesh_size_mm: float,
    amplitude: float,
    seed: int,
) -> dict[str, Any]:
    variant_mesh.parent.mkdir(parents=True, exist_ok=True)
    if amplitude == 0:
        shutil.copy2(base_mesh, variant_mesh)
        return {"moved_nodes": 0, "displacement_mm": 0.0, "seed": seed}
    start_gmsh()
    try:
        gmsh.open(str(base_mesh))
        volumes = gmsh.model.getEntities(3)
        if len(volumes) != 1:
            raise RuntimeError(f"expected one volume in base mesh; got {len(volumes)}")
        volume = volumes[0][1]
        tags, coords, parametric = gmsh.model.mesh.getNodes(
            3, volume, includeBoundary=False, returnParametricCoord=True
        )
        points = np.asarray(coords, dtype=float).reshape((-1, 3))
        boundary_nodes: dict[int, np.ndarray] = {}
        for dim, entity in gmsh.model.getEntities(2):
            surface_tags, surface_xyz, _ = gmsh.model.mesh.getNodes(
                dim, entity, includeBoundary=True
            )
            surface_points = np.asarray(surface_xyz, dtype=float).reshape((-1, 3))
            boundary_nodes.update(
                (int(node), point.copy())
                for node, point in zip(surface_tags, surface_points, strict=True)
            )
        if set(map(int, tags)) & boundary_nodes.keys():
            raise RuntimeError("Gmsh classified a boundary node as volume-interior")
        parametric_points = (
            np.asarray(parametric, dtype=float).reshape((-1, 3))
            if len(parametric) == 3 * len(tags)
            else None
        )
        if not len(tags):
            raise RuntimeError("no volume-interior nodes are available for controlled perturbation")
        rng = np.random.default_rng(seed)
        displacement_mm = amplitude * mesh_size_mm
        actual_displacements = []
        for index, tag in enumerate(tags):
            direction = rng.normal(size=3)
            norm = float(np.linalg.norm(direction))
            if not math.isfinite(norm) or norm == 0:
                raise RuntimeError("random displacement direction was not finite")
            moved = points[index] + (direction / norm) * displacement_mm
            parametric_coord = [] if parametric_points is None else parametric_points[index].tolist()
            gmsh.model.mesh.setNode(int(tag), moved.tolist(), parametric_coord)
            actual_displacements.append(float(np.linalg.norm(moved - points[index])))
        all_tags, all_xyz, _ = gmsh.model.mesh.getNodes()
        after = dict(
            zip(map(int, all_tags), np.asarray(all_xyz, dtype=float).reshape((-1, 3)), strict=True)
        )
        boundary_drift = max(
            (float(np.linalg.norm(after[node] - point)) for node, point in boundary_nodes.items()),
            default=0.0,
        )
        if boundary_drift > 1e-10:
            raise RuntimeError(f"boundary nodes moved by {boundary_drift:.6g} mm")
        gmsh.write(str(variant_mesh))
        return {
            "moved_nodes": len(tags),
            "displacement_mm": displacement_mm,
            "maximum_actual_displacement_mm": max(actual_displacements, default=0.0),
            "maximum_boundary_drift_mm": boundary_drift,
            "boundary_nodes_preserved": boundary_drift <= 1e-10,
            "seed": seed,
            "parametric_coordinates_returned": len(parametric),
        }
    finally:
        gmsh.finalize()


def quality_summary(mesh_path: Path) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    start_gmsh()
    try:
        gmsh.open(str(mesh_path))
        volumes = gmsh.model.getEntities(3)
        if len(volumes) != 1:
            raise RuntimeError(f"expected one volume in mesh; got {len(volumes)}")
        interior_nodes, _, _ = gmsh.model.mesh.getNodes(
            3, volumes[0][1], includeBoundary=False
        )
        types, element_tags, blocks = gmsh.model.mesh.getElements(3, volumes[0][1])
        if list(types) != [11]:
            raise RuntimeError(f"expected only Gmsh type 11 C3D10 tetrahedra, got {types}")
        elements = np.asarray(blocks[0], dtype=np.int64).reshape((-1, 10))
        metrics: dict[str, np.ndarray] = {}
        for metric_name in ("minSICN", "minSJ", "minDetJac"):
            metrics[metric_name] = np.asarray(
                gmsh.model.mesh.getElementQualities(element_tags[0], metric_name), dtype=float
            )
            if not len(metrics[metric_name]) or not np.isfinite(metrics[metric_name]).all():
                raise RuntimeError(f"quality measure {metric_name} is empty or non-finite")
        nodes, coords, _ = gmsh.model.mesh.getNodes()
        coordinates = dict(
            zip(map(int, nodes), np.asarray(coords, dtype=float).reshape((-1, 3)), strict=True)
        )
        groups: dict[str, list[int]] = {}
        for dim, tag in gmsh.model.getPhysicalGroups(2):
            name = gmsh.model.getPhysicalName(dim, tag)
            if name in groups:
                raise RuntimeError(f"duplicate physical group name {name}")
            groups[name] = list(map(int, gmsh.model.getEntitiesForPhysicalGroup(dim, tag)))
        if set(groups) != {"FIXED_END", "LOADED_END"}:
            raise RuntimeError(f"unexpected physical groups {groups.keys()}")
        fixed_nodes: set[int] = set()
        loaded_nodes: set[int] = set()
        loaded_triangles: list[tuple[int, ...]] = []
        for name, target_nodes in (("FIXED_END", fixed_nodes), ("LOADED_END", loaded_nodes)):
            for surface in groups[name]:
                surface_nodes, _, _ = gmsh.model.mesh.getNodes(2, surface, includeBoundary=True)
                target_nodes.update(map(int, surface_nodes))
                surface_types, _, surface_blocks = gmsh.model.mesh.getElements(2, surface)
                if list(surface_types) != [9]:
                    raise RuntimeError(f"expected triangle6 boundary elements, got {surface_types}")
                if name == "LOADED_END":
                    loaded_triangles.extend(
                        tuple(map(int, row))
                        for row in np.asarray(surface_blocks[0], dtype=np.int64).reshape((-1, 6))
                    )
        if not fixed_nodes or not loaded_nodes or not loaded_triangles:
            raise RuntimeError("fixed or loaded physical group is empty")
        if fixed_nodes & loaded_nodes:
            raise RuntimeError("fixed and loaded end node sets overlap")
        if set(coordinates) != {int(n) for row in elements for n in row}:
            raise RuntimeError("mesh has orphan or missing volume nodes")
        detail = {
            name: {
                "minimum": float(np.min(values)),
                "p05": float(np.percentile(values, 5)),
                "median": float(np.percentile(values, 50)),
                "p95": float(np.percentile(values, 95)),
                "maximum": float(np.max(values)),
            }
            for name, values in metrics.items()
        }
        detail["counts"] = {
            "nodes": len(coordinates),
            "elements_c3d10": len(elements),
            "fixed_end_nodes": len(fixed_nodes),
            "loaded_end_nodes": len(loaded_nodes),
            "loaded_tri6": len(loaded_triangles),
            "interior_nodes": len(interior_nodes),
        }
        return (
            {
                "coordinates": coordinates,
                "elements": elements,
                "fixed_nodes": fixed_nodes,
                "loaded_nodes": loaded_nodes,
                "loaded_triangles": loaded_triangles,
            },
            detail,
        )
    finally:
        gmsh.finalize()


def consistent_triangle_load(
    triangle: tuple[int, ...], coordinates: dict[int, np.ndarray], traction: np.ndarray
) -> dict[int, np.ndarray]:
    corner = [coordinates[node] for node in triangle[:3]]
    area = 0.5 * float(np.linalg.norm(np.cross(corner[1] - corner[0], corner[2] - corner[0])))
    if not math.isfinite(area) or area <= 0:
        raise RuntimeError("degenerate load-surface triangle")
    quadrature = ((2 / 3, 1 / 6, 1 / 6), (1 / 6, 2 / 3, 1 / 6), (1 / 6, 1 / 6, 2 / 3))
    result = {node: np.zeros(3, dtype=float) for node in triangle}
    for l1, l2, l3 in quadrature:
        weights = (
            l1 * (2 * l1 - 1),
            l2 * (2 * l2 - 1),
            l3 * (2 * l3 - 1),
            4 * l1 * l2,
            4 * l2 * l3,
            4 * l3 * l1,
        )
        for node, weight in zip(triangle, weights, strict=True):
            result[node] += traction * area * weight / 3
    return result


def build_deck(mesh: dict[str, Any], output: Path) -> tuple[np.ndarray, np.ndarray]:
    coordinates = mesh["coordinates"]
    elements = mesh["elements"]
    force_vector = np.array([0.0, 0.0, -FORCE_N])
    traction = force_vector / (WIDTH_MM * HEIGHT_MM)
    loads: dict[int, np.ndarray] = {}
    for triangle in mesh["loaded_triangles"]:
        contribution = consistent_triangle_load(triangle, coordinates, traction)
        for node, value in contribution.items():
            loads.setdefault(node, np.zeros(3, dtype=float))
            loads[node] += value
    assembled = np.sum(list(loads.values()), axis=0)
    force_error = float(np.linalg.norm(assembled - force_vector) / FORCE_N)
    if force_error > 1e-10:
        raise RuntimeError(f"consistent traction integration failed: relative error={force_error}")

    lines = ["*HEADING", "Mesh response pilot; mm N MPa", "*NODE"]
    for node, xyz in sorted(coordinates.items()):
        lines.append(f"{node}, {xyz[0]:.15g}, {xyz[1]:.15g}, {xyz[2]:.15g}")
    lines.append("*ELEMENT, TYPE=C3D10, ELSET=EALL")
    for element_tag, row in enumerate(elements, start=1):
        ccx_row = list(map(int, row[:8])) + [int(row[9]), int(row[8])]
        lines.append(f"{element_tag}, " + ", ".join(map(str, ccx_row)))
    for name, node_set in (("FIX", mesh["fixed_nodes"]), ("TIP", mesh["loaded_nodes"])):
        lines.append(f"*NSET, NSET={name}")
        ordered = sorted(node_set)
        lines.extend(", ".join(map(str, ordered[i : i + 12])) for i in range(0, len(ordered), 12))
    lines.extend(
        [
            "*MATERIAL, NAME=MAT",
            "*ELASTIC",
            f"{YOUNGS_MODULUS_MPA:.15g}, {POISSON_RATIO:.15g}",
            "*SOLID SECTION, ELSET=EALL, MATERIAL=MAT",
            ",",
            "*STEP",
            "*STATIC",
            "*BOUNDARY",
            "FIX, 1, 3, 0.",
            "*CLOAD",
        ]
    )
    for node, vector in sorted(loads.items()):
        for dof, component in enumerate(vector, start=1):
            if abs(component) > 1e-14:
                lines.append(f"{node}, {dof}, {component:.15g}")
    lines.extend(
        [
            "*NODE PRINT, NSET=FIX",
            "RF",
            "*NODE PRINT, NSET=TIP",
            "U",
            "*END STEP",
        ]
    )
    deck_path = output / "analysis.inp"
    deck_path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return force_vector, traction


def parse_dat(path: Path) -> tuple[dict[int, np.ndarray], dict[int, np.ndarray]]:
    mode = None
    displacements: dict[int, np.ndarray] = {}
    reactions: dict[int, np.ndarray] = {}
    for line in path.read_text(encoding="ascii", errors="replace").splitlines():
        low = line.lower()
        if "displacements (vx,vy,vz)" in low and "set tip" in low:
            mode = "u"
            continue
        if "forces (fx,fy,fz)" in low and "set fix" in low:
            mode = "rf"
            continue
        if not line.strip():
            continue
        if mode is None:
            continue
        fields = line.split()
        if len(fields) != 4:
            continue
        try:
            node = int(fields[0])
            values = np.asarray([float(value.replace("D", "E")) for value in fields[1:]], dtype=float)
        except ValueError:
            continue
        if not np.isfinite(values).all():
            raise RuntimeError(f"non-finite solver value in {path}")
        target = displacements if mode == "u" else reactions
        if node in target:
            raise RuntimeError(f"duplicate node {node} in CalculiX {mode} table")
        target[node] = values
    if not displacements or not reactions:
        raise RuntimeError("CalculiX DAT file is missing tip displacements or support reactions")
    return displacements, reactions


def run_solver(
    run_dir: Path,
    mesh_path: Path,
    mesh: dict[str, Any],
    quality: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    force_vector, _ = build_deck(mesh, run_dir)
    mesh_hash = sha256(mesh_path)
    deck_hash = sha256(run_dir / "analysis.inp")
    command = shutil.which("ccx")
    if command is None:
        raise RuntimeError("CalculiX 'ccx' executable is not available on PATH")
    command_hash = sha256(Path(command))
    version_result = subprocess.run([command, "-v"], capture_output=True, text=True, timeout=10)
    solver_version = version_result.stdout + version_result.stderr
    started = time.monotonic()
    completed = subprocess.run(
        [command, "analysis"], cwd=run_dir, capture_output=True, text=True, timeout=300, check=False
    )
    (run_dir / "solver.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (run_dir / "solver.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    elapsed = time.monotonic() - started
    if completed.returncode != 0 or "Job finished" not in completed.stdout:
        raise RuntimeError(f"CalculiX failed with exit {completed.returncode}")
    displacements, reactions = parse_dat(run_dir / "analysis.dat")
    if set(displacements) != mesh["loaded_nodes"] or set(reactions) != mesh["fixed_nodes"]:
        raise RuntimeError("solver output node coverage does not match the mesh boundary sets")
    tip_displacement = np.mean(list(displacements.values()), axis=0)
    reaction = np.sum(list(reactions.values()), axis=0)
    force_residual = float(np.linalg.norm(reaction + force_vector) / FORCE_N)
    reaction_moment = sum(
        (np.cross(mesh["coordinates"][node], value) for node, value in reactions.items()),
        np.zeros(3),
    )
    applied_moment = np.cross(np.array([LENGTH_MM, WIDTH_MM / 2, HEIGHT_MM / 2]), force_vector)
    moment_scale = max(float(np.linalg.norm(applied_moment)), FORCE_N * LENGTH_MM)
    moment_residual = float(np.linalg.norm(reaction_moment + applied_moment) / moment_scale)
    displacement_mm = float(-tip_displacement[2])
    response_error = abs(displacement_mm - REFERENCE_MM) / REFERENCE_MM
    metric_summary = {name: quality[name] for name in ("minSICN", "minSJ", "minDetJac")}
    result = {
        "schema": "mesh-response-benchmark.sample/0.1",
        "sample": metadata,
        "mesh": {"sha256": mesh_hash, **quality["counts"]},
        "quality_metrics": metric_summary,
        "response": {
            "tip_deflection_mm": displacement_mm,
            "timoshenko_reference_mm": REFERENCE_MM,
            "relative_error": response_error,
            "target_relative_error": RESPONSE_TOLERANCE,
            "target_passed": response_error <= RESPONSE_TOLERANCE,
        },
        "equilibrium": {
            "reaction_force_N": reaction.tolist(),
            "force_residual_relative": force_residual,
            "reaction_moment_Nmm": reaction_moment.tolist(),
            "applied_moment_Nmm": applied_moment.tolist(),
            "moment_residual_relative": moment_residual,
            "target_relative": 0.001,
            "passed": force_residual <= 0.001 and moment_residual <= 0.001,
        },
        "execution": {
            "status": "completed",
            "solver": "CalculiX",
            "solver_version": solver_version.strip(),
            "solver_executable_sha256": command_hash,
            "runtime_seconds": elapsed,
            "exit_code": completed.returncode,
            "stdout_sha256": sha256(run_dir / "solver.stdout.txt"),
            "stderr_sha256": sha256(run_dir / "solver.stderr.txt"),
        },
        "input_sha256": {"mesh": mesh_hash, "calculix_deck": deck_hash},
    }
    if quality["minSICN"]["minimum"] <= 0 or quality["minSJ"]["minimum"] <= 0 or quality["minDetJac"]["minimum"] <= 0:
        result["mesh"]["valid"] = False
    else:
        result["mesh"]["valid"] = True
    write_json(run_dir / "result.json", result)
    return result


def average_ranks(values: list[float]) -> np.ndarray:
    values_array = np.asarray(values, dtype=float)
    order = np.argsort(values_array, kind="mergesort")
    ranks = np.empty(len(values_array), dtype=float)
    index = 0
    while index < len(order):
        end = index + 1
        while end < len(order) and values_array[order[end]] == values_array[order[index]]:
            end += 1
        rank = (index + 1 + end) / 2
        ranks[order[index:end]] = rank
        index = end
    return ranks


def spearman(values_x: list[float], values_y: list[float]) -> float | None:
    if len(values_x) != len(values_y) or len(values_x) < 3:
        return None
    ranks_x = average_ranks(values_x)
    ranks_y = average_ranks(values_y)
    if np.std(ranks_x) == 0 or np.std(ranks_y) == 0:
        return None
    return float(np.corrcoef(ranks_x, ranks_y)[0, 1])


def summarize(results: list[dict[str, Any]], expected: int) -> dict[str, Any]:
    solved = [r for r in results if r.get("execution", {}).get("status") == "completed"]
    invalid_meshes = [r for r in results if r.get("execution", {}).get("status") == "invalid_mesh"]
    analysable = [r for r in solved if r.get("equilibrium", {}).get("passed") is True]
    errors = [float(r["response"]["relative_error"]) for r in analysable]
    statuses = [r.get("execution", {}).get("status") for r in results]
    all_samples_accounted = len(results) == expected and all(
        status in {"completed", "invalid_mesh"} for status in statuses
    )
    summary: dict[str, Any] = {
        "schema": "mesh-response-benchmark.study/0.1",
        "execution_status": "completed" if all_samples_accounted else "incomplete",
        "expected_samples": expected,
        "recorded_samples": len(results),
        "completed_samples": len(solved),
        "equilibrium_passed_samples": len(analysable),
        "excluded_from_metric_error_analysis": len(solved) - len(analysable),
        "invalid_mesh_samples": len(invalid_meshes),
        "solver_failed_samples": len(results) - len(solved) - len(invalid_meshes),
        "response_error_failures": sum(
            not bool(r["response"]["target_passed"]) for r in analysable
        ),
        "response_error_tolerance": RESPONSE_TOLERANCE,
        "samples": results,
        "descriptive_spearman_by_metric": {},
        "minSICN_threshold_counts": {},
        "interpretation_limit": "Designed one-case sample only; no result generalizes to other geometries or workflows.",
    }
    for key in ("minimum", "p05", "median"):
        for metric_name in ("minSICN", "minSJ", "minDetJac"):
            x = [float(r["quality_metrics"][metric_name][key]) for r in analysable]
            summary["descriptive_spearman_by_metric"][f"{metric_name}_{key}"] = spearman(x, errors)
    for threshold in QUALITY_THRESHOLDS:
        false_safe = false_reject = 0
        for r in analysable:
            quality_pass = float(r["quality_metrics"]["minSICN"]["minimum"]) >= threshold
            response_pass = bool(r["response"]["target_passed"])
            false_safe += int(quality_pass and not response_pass)
            false_reject += int(not quality_pass and response_pass)
        summary["minSICN_threshold_counts"][str(threshold)] = {
            "threshold_is_project_probe_not_standard": True,
            "solved_samples": len(analysable),
            "false_safe": false_safe,
            "false_reject": false_reject,
        }
    summary["study_status"] = (
        "complete_for_declared_case"
        if all_samples_accounted and len(analysable) == len(solved)
        else "incomplete"
    )
    return summary


def markdown_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Mesh response pilot report",
        "",
        f"**Study status:** {summary['study_status']}",
        "",
        "This report is limited to one idealized linear-elastic cantilever, Gmsh, C3D10 elements, and CalculiX. It is not a general mesh acceptance rule or a design validation.",
        "",
    ]
    lines.extend([
        "## Attempt accounting",
        "",
        f"- Planned and recorded attempts: {summary['expected_samples']} / {summary['recorded_samples']}",
        f"- Solver-completed samples: {summary['completed_samples']}",
        f"- Equilibrium checks passed: {summary['equilibrium_passed_samples']}",
        f"- Invalid meshes retained without solving: {summary['invalid_mesh_samples']}",
        f"- Solver or unclassified failures: {summary['solver_failed_samples']}",
        f"- Responses above the 2% project target: {summary['response_error_failures']}",
        "",
    ])
    lines.extend([
        "## Samples",
        "",
        "| Size (mm) | Distortion | Seed | Elements | Min SICN | Tip error (%) | Force residual | Moment residual | Status |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ])
    for result in summary["samples"]:
        if result.get("execution", {}).get("status") != "completed":
            lines.append(
                f"| {result['sample']['mesh_size_mm']:.4g} | {result['sample']['amplitude_fraction_h']:.3g} | {result['sample']['seed']} | — | — | — | — | — | {result['execution']['status']} |"
            )
            continue
        lines.append(
            "| {size:.4g} | {amp:.3g} | {seed} | {elements} | {quality:.5f} | {error:.4f} | {force:.3e} | {moment:.3e} | completed |".format(
                size=result["sample"]["mesh_size_mm"],
                amp=result["sample"]["amplitude_fraction_h"],
                seed=result["sample"]["seed"],
                elements=result["mesh"]["elements_c3d10"],
                quality=result["quality_metrics"]["minSICN"]["minimum"],
                error=100 * result["response"]["relative_error"],
                force=result["equilibrium"]["force_residual_relative"],
                moment=result["equilibrium"]["moment_residual_relative"],
            )
        )
    lines.extend(["", "## Fixed threshold probes", "", "| minSICN minimum | False safe | False reject | Solved samples |", "|---:|---:|---:|---:|"])
    for threshold, counts in summary["minSICN_threshold_counts"].items():
        lines.append(
            f"| {float(threshold):.2f} | {counts['false_safe']} | {counts['false_reject']} | {counts['solved_samples']} |"
        )
    lines.extend(
        [
            "",
            "These threshold values are project probes, not universal engineering limits. Correlations are descriptive and do not support generalization beyond the declared case.",
            "",
        ]
    )
    if summary["completed_samples"] > 0 and summary["response_error_failures"] == 0:
        lines.extend([
            "All solver-completed samples met the 2% response target. Therefore, zero false-safe cases do not show that any minSICN threshold detects unacceptable response error; this sample did not contain a response failure to detect.",
            "",
        ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    smoke = parser.add_mutually_exclusive_group()
    smoke.add_argument("--smoke", action="store_true", help="run only the 5 mm undistorted baseline")
    smoke.add_argument(
        "--smoke-distortion",
        action="store_true",
        help="run only one 5 mm mesh with 0.01h interior-node perturbation",
    )
    args = parser.parse_args()
    manifest = json.loads((BASE_MESH_DIR / "manifest.json").read_text(encoding="utf-8"))
    manifest_by_file = {item["file"]: item for item in manifest["meshes"]}
    mesh_specs = [
        (DEFAULT_SIZES_MM[index], BASE_MESH_DIR / filename, manifest_by_file[filename])
        for index, filename in enumerate(BASE_MESH_FILES)
    ]
    if args.smoke:
        mesh_specs = mesh_specs[:1]
        amplitudes = (0.0,)
        seeds = (DEFAULT_SEEDS[0],)
    elif args.smoke_distortion:
        mesh_specs = mesh_specs[:1]
        amplitudes = (DEFAULT_AMPLITUDES[-1],)
        seeds = (DEFAULT_SEEDS[0],)
    else:
        amplitudes = DEFAULT_AMPLITUDES
        seeds = DEFAULT_SEEDS
    for _, source_mesh, source_record in mesh_specs:
        if not source_mesh.is_file() or sha256(source_mesh) != source_record["sha256"]:
            parser.error(f"baseline mesh missing or hash mismatch: {source_mesh}")
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    mesh_sizes = [size for size, _, _ in mesh_specs]
    samples = []
    expected = sum(
        1 if amplitude == 0 else len(seeds)
        for _ in mesh_specs
        for amplitude in amplitudes
    )
    solver_command = shutil.which("ccx")
    if solver_command is None:
        parser.error("CalculiX 'ccx' executable is not available on PATH")
    solver_version_result = subprocess.run(
        [solver_command, "-v"], capture_output=True, text=True, timeout=10
    )
    solver_version = (solver_version_result.stdout + solver_version_result.stderr).strip()
    protocol = {
        "schema": "mesh-response-benchmark.protocol/0.1",
        "case": {
            "geometry_mm": {"length": LENGTH_MM, "width": WIDTH_MM, "height": HEIGHT_MM},
            "youngs_modulus_MPa": YOUNGS_MODULUS_MPA,
            "poisson_ratio": POISSON_RATIO,
            "total_end_load_N": [0, 0, -FORCE_N],
            "element_family": "C3D10",
            "reference": "Timoshenko beam estimate",
            "reference_tip_deflection_mm": REFERENCE_MM,
        },
        "toolchain": {
            "gmsh": gmsh.__version__,
            "numpy": np.__version__,
            "solver": "CalculiX",
            "solver_version": solver_version,
        },
        "mesh_sizes_mm": mesh_sizes,
        "base_mesh_inputs": [
            {
                "path": f"data/base-meshes/{record['file']}",
                "sha256": record["sha256"],
                "elements_c3d10": record["elements_c3d10"],
            }
            for _, _, record in mesh_specs
        ],
        "distortion_amplitudes_fraction_h": amplitudes,
        "seeds_for_nonzero_amplitudes": seeds,
        "expected_sample_count": expected,
        "primary_metric": "Gmsh minSICN minimum",
        "secondary_metrics": ["Gmsh minSJ", "Gmsh minDetJac"],
        "metric_threshold_probes": list(QUALITY_THRESHOLDS),
        "response_error_definition": "abs(FEA - Timoshenko) / abs(Timoshenko)",
        "response_error_limit": RESPONSE_TOLERANCE,
        "distortion_scope": "move only Gmsh nodes classified on the solid volume; preserve CAD-boundary nodes",
        "thresholds_are_project_probes_not_industry_standards": True,
    }
    write_json(out / "protocol.json", protocol)
    protocol_hash = sha256(out / "protocol.json")
    protocol_document_hash = sha256(
        Path(__file__).resolve().parents[1] / "docs" / "protocol-v0.1.md"
    )
    baseline_manifest_hash = sha256(BASE_MESH_DIR / "manifest.json")
    runner_hash = sha256(Path(__file__).resolve())
    for size, source_mesh, source_record in mesh_specs:
        base_dir = out / f"base-{size:.8g}mm"
        base_dir.mkdir()
        base_mesh = base_dir / "base.msh"
        shutil.copy2(source_mesh, base_mesh)
        _, base_quality = quality_summary(base_mesh)
        for amplitude in amplitudes:
            sample_seeds = [seeds[0]] if amplitude == 0 else seeds
            for seed in sample_seeds:
                sample_id = f"h{size:.8g}-a{amplitude:.4g}-s{seed}"
                run_dir = out / sample_id
                run_dir.mkdir()
                mesh_path = run_dir / "mesh.msh"
                perturbation = perturb_mesh(base_mesh, mesh_path, size, amplitude, seed)
                metadata = {
                    "sample_id": sample_id,
                    "mesh_size_mm": size,
                    "amplitude_fraction_h": amplitude,
                    "seed": seed,
                    "perturbation": perturbation,
                    "base_mesh_sha256": source_record["sha256"],
                }
                try:
                    mesh, quality = quality_summary(mesh_path)
                    metadata["quality_metrics"] = {
                        name: quality[name] for name in ("minSICN", "minSJ", "minDetJac")
                    }
                    metadata["mesh_counts"] = quality["counts"]
                    metadata["mesh_interior_node_count"] = base_quality["counts"]["interior_nodes"]
                    metadata["mesh_validity"] = all(
                        quality[name]["minimum"] > 0
                        for name in ("minSICN", "minSJ", "minDetJac")
                    )
                    if not metadata["mesh_validity"]:
                        result = {
                            "schema": "mesh-response-benchmark.sample/0.1",
                            "sample": metadata,
                            "mesh_quality": {
                                name: quality[name]
                                for name in ("minSICN", "minSJ", "minDetJac")
                            },
                            "execution": {"status": "invalid_mesh", "solver": "not_run"},
                        }
                        write_json(run_dir / "result.json", result)
                    else:
                        result = run_solver(run_dir, mesh_path, mesh, quality, metadata)
                except Exception as exc:
                    result = {
                        "schema": "mesh-response-benchmark.sample/0.1",
                        "sample": metadata,
                        "execution": {"status": "failed", "error": f"{type(exc).__name__}: {exc}"},
                    }
                    write_json(run_dir / "result.json", result)
                samples.append(result)
                print(f"{sample_id}: {result.get('execution', {}).get('status')}", flush=True)
    summary = summarize(samples, expected)
    summary["protocol_sha256"] = protocol_hash
    summary["protocol_document_sha256"] = protocol_document_hash
    summary["baseline_manifest_sha256"] = baseline_manifest_hash
    summary["runner_sha256"] = runner_hash
    if args.smoke or args.smoke_distortion:
        summary["study_status"] = "smoke_only"
        summary["study_complete_for_protocol"] = False
        summary["smoke_scope"] = "single baseline sample" if args.smoke else "single distorted sample"
    write_json(out / "benchmark.json", summary)
    (out / "report.md").write_text(markdown_report(summary), encoding="utf-8")
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "study_status",
                    "execution_status",
                    "expected_samples",
                    "recorded_samples",
                    "completed_samples",
                    "invalid_mesh_samples",
                    "solver_failed_samples",
                    "minSICN_threshold_counts",
                )
            },
            indent=2,
        )
    )
    return 0 if summary["study_status"] in ("complete_for_declared_case", "smoke_only") else 2


if __name__ == "__main__":
    raise SystemExit(main())
