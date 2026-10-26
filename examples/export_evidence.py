"""Publish a compact, unchanged result snapshot without copying raw solver workspaces."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from openmechanical.reporting import write_comparison_report
from openmechanical.solver import sha256, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--units", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=False)
    summary = json.loads((args.study / "comparison.json").read_text())
    copied = {}

    def copy(source, relative):
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied[str(relative)] = sha256(source)

    for filename in ("comparison.json", "comparison-policy.json"):
        copy(args.study / filename, Path(filename))
    for index, candidate in enumerate(summary["candidates"]):
        relative = Path(f"candidate-{index}")
        copy(args.study / relative / "study-policy.json", relative / "study-policy.json")
        for mesh_index, _ in enumerate(candidate["verification"]["runs"]):
            run = relative / f"mesh-{mesh_index}"
            for filename in ("result.json", "input.json", "canonical.json"):
                copy(args.study / run / filename, run / filename)
    preview = Path("candidate-0/mesh-0/geometry/boundary-preview.png")
    copy(args.study / preview, preview)
    copy(args.backend, Path("backend-qualification.json"))
    copy(args.units, Path("unit-equivalence.json"))
    write_comparison_report(root, summary)
    svg = root / "convergence.svg"
    svg.write_text(
        "\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        "# Published numerical evidence\n\n"
        "This is a compact snapshot of actual retained CalculiX results, not a new solve. "
        "The exported JSON records and inputs are copied unchanged; source file hashes "
        "are in `export-manifest.json`.\n\n"
        "Open [report.html](report.html), [comparison.json](comparison.json), "
        "[backend qualification](backend-qualification.json), or "
        "[unit equivalence](unit-equivalence.json). "
        "Download the HTML to view its embedded plots.\n\n"
        "Raw STEP, mesh, deck, DAT/FRD, logs and per-run source snapshots are not bundled "
        "in Git. Reproduce them with the commands in [the installation guide](../installation.md). "
        "The result records retain the original raw-artifact checksums.\n\n"
        "Numerical passing is limited to the declared scope. Design status remains "
        "unassessed, and raw global clamp peaks are not qualified as converged design stresses.\n",
        encoding="utf-8",
    )
    write_json(
        root / "export-manifest.json",
        {
            "method": "unchanged JSON/input copy; report rendered from the retained comparison",
            "raw_solver_files_bundled": False,
            "copied_source_sha256": copied,
            "exporter_sha256": sha256(Path(__file__)),
        },
    )
    print(json.dumps({"status": "exported", "files_copied": len(copied)}))


if __name__ == "__main__":
    main()
