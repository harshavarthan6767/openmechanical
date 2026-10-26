"""Independent axial patch, rotated patch, load-linearity and bending checks."""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import math
from pathlib import Path

import numpy as np

from openmechanical.cantilever import main as cantilever
from openmechanical.solver import parse_dat, read_mesh, solve, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=False)
    policy = {
        "axial_displacement_relative_tolerance": 1e-5,
        "axial_stress_tensor_relative_tolerance": 1e-5,
        "bending_reference_relative_tolerance": 0.02,
        "case": "200 x 20 x 10 mm; E=210000 MPa; axial nu=0 avoids clamp Poisson effects",
        "rotation": "30 degrees about Z, translated by [17,-3,8] mm",
        "note": "uniform stress and displacement reference, not fitted to solver output",
    }
    write_json(root / "policy.json", policy)
    with (root / "cantilever-cli.json").open("w") as log, contextlib.redirect_stdout(log):
        status = cantilever(["--out", str(root / "cantilever")])
    if status:
        raise RuntimeError("cantilever mesh generation failed")
    mesh = read_mesh(root / "cantilever/cantilever.msh", "FIXED_END", "LOADED_END")
    angle = math.pi / 6
    rotation = np.array(
        [[math.cos(angle), -math.sin(angle), 0], [math.sin(angle), math.cos(angle), 0], [0, 0, 1]]
    )
    records = []
    for name, transform, offset, magnitude in (
        ("axial", np.eye(3), np.zeros(3), 0.5),
        ("rotated_axial", rotation, np.array([17.0, -3.0, 8.0]), 0.5),
        ("double_load", np.eye(3), np.zeros(3), 1.0),
    ):
        candidate = dataclasses.replace(
            mesh, coordinates={n: transform @ xyz + offset for n, xyz in mesh.coordinates.items()}
        )
        direction = transform @ np.array([1.0, 0.0, 0.0])
        result = solve(candidate, 210000.0, 0.0, direction * magnitude, root / name)
        raw = parse_dat(
            root / name / "analysis.dat", set(mesh.coordinates), mesh.fixed, set(mesh.elements)
        )
        displacement_error = max(
            np.linalg.norm(raw["u"][n] - direction * magnitude / 210000.0 * xyz[0])
            for n, xyz in mesh.coordinates.items()
        ) / (magnitude * 200 / 210000.0)
        tensor = magnitude * np.outer(direction, direction)
        expected = np.array(
            [tensor[0, 0], tensor[1, 1], tensor[2, 2], tensor[0, 1], tensor[0, 2], tensor[1, 2]]
        )
        stress_error = (
            max(np.linalg.norm(stress - expected) for stress in raw["s"].values()) / magnitude
        )
        passed = (
            displacement_error <= 1e-5 and stress_error <= 1e-5 and all(result["checks"].values())
        )
        records.append(
            {
                "case": name,
                "status": "passed" if passed else "failed",
                "full_field_displacement_error_relative": float(displacement_error),
                "full_field_stress_tensor_error_relative": float(stress_error),
                "tip_displacement_reference_mm": magnitude * 200 / 210000.0,
                "force_residual_relative": result["force_residual_relative"],
                "moment_residual_relative": result["moment_residual_relative"],
            }
        )
        print(records[-1], flush=True)
    bending = solve(mesh, 210000.0, 0.3, np.array([0.0, 0.0, -0.5]), root / "bending")
    reference = 100 * 200**3 / (3 * 210000 * (20 * 10**3 / 12)) + 100 * 200 / (
        (5 / 6) * (210000 / 2.6) * 200
    )
    error = (
        abs(abs(bending["result"]["area_mean_loaded_displacement_mm"][2]) - reference) / reference
    )
    records.append(
        {
            "case": "bending",
            "reference_mm": reference,
            "relative_error": error,
            "status": "passed" if error <= 0.02 and all(bending["checks"].values()) else "failed",
        }
    )
    summary = {
        "status": "passed" if all(r["status"] == "passed" for r in records) else "failed",
        "scope": "supported C3D10 adapter numerical qualification; not physical validation",
        "cases": records,
    }
    write_json(root / "qualification.json", summary)
    print(summary)
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
