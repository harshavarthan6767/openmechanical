---
name: mechanical-fea
description: Run OpenMechanical cantilever and filleted mounting-bracket FEA, check numerical verification, and interpret retained solver evidence. Use for the supported linear-static templates and thickness studies; general CAD import and unsupported physics require a different workflow.
---

# Mechanical FEA

Use the installed OpenMechanical package as the numerical execution layer. This skill requires a terminal, filesystem access, and a working Linux/WSL installation; it does not require an LLM API key or an MCP server.

## Locate the tools

Locate the checkout through the user's working directory or `OPENMECHANICAL_PROJECT`. Confirm it contains the OpenMechanical `pyproject.toml` and examples. In that checkout use `uv run --locked openmechanical ...`, or the verified environment's `openmechanical` executable. Run `doctor --json` before numerical work. If dependencies are missing, follow the repository's [installation guide](https://github.com/harshavarthan6767/openmechanical/blob/main/docs/installation.md).

## Match the supported scope

Execution supports the supplied rectangular cantilever proof and filleted L-bracket template, homogeneous isotropic linear elasticity, small displacement, quadratic tetrahedra, one full fixed region, and one constant vector traction. The bracket workflow currently expects downward -Z traction, `mount_face` fixed, and `loaded_pad` loaded.

Reject or explain unsupported pressure, curved-face traction, imported STEP execution, contact, bolt pretension, plasticity, large deformation, assemblies, fatigue, buckling, and arbitrary support patterns. Reserved schema fields do not imply executable capability.

For actual design work, obtain consequential missing dimensions, material properties/provenance, load definition, support idealization, and assessment criteria. Do not substitute the illustrative example steel or load for the user's engineering data. An explicitly requested demonstration may use the supplied example, labeled as illustrative. Density is optional for solving but required for mass. No design pass or winning thickness is currently produced, even when an allowable field is present.

## Execute and inspect

Read [references/cli.md](references/cli.md) when constructing input, choosing a command, or interpreting a result. Inputs carry explicit units. Validate the JSON, then choose the smallest workflow that fulfills the request:

- `prepare`: CAD, boundary preview, and mesh only.
- `run`: one actual solve; a single mesh normally leaves numerical verification incomplete.
- `verify`: three mesh levels for one bracket.
- `compare`: three mesh levels per thickness, preserving the baseline total force by explicitly adjusting candidate traction to face area.

Use a fresh output directory. Capture the command, exit status, JSON result, and evidence paths. If execution fails, inspect the retained logs/failure record and correct an identified cause; do not repeat an unchanged failed run or reuse stale outputs. Exit code 6 means required numerical verification is failed or incomplete.

## Interpret the evidence

Inspect execution, numerical, and design statuses separately. Solver completion alone is insufficient. Required checks include force/moment assembly and balance, mesh/geometry integrity, complete finite result coverage, displacement sensitivity, and the declared regular stress metric. Never weaken a tolerance, move a support, change a load, or alter a stress exclusion/region to obtain a pass.

The comparison report uses an area integral of loaded-face displacement and integration-point stress tensors. Its regular-region RMS is not a whole-part peak stress or an allowable comparison. Preserve and explain raw global peaks and nonconvergent clamp behavior. A scoped numerical pass does not establish physical validation or design safety.

Report measured quantities with units, the verification scope, failed/not-run checks, assumptions, and links to `report.html`, result JSON, and solver evidence. Keep missing design criteria or material validation visible as `design_status: unassessed`; select no winner from an unassessed study.
