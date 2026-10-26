"""Bracket verification and equal-resultant thickness studies with retained evidence."""

from __future__ import annotations

import importlib.metadata
import math
import platform
from pathlib import Path

import numpy as np

from .bracket import prepare_bracket_mesh
from .contracts import MountingBracketGeometry, ProblemSpec, Quantity, validate_problem
from .solver import read_mesh, sha256, solve, write_json
from .units import canonical_problem_si, to_si, validate_problem_units

SOURCE_SNAPSHOT = {p.name: p.read_bytes() for p in Path(__file__).parent.glob("*.py")}


def run_bracket(problem: ProblemSpec, out: Path):
    validate_problem_units(problem)
    if not isinstance(problem.geometry, MountingBracketGeometry):
        raise ValueError("this workflow supports mounting_bracket geometry only")
    data = canonical_problem_si(problem)
    g = data["geometry"]
    length, width, thickness, radius = (
        g[key]["value"] * 1000 for key in ("base_length", "width", "thickness", "root_radius")
    )
    roi = (0.55 * length, 0.75 * length, 0.2 * width, 0.8 * width)
    if thickness + radius >= roi[0]:
        raise ValueError("bracket root overlaps predefined regular stress ROI")
    out.mkdir(parents=True, exist_ok=False)
    (out / "source").mkdir()
    for name, contents in SOURCE_SNAPSHOT.items():
        (out / "source" / name).write_bytes(contents)
    write_json(
        out / "environment.json",
        {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {
                name: importlib.metadata.version(name)
                for name in ("cadquery", "gmsh", "numpy", "pint", "pydantic")
            },
        },
    )
    write_json(out / "input.json", problem.model_dump(mode="json"))
    write_json(out / "canonical.json", data)
    write_json(
        out / "verification-policy.json",
        {
            "roi_xy_mm": roi,
            "roi_selection": "element centroid; includes full base thickness",
            "roi_is_not_whole_part_strength_assessment": True,
            "max_displacement_over_thickness_screen": 0.05,
            "max_principal_elastic_strain_screen": 0.01,
            "CAD_mesh_volume_relative_tolerance": 0.005,
        },
    )
    try:
        preparation = prepare_bracket_mesh(problem, out / "geometry", partition_stress_roi=True)
        write_json(out / "preparation.json", preparation)
        mesh = read_mesh(out / "geometry/bracket.msh", "MOUNT_FACE", "LOADED_PAD")
        if mesh.quality["minimum_minsicn"] < problem.mesh.minimum_minsicn:
            raise ValueError("mesh violates requested quality threshold")
        direction = np.array(problem.loads[0].direction, dtype=float)
        direction /= np.linalg.norm(direction)
        traction = direction * to_si(problem.loads[0].magnitude, "pascal") / 1e6
        result = solve(
            mesh,
            to_si(problem.material.youngs_modulus, "pascal") / 1e6,
            problem.material.poisson_ratio,
            traction,
            out / "solver",
            roi,
        )
        volume = preparation["geometry"]["volume_mm3"]
        height = g["height"]["value"] * 1000
        analytic_volume = width * (
            length * thickness + height * thickness - thickness**2 + (1 - math.pi / 4) * radius**2
        )
        volume_error = abs(sum(mesh.volumes.values()) - volume) / volume
        area_expected = preparation["regions"]["loaded_pad"]["area_mm2"]
        area_error = abs(result["load"]["area_mm2"] - area_expected) / area_expected
        result["checks"].update(
            {
                "cad_mesh_volume": volume_error <= 0.005,
                "cad_load_area": area_error <= 1e-8,
                "analytic_cad_volume": abs(volume - analytic_volume) / analytic_volume <= 1e-8,
            }
        )
        result["cad_mesh_volume_error"] = volume_error
        result["cad_load_area_error"] = area_error
        result["mass_kg"] = (
            volume * 1e-9 * to_si(problem.material.density, "kg/m^3")
            if problem.material.density
            else None
        )
        result["applicability_screen"] = {
            "max_displacement_over_thickness": result["result"]["maximum_nodal_displacement_mm"]
            / thickness,
            "passed": (
                result["result"]["maximum_nodal_displacement_mm"] / thickness <= 0.05
                and result["stress"]["maximum_absolute_principal_elastic_strain"] <= 0.01
            ),
            "meaning": (
                "kinematic screening only; does not establish elastic strength or physical validity"
            ),
        }
        if not all(result["checks"].values()) or not result["applicability_screen"]["passed"]:
            result["numerical_status"] = "failed"
        result["source_hashes"] = {p.name: sha256(p) for p in (out / "source").glob("*.py")}
        result["input_sha256"] = sha256(out / "input.json")
        write_json(out / "result.json", result)
        return result
    except Exception as exc:
        write_json(out / "failure.json", {"execution_status": "failed", "error": str(exc)})
        raise


def convergence(values, tolerance):
    values = np.asarray(values, dtype=float)
    if len(values) < 3 or not np.isfinite(values).all() or np.any(values <= 0):
        return {"status": "incomplete", "reason": "need three positive finite quantities"}
    differences = np.diff(values)
    relative = np.abs(differences) / values[1:]
    monotonic = differences[-1] * differences[-2] >= 0
    decreasing = abs(differences[-1]) <= abs(differences[-2]) + 1e-12 * max(values)
    passed = relative[-1] <= tolerance and monotonic and decreasing
    return {
        "status": "passed" if passed else "incomplete",
        "relative_changes": relative.tolist(),
        "monotonic": bool(monotonic),
        "decreasing_increments": bool(decreasing),
        "tolerance": tolerance,
    }


