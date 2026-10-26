#!/usr/bin/env python3
"""Compare a Foundation v14 backward-step run with NASA TMR reference data."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path


NASA_REATTACHMENT = 6.26
NASA_REATTACHMENT_UNCERTAINTY = 0.10
PROFILE_STATIONS = (-4, 1, 4, 6, 10)


def numeric_rows(path: Path) -> list[list[float]]:
    rows: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("(") or line.startswith(")"):
            continue
        values = re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", line)
        if values:
            try:
                row = [float(value) for value in values]
            except ValueError:
                continue
            if all(math.isfinite(value) for value in row):
                rows.append(row)
    return rows


def parse_experimental_profiles(path: Path) -> dict[int, list[tuple[float, float]]]:
    profiles: dict[int, list[tuple[float, float]]] = {}
    station: int | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        header = re.search(r"x/H\s*=\s*(-?\d+)", line)
        if header:
            station = int(header.group(1))
            profiles[station] = []
            continue
        if station is None or not line.strip() or line.lstrip().startswith(("#", "variables", "zone")):
            continue
        row = numeric_rows_from_line(line)
        if len(row) >= 4:
            # TMR columns are ID, y/H, u/Uref, v/Uref, ...
            # TMR's y/H origin is the downstream floor; this case places that
            # floor at model y/H=-1, so every experimental station shifts by -1.
            y = row[1] - 1.0
            profiles[station].append((y, row[2]))
    return profiles


def numeric_rows_from_line(line: str) -> list[float]:
    try:
        return [float(value) for value in line.split()]
    except ValueError:
        return []


def graph_file(run_dir: Path, object_name: str) -> Path | None:
    candidates = list((run_dir / "case" / "postProcessing" / object_name).glob("*/line.xy"))
    candidates.sort(key=lambda path: float(path.parent.name))
    return candidates[-1] if candidates else None


def flow_rate(run_dir: Path, object_name: str) -> tuple[float, Path] | None:
    candidates = list(
        (run_dir / "case" / "postProcessing" / object_name).glob("*/surfaceFieldValue.dat")
    )
    candidates.sort(key=lambda path: float(path.parent.name))
    if not candidates:
        return None
    rows = numeric_rows(candidates[-1])
    if not rows or len(rows[-1]) < 2:
        return None
    return rows[-1][1], candidates[-1]


def interpolate(points: list[tuple[float, float]], x: float) -> float | None:
    points = sorted(points)
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return y0
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return None


def zero_crossings(points: list[tuple[float, float]]) -> list[dict[str, float | str]]:
    points = sorted(points)
    result: list[dict[str, float | str]] = []
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if y0 * y1 < 0 and x1 != x0:
            direction = "negative_to_positive" if y0 < 0 < y1 else "positive_to_negative"
            result.append(
                {
                    "x_over_H": x0 - y0 * (x1 - x0) / (y1 - y0),
                    "direction": direction,
                }
            )
    return result


def profile_rmse(predicted: list[tuple[float, float]], reference: list[tuple[float, float]]) -> dict[str, float | int] | None:
    pairs = []
    for y, u_ref in reference:
        u_model = interpolate(predicted, y)
        if u_model is not None:
            pairs.append((u_model, u_ref))
    if not pairs:
        return None
    mse = sum((model - ref) ** 2 for model, ref in pairs) / len(pairs)
    return {"n": len(pairs), "rmse_u_over_uref": math.sqrt(mse)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    solver_logs = [
        path
        for path in (
            args.run_dir / "log.foamRun",
            args.run_dir / "log.foamRun.continuation",
            args.run_dir / "log.foamRun.extended",
        )
        if path.exists()
    ]
    log_text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in solver_logs)
    solver_log_names = [path.name for path in solver_logs]
    converged = "SIMPLE solution converged" in log_text
    check_mesh_log = (args.run_dir / "log.checkMesh").read_text(encoding="utf-8", errors="replace")
    mesh_ok = "Mesh OK" in check_mesh_log
    profiles_exp = parse_experimental_profiles(args.reference_dir / "profiles.exp.dat")

    checks: list[dict[str, object]] = [
        {"name": "mesh_check", "status": "passed" if mesh_ok else "failed", "evidence": "log.checkMesh"},
        {
            "name": "simple_residual_convergence",
            "status": "passed" if converged else "incomplete",
            "evidence": solver_log_names or None,
            "criterion": "Foundation v14 reports SIMPLE solution converged using system/fvSolution residualControl",
        },
    ]

    inlet_flow = flow_rate(args.run_dir, "inletFlowRate")
    outlet_flow = flow_rate(args.run_dir, "outletFlowRate")
    if inlet_flow and outlet_flow and abs(inlet_flow[0]) > 0:
        mass_imbalance_pct = 100.0 * abs(abs(inlet_flow[0]) - abs(outlet_flow[0])) / abs(inlet_flow[0])
        checks.append(
            {
                "name": "inlet_outlet_mass_balance",
                "status": "passed" if mass_imbalance_pct <= 0.1 else "failed",
                "metric_percent": mass_imbalance_pct,
                "threshold_percent": 0.1,
                "threshold_basis": "project pilot acceptance target; constant density makes relative volumetric-flux imbalance equal mass-flow imbalance",
                "inlet_evidence": inlet_flow[1].relative_to(args.run_dir).as_posix(),
                "outlet_evidence": outlet_flow[1].relative_to(args.run_dir).as_posix(),
            }
        )
    else:
        mass_imbalance_pct = None
        checks.append(
            {
                "name": "inlet_outlet_mass_balance",
                "status": "incomplete",
                "threshold_percent": 0.1,
                "threshold_basis": "project pilot acceptance target",
                "reason": "missing patchFlowRate output or zero inlet flow",
            }
        )

    profiles: dict[str, object] = {}
    for station in PROFILE_STATIONS:
        name = "inletProfile" if station == -4 else f"profileX{station}"
        path = graph_file(args.run_dir, name)
        if path is None:
            profiles[str(station)] = {"status": "incomplete", "reason": "OpenFOAM graph output missing"}
            continue
        rows = numeric_rows(path)
        if not rows:
            profiles[str(station)] = {"status": "failed", "reason": "graph file has no numeric rows"}
            continue
        # graphUniform with axis=y writes y followed by Ux, Uy, Uz.
        prediction = [(row[0], row[1]) for row in rows if len(row) >= 2]
        metric = profile_rmse(prediction, profiles_exp.get(station, []))
        profiles[str(station)] = {
            "status": ("assessed" if converged else "provisional") if metric else "incomplete",
            "nasa_tmr_profile_rmse": metric,
            "output": path.relative_to(args.run_dir).as_posix(),
        }

    shear_path = graph_file(args.run_dir, "lowerWallShear")
    reattachment: dict[str, object]
    if shear_path is None:
        reattachment = {"status": "incomplete", "reason": "lower-wall wallShearStress graph missing"}
    else:
        rows = numeric_rows(shear_path)
        # graphUniform with axis=x writes x, then wallShearStress components.
        cf = [(row[0], -row[1] / 0.5) for row in rows if len(row) >= 2 and row[0] > 0]
        crossings = [event for event in zero_crossings(cf) if event["x_over_H"] >= 0]
        reattachment_candidates = [
            event for event in crossings if event["direction"] == "negative_to_positive"
        ]
        separation_candidates = [
            event for event in crossings if event["direction"] == "positive_to_negative"
        ]
        if reattachment_candidates:
            first = float(reattachment_candidates[0]["x_over_H"])
            reattachment = {
                "status": "assessed" if converged else "provisional",
                "x_over_H": first,
                "definition": "first negative-to-positive Cf crossing on the lower wall",
                "cf_sign_convention": "Cf = -wallShearStress_x / 0.5",
                "separation_candidates_x_over_H": [
                    event["x_over_H"] for event in separation_candidates
                ],
                "reattachment_candidates_x_over_H": [
                    event["x_over_H"] for event in reattachment_candidates
                ],
                "nasa_tmr_reference_x_over_H": NASA_REATTACHMENT,
                "nasa_experimental_uncertainty_x_over_H": NASA_REATTACHMENT_UNCERTAINTY,
                "difference_from_reference": first - NASA_REATTACHMENT,
                "within_published_experimental_interval": abs(first - NASA_REATTACHMENT) <= NASA_REATTACHMENT_UNCERTAINTY,
                "all_crossings": crossings,
                "output": shear_path.relative_to(args.run_dir).as_posix(),
            }
        else:
            reattachment = {
                "status": "incomplete",
                "reason": "no negative-to-positive lower-wall Cf crossing found",
                "all_crossings": crossings,
                "output": shear_path.relative_to(args.run_dir).as_posix(),
            }

    result = {
        "schema": "cfd-repro-study.result/0.1",
        "execution_status": "completed" if converged else "incomplete",
        "numerical_status": "incomplete",
        "validation_status": "incomplete",
        "intended_use": "research_and_portfolio_only",
        "solver": {"family": "OpenFOAM Foundation", "version": "14"},
        "case_id": "nasa-tmr-2d-backward-facing-step",
        "checks": checks,
        "reference_comparison": {"lower_wall_reattachment": reattachment, "mean_velocity_profiles": profiles},
        "mass_balance_percent": mass_imbalance_pct,
        "input_hashes": {
            line.split(None, 1)[1]: line.split(None, 1)[0]
            for line in (args.run_dir / "input-sha256.txt").read_text(encoding="utf-8", errors="replace").splitlines()
            if len(line.split(None, 1)) == 2
        } if (args.run_dir / "input-sha256.txt").exists() else {},
        "uncertainty_note": "NASA's experimental uncertainty is reported separately; numerical uncertainty requires the planned three-grid study.",
        "evidence_paths": ["log.blockMesh", "log.checkMesh", *solver_log_names],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
