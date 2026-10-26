#!/usr/bin/env python3
"""Generate fresh CAD, boundary previews, and quadratic meshes per thickness."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import uuid
from pathlib import Path

from openmechanical.bracket import prepare_bracket_mesh
from openmechanical.contracts import (
    MountingBracketGeometry,
    Quantity,
    validate_problem,
)
from openmechanical.units import validate_problem_units


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--problem", type=Path, default=Path(__file__).with_name("problem.json"))
    parser.add_argument("--study", type=Path, default=Path(__file__).with_name("study.json"))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    try:
        original_bytes = args.problem.read_bytes()
        problem = validate_problem(json.loads(original_bytes))
        validate_problem_units(problem)
        study = json.loads(args.study.read_text(encoding="utf-8"))
        candidates = [Quantity.model_validate(item) for item in study["thickness_candidates"]]
        if not isinstance(problem.geometry, MountingBracketGeometry):
            raise ValueError("problem.geometry.kind must be mounting_bracket")
        if not candidates:
            raise ValueError("study must define at least one thickness candidate")
        for candidate in candidates:
            Quantity(value=candidate.value, unit=candidate.unit)
            validate_problem_units(
                problem.model_copy(
                    update={
                        "geometry": problem.geometry.model_copy(update={"thickness": candidate})
                    }
                )
            )
    except (OSError, KeyError, TypeError, ValueError) as exc:
        parser.error(f"invalid bracket preparation input: {exc}")

    root = args.out.resolve()
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        suffix = f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:8]}"
        root = root.with_name(f"{root.name}-{suffix}")
    root.mkdir(parents=True, exist_ok=True)
    (root / "problem.original.json").write_bytes(original_bytes)
    (root / "study.original.json").write_text(
        json.dumps(study, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    records = []
    for candidate in candidates:
        variant = problem.model_copy(
            update={"geometry": problem.geometry.model_copy(update={"thickness": candidate})}
        )
        label = f"thickness-{candidate.value:g}-{candidate.unit.replace('/', '-')}"
        record = prepare_bracket_mesh(variant, root / label)
        records.append({"candidate": candidate.model_dump(mode="json"), **record})
    manifest = {
        "preparation_status": "completed",
        "analysis_status": "not_run",
        "design_status": "unassessed",
        "source_problem_sha256": sha256_bytes(original_bytes),
        "candidates": records,
        "limitations": [
            "geometry and mesh preparation only; no CalculiX analyses were run",
            "no candidate meets or violates design criteria because none were assessed",
        ],
    }
    (root / "preparation-study.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