def aggregate_numerical_status(statuses):
    """Preserve failures and never treat an empty or partial study as passed."""
    statuses = list(statuses)
    if "failed" in statuses:
        return "failed"
    return "passed" if statuses and all(s == "passed" for s in statuses) else "incomplete"


def verify_bracket(problem: ProblemSpec, out: Path, *, progress=None):
    out.mkdir(parents=True, exist_ok=False)
    size = to_si(problem.mesh.size, "meter")
    policy = {
        "mesh_sizes_m": [size, size / math.sqrt(2), size / 2],
        "displacement_change_tolerance": 0.02,
        "stress_change_tolerance": 0.05,
        "roi_volume_error_tolerance": 0.05,
        "trend_required": "monotonic with decreasing increments",
        "stress_scope": "predeclared regular-region RMS; global peak is reported but not certified",
    }
    write_json(out / "study-policy.json", policy)
    records = []
    for index, mesh_size in enumerate(policy["mesh_sizes_m"]):
        data = problem.model_dump(mode="json")
        data["mesh"]["size"] = {"value": mesh_size, "unit": "m"}
        result = run_bracket(validate_problem(data), out / f"mesh-{index}")
        records.append(result)
        if progress:
            progress(index, result)
    displacement = convergence(
        [abs(r["result"]["area_mean_loaded_displacement_mm"][2]) for r in records], 0.02
    )
    stress = convergence([r["stress"]["roi_rms_von_mises_MPa"] for r in records], 0.05)
    geometry = problem.geometry
    expected_roi_volume = (
        0.2
        * to_si(geometry.base_length, "m")
        * 1000
        * 0.6
        * to_si(geometry.width, "m")
        * 1000
        * to_si(geometry.thickness, "m")
        * 1000
    )
    roi_errors = [
        abs(r["stress"]["roi_volume_mm3"] - expected_roi_volume) / expected_roi_volume
        for r in records
    ]
    all_checks = all(
        all(r["checks"].values()) and r["applicability_screen"]["passed"] for r in records
    )
    passed = (
        all_checks
        and displacement["status"] == stress["status"] == "passed"
        and max(roi_errors) <= 0.05
    )
    summary = {
        "execution_status": "completed",
        "numerical_status": "passed" if passed else "incomplete" if all_checks else "failed",
        "verification_scope": (
            "equilibrium, geometry, displacement and regular-region stress mesh sensitivity"
        ),
        "design_status": "unassessed",
        "physical_validation": "not_performed",
        "displacement_convergence": displacement,
        "stress_convergence": stress,
        "roi_volume_relative_errors": roi_errors,
        "global_peak_stress_convergence": "not_assessed; possible clamp singularity",
        "runs": records,
    }
    write_json(out / "verification.json", summary)
    return summary


def compare_brackets(
    problem: ProblemSpec, thicknesses_mm: list[float], out: Path, *, progress=None
):
    validate_problem_units(problem)
    if not isinstance(problem.geometry, MountingBracketGeometry):
        raise ValueError("comparison requires mounting_bracket")
    if len(set(thicknesses_mm)) != len(thicknesses_mm) or not thicknesses_mm:
        raise ValueError("thickness candidates must be nonempty and unique")
    g = problem.geometry
    length, width, thickness, radius = (
        to_si(getattr(g, key), "m") * 1000
        for key in ("base_length", "width", "thickness", "root_radius")
    )
    force = to_si(problem.loads[0].magnitude, "Pa") / 1e6 * (length - thickness - radius) * width
    candidates = []
    for value in thicknesses_mm:
        quantity = Quantity(value=value, unit="mm")
        data = problem.model_dump(mode="json")
        data["geometry"]["thickness"] = quantity.model_dump()
        area = (length - value - radius) * width
        if area <= 0:
            raise ValueError("candidate leaves no load face")
        data["loads"][0]["magnitude"] = {"value": force / area, "unit": "MPa"}
        candidate = validate_problem(data)
        validate_problem_units(candidate)
        candidates.append(candidate)
    out.mkdir(parents=True, exist_ok=False)
    write_json(
        out / "comparison-policy.json",
        {
            "total_force_N": force,
            "source": "resultant of supplied baseline traction and face area",
            "thicknesses_mm": thicknesses_mm,
            "load_policy": (
                "constant total force; candidate traction deliberately adjusted to its area"
            ),
            "assessment": "no winning design without supplied criteria and whole-part assessment",
        },
    )
    records = []
    for index, candidate in enumerate(candidates):
        if progress:
            progress(f"candidate {index + 1}/{len(candidates)}: {thicknesses_mm[index]} mm")
        verification = verify_bracket(
            candidate,
            out / f"candidate-{index}",
            progress=(lambda i, r: progress(f"mesh {i + 1}/3: {r['mesh']['elements']} elements"))
            if progress
            else None,
        )
        records.append({"thickness_mm": thicknesses_mm[index], "verification": verification})
        write_json(out / "comparison-progress.json", records)
    summary = {
        "execution_status": "completed",
        "design_status": "unassessed",
        "winner": None,
        "numerical_status": aggregate_numerical_status(
            r["verification"]["numerical_status"] for r in records
        ),
        "total_force_N": force,
        "candidates": records,
    }
    write_json(out / "comparison.json", summary)
    from .reporting import write_comparison_report

    write_comparison_report(out, summary)
    return summary
