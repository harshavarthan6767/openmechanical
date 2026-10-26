"""Three-mesh analytical benchmark of the actual installed solver workflow."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=False)
    fixture = Path(__file__).with_name("problem.json").read_bytes()
    fixture_hash = hashlib.sha256(fixture).hexdigest()
    if fixture_hash != "b76b96275ce3fcebbc27d491cd178184bbdb6ef943ab76337de2817cdeca4a88":
        raise ValueError(
            "benchmark fixture changed; review the independent reference before running"
        )
    original = json.loads(fixture)
    # Independent analytical calculation for this fixed benchmark, in SI.
    length, width, height = 0.2, 0.02, 0.01
    youngs, poisson, load = 210e9, 0.3, 100.0
    area = width * height
    inertia = width * height**3 / 12
    shear_modulus = youngs / (2 * (1 + poisson))
    euler_mm = load * length**3 / (3 * youngs * inertia) * 1000
    reference_mm = euler_mm + load * length / ((5 / 6) * shear_modulus * area) * 1000
    policy = {
        "analytical_deflection_relative_error_max": 0.02,
        "force_balance_relative_error_max": 0.001,
        "moment_balance_relative_error_max": 0.001,
        "final_displacement_change_relative_max": 0.02,
        "mesh_sizes_mm": [5.0, 5.0 / math.sqrt(2), 2.5],
        "reference": "Timoshenko tip deflection, rectangular beam, shear factor 5/6",
        "euler_bernoulli_mm": euler_mm,
        "reference_mm": reference_mm,
        "scope": "displacement and equilibrium only; stress convergence is not assessed",
    }
    (root / "policy.json").write_text(json.dumps(policy, indent=2) + "\n")
    rows = []
    for index, size in enumerate(policy["mesh_sizes_mm"]):
        spec = copy.deepcopy(original)
        spec["mesh"]["size"] = {"value": size, "unit": "mm"}
        spec_path = root / f"input-{index}.json"
        spec_path.write_text(json.dumps(spec, indent=2) + "\n")
        command = [
            sys.executable,
            "-m",
            "openmechanical.cli",
            "run",
            str(spec_path),
            "--out",
            str(root / f"mesh-{index}"),
            "--json",
        ]
        process = subprocess.run(command, capture_output=True, text=True, timeout=600)
        (root / f"cli-{index}.stdout.txt").write_text(process.stdout)
        (root / f"cli-{index}.stderr.txt").write_text(process.stderr)
        if process.returncode != 0:
            raise RuntimeError(f"mesh {index} failed; see retained CLI logs in {root}")
        result = json.loads(process.stdout)
        displacement = -result["result"]["mean_tip_displacement_mm"][2]
        verification = result["verification"]
        row = {
            "mesh_size_mm": size,
            "nodes": result["mesh"]["nodes"],
            "elements": result["mesh"]["elements_c3d10"],
            "tip_deflection_mm": displacement,
            "analytical_error_relative": abs(displacement - reference_mm) / reference_mm,
            "force_residual_relative": verification["force_equilibrium_relative_error"],
            "moment_residual_relative": verification["moment_equilibrium_relative_error"],
            "evidence": f"mesh-{index}/m0_summary.json",
        }
        if rows:
            row["change_from_previous_relative"] = abs(
                displacement - rows[-1]["tip_deflection_mm"]
            ) / abs(displacement)
        rows.append(row)
        print(json.dumps(row), flush=True)

    changes = [rows[i]["tip_deflection_mm"] - rows[i - 1]["tip_deflection_mm"] for i in (1, 2)]
    trend_consistent = changes[0] * changes[1] >= 0 and abs(changes[1]) <= abs(changes[0])
    checks = {
        "analytical_deflection": all(r["analytical_error_relative"] <= 0.02 for r in rows),
        "force_balance": all(r["force_residual_relative"] <= 0.001 for r in rows),
        "moment_balance": all(r["moment_residual_relative"] <= 0.001 for r in rows),
        "displacement_mesh_sensitivity": rows[-1]["change_from_previous_relative"] <= 0.02,
        "monotonic_decreasing_increments": trend_consistent,
    }
    result = {
        "benchmark_status": "passed" if all(checks.values()) else "failed_or_inconclusive",
        "scope": policy["scope"],
        "full_verification_status": "incomplete",
        "stress_convergence": "not_run",
        "bracket_solver_benchmark": "not_run",
        "physical_validation": "not_performed",
        "policy": policy,
        "checks": checks,
        "runs": rows,
    }
    (root / "benchmark.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    report = [
        "# Cantilever analytical benchmark",
        "",
        f"Result: **{result['benchmark_status']}** for displacement and equilibrium.",
        "",
        f"Reference: {reference_mm:.9f} mm (Timoshenko); {euler_mm:.9f} mm (Euler-Bernoulli).",
        "",
        "| Mesh size (mm) | Elements | Tip deflection (mm) | Reference error "
        "| Force residual | Moment residual |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        report.append(
            f"| {row['mesh_size_mm']:.4f} | {row['elements']} | {row['tip_deflection_mm']:.9f} "
            f"| {100 * row['analytical_error_relative']:.4f}% "
            f"| {row['force_residual_relative']:.3g} "
            f"| {row['moment_residual_relative']:.3g} |"
        )
    report += [
        "",
        f"Final displacement change: {100 * rows[-1]['change_from_previous_relative']:.5f}%.",
        f"Monotonic refinement with decreasing increments: {trend_consistent}.",
        "",
        "The 200 x 20 x 10 mm beam uses E=210 GPa, nu=0.3, and a 100 N distributed end load.",
        "The clamp fixes the entire end face. The comparison quantity is the arithmetic mean "
        "of loaded-end nodal Z displacements.",
        "The beam estimate does not exactly reproduce the 3D clamp and end-face effects; "
        "refinement need not drive the difference to zero.",
        "",
        "Stress convergence, bracket FEA, and physical validation remain unassessed. "
        "This benchmark does not establish a safe bracket design.",
    ]
    (root / "report.md").write_text("\n".join(report) + "\n")
    print(json.dumps({"benchmark_status": result["benchmark_status"], "checks": checks}))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
