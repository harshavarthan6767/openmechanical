"""Replay a retained bracket in canonical SI and compare actual solver outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from openmechanical.contracts import validate_problem
from openmechanical.solver import sha256, write_json
from openmechanical.verification import run_bracket


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    baseline = json.loads((args.baseline / "result.json").read_text())
    problem = validate_problem(json.loads((args.baseline / "canonical.json").read_text()))
    result = run_bracket(problem, args.out.resolve())
    checks = {}
    for name in ("area_mean_loaded_displacement_mm", "maximum_nodal_displacement_mm"):
        checks[name] = bool(
            np.allclose(result["result"][name], baseline["result"][name], rtol=1e-6, atol=1e-10)
        )
    for name in ("roi_rms_von_mises_MPa", "raw_peak_von_mises_MPa"):
        checks[name] = bool(
            np.isclose(result["stress"][name], baseline["stress"][name], rtol=1e-6, atol=1e-10)
        )
    checks["force_resultant"] = bool(
        np.allclose(result["load"]["force_N"], baseline["load"]["force_N"], rtol=1e-10, atol=1e-10)
    )
    checks["mesh_counts"] = all(
        result["mesh"][key] == baseline["mesh"][key] for key in ("nodes", "elements")
    )
    checks["solver_checks"] = all(result["checks"].values()) and all(baseline["checks"].values())
    summary = {
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "baseline_result_sha256": sha256(args.baseline / "result.json"),
        "SI_input_sha256": sha256(args.baseline / "canonical.json"),
        "metric_relative_tolerance": 1e-6,
        "metric_absolute_tolerance": 1e-10,
    }
    write_json(args.out.resolve() / "unit-equivalence.json", summary)
    print(json.dumps(summary, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
