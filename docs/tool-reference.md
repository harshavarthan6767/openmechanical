# Tools and execution contract

All commands run through the installed `openmechanical` CLI; use `uv run --no-sync openmechanical` after syncing the checkout. JSON goes to stdout and progress messages to stderr. No server or API key is needed.

| Command | Purpose | Main evidence |
|---|---|---|
| `doctor --json` | Inspect packages and solver executables | Tool availability and actual versions |
| `validate problem.json --json` | Check schema and units | `valid` / `invalid_input` JSON |
| `prepare problem.json --out runs/new --json` | Prepare the bracket CAD, boundaries and mesh | STEP, mesh and boundary preview; no FEA |
| `run problem.json --out runs/new --json` | Solve one supported bracket or cantilever | Result JSON and retained solver evidence |
| `verify problem.json --out runs/new --json` | Verify one bracket using three meshes | `verification.json`, mesh-level runs |
| `compare problem.json --thickness-mm 6 8 10 --out runs/new --json` | Equal-resultant bracket thickness study | `comparison.json`, `report.html`, convergence plots |

Use a fresh output path for each operation. `verify`/`compare` currently apply to the bracket template. Cantilever `run` is a restricted proof workflow; it is not a general imported-CAD analyzer.

## Input and physics

Examples are in `examples/mounting_bracket/problem.json` and `examples/m0_cantilever/problem.json`. Quantities have a positive finite `value` and explicit `unit`. Inputs normalize to SI; CAD/deck boundaries use mm, N and MPa. Traction is force per area; do not put a total force value in a traction field. Comparison records the baseline total force and deliberately adjusts each candidate's traction for its face area.

Supported physics: homogeneous isotropic linear elasticity, small displacement, C3D10 solids, one complete fixed region, and one constant vector traction on the supported planar boundary. Bracket execution currently uses downward -Z traction on `loaded_pad` and a fixed `mount_face`. Density enables mass. Allowable-stress fields do not currently produce design pass/fail results.

Pressure, curved-face traction, arbitrary STEP execution, contact/bolts/preload, nonlinear response, fatigue, buckling, assemblies and arbitrary support/load configurations are outside the qualified execution subset. Some schemas reserve future concepts; `validate` acceptance does not guarantee an execution path exists.

## Statuses and exit handling

Execution completion, numerical verification, and design assessment are separate fields. A single solve can complete successfully while its numerical status is incomplete. A three-mesh verification passes only its stated geometry, equilibrium, displacement and regular-region stress checks. Design remains unassessed until a supported assessment policy and engineering data are established.

Exit 0 means the command completed its execution contract; inspect status fields. Exit 6 means required verification is failed or incomplete. Other nonzero returns indicate input/dependency/execution failure, with details in JSON and available logs. Do not continue a shell pipeline as though an ignored nonzero result were a pass.

## Evidence and limitations

The bracket adapter retains original/canonical inputs, CAD/mesh manifests, boundary previews, solver deck, DAT/FRD, stdout/stderr, binary/source hashes and result JSON. DAT stresses are parsed at all four C3D10 integration points. Loaded-face displacement is integrated with quadratic shape functions.

Refinement compares displacement and a fixed regular-region RMS stress, with strict trend checks. The raw global stress peak is preserved separately and can rise at an ideal clamp. Neither a regular-region pass nor a small force residual establishes whole-part strength or experimental validity. See the [readiness assessment](professional-readiness.md).
