"""Minimal CLI entry point."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from pydantic import ValidationError

from .contracts import BoxGeometry, validate_problem
from .units import validate_problem_units


def main() -> int:
    parser = argparse.ArgumentParser(prog="openmechanical")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor_parser = subparsers.add_parser("doctor", help="inspect engineering tool availability")
    doctor_parser.add_argument("--json", action="store_true")
    validate_parser = subparsers.add_parser("validate", help="validate a problem JSON file")
    validate_parser.add_argument("problem", type=Path)
    validate_parser.add_argument("--json", action="store_true")
    run_parser = subparsers.add_parser("run", help="execute a supported structural problem")
    run_parser.add_argument("problem", type=Path)
    run_parser.add_argument("--out", type=Path, required=True)
    run_parser.add_argument("--json", action="store_true")
    for name in ("prepare", "verify", "compare"):
        command_parser = subparsers.add_parser(name)
        command_parser.add_argument("problem", type=Path)
        command_parser.add_argument("--out", type=Path, required=True)
        command_parser.add_argument("--json", action="store_true")
        if name == "compare":
            command_parser.add_argument("--thickness-mm", nargs="+", type=float, required=True)
    args = parser.parse_args()

    if args.command == "doctor":
        return _doctor()
    try:
        original_input = args.problem.read_bytes()
        data = json.loads(original_input, parse_constant=_reject_constant)
        problem = validate_problem(data)
        validate_problem_units(problem)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(json.dumps({"status": "invalid_input", "error": str(exc)}, allow_nan=False))
        return 2

    if args.command != "validate":
        try:
            from .verification import compare_brackets, run_bracket, verify_bracket

            if args.command == "run" and isinstance(problem.geometry, BoxGeometry):
                from .cantilever import main as run_cantilever

                return run_cantilever(["--spec", str(args.problem), "--out", str(args.out)])
            if args.command == "run":
                result = run_bracket(problem, args.out.resolve())
            elif args.command == "verify":
                result = verify_bracket(problem, args.out.resolve())
            elif args.command == "compare":
                result = compare_brackets(
                    problem,
                    args.thickness_mm,
                    args.out.resolve(),
                    progress=lambda message: print(message, file=sys.stderr, flush=True),
                )
            else:
                from .bracket import prepare_bracket_mesh

                result = prepare_bracket_mesh(problem, args.out.resolve())
            from .solver import sha256, write_json

            original_path = args.out.resolve() / "problem.original.json"
            original_path.write_bytes(original_input)
            write_json(
                args.out.resolve() / "cli-provenance.json",
                {
                    "original_input_sha256": sha256(original_path),
                    "source_problem": str(args.problem.resolve()),
                    "command": args.command,
                },
            )
            print(json.dumps(result, allow_nan=False))
            return (
                6
                if result.get("numerical_status") == "failed"
                or (
                    args.command in ("verify", "compare") and result["numerical_status"] != "passed"
                )
                else 0
            )
        except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
            print(json.dumps({"execution_status": "failed", "error": str(exc)}))
            return 2 if isinstance(exc, ValueError) else 4

    print(
        json.dumps({"status": "valid", "schema_version": problem.schema_version}, allow_nan=False)
    )
    return 0


def _doctor() -> int:
    tools: dict[str, dict[str, str | None]] = {}
    for module_name, display_name in (
        ("cadquery", "CadQuery"),
        ("gmsh", "Gmsh Python API"),
        ("pint", "Pint"),
        ("pydantic", "Pydantic"),
    ):
        try:
            module = __import__(module_name)
            version = getattr(module, "__version__", "available")
            tools[display_name] = {"status": "available", "version": str(version)}
        except Exception as exc:
            tools[display_name] = {"status": "missing", "version": None, "error": str(exc)}

    for executable, version_args, name in (
        ("ccx", ["-v"], "CalculiX"),
        ("gmsh", ["--version"], "Gmsh executable"),
    ):
        path = shutil.which(executable)
        if path is None:
            tools[name] = {"status": "missing", "version": None, "path": None}
            continue
        try:
            result = subprocess.run(
                [path, *version_args], capture_output=True, text=True, timeout=10, check=False
            )
            output = (result.stdout + result.stderr).strip()
            output_lines = output.splitlines()
            if name == "CalculiX":
                match = re.search(r"This is Version\s+([^\s]+)", output)
                version = match.group(1) if match else "unknown"
                recognized = match is not None
            else:
                version = next((line.strip() for line in output_lines if line.strip()), "unknown")
                recognized = result.returncode == 0
            tools[name] = {
                "status": "available" if recognized else "error",
                "version": version,
                "path": path,
            }
        except (OSError, subprocess.TimeoutExpired) as exc:
            tools[name] = {"status": "error", "version": None, "path": path, "error": str(exc)}

    overall = (
        "ready" if all(tool["status"] == "available" for tool in tools.values()) else "incomplete"
    )
    print(json.dumps({"status": overall, "tools": tools}, allow_nan=False))
    return 0 if overall == "ready" else 3


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number {value!r} is not allowed")


if __name__ == "__main__":
    sys.exit(main())
