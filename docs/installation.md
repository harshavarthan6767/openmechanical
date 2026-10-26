# Install OpenMechanical

The verified execution platform is Ubuntu 24.04 on Linux or WSL2, Python 3.12, and CalculiX 2.21. The lockfile pins CadQuery 2.8.0, Gmsh 4.12.1 and the Python dependencies. Native Windows solver execution is not part of the qualified scope.

## 1. System prerequisites

In Ubuntu/WSL:

```bash
sudo apt-get update
sudo apt-get install -y git curl calculix-ccx libgl1 libglu1-mesa
```

On Windows, open your Ubuntu WSL terminal for the commands below. Prefer a checkout in the Linux home directory for solver I/O.

Install the tested uv version using its [official installer](https://docs.astral.sh/uv/getting-started/installation/):

```bash
curl -LsSf https://astral.sh/uv/0.13.0/install.sh | sh
```

Open a new shell if `uv` is not on PATH.

## 2. Install the locked tools

```bash
git clone https://github.com/harshavarthan6767/openmechanical.git
cd openmechanical
uv sync --locked --extra dev --python 3.12
uv run --no-sync openmechanical doctor --json
```

The doctor output must show the required packages and CalculiX available. Confirm CalculiX reports **2.21**; another version has not been qualified by the published evidence. The repository does not bundle or replace the system solver.

No LLM API key is required to use the tools. A coding agent with terminal access can use the optional skill.

## 3. Run a demonstration

```bash
uv run --no-sync openmechanical validate examples/mounting_bracket/problem.json --json
uv run --no-sync openmechanical compare examples/mounting_bracket/problem.json --thickness-mm 6 8 10 --out runs/first-comparison --json
```

Open `runs/first-comparison/report.html`. The example uses illustrative dimensions/material and preserves 295 N total force across candidates. It produces numerical verification, not a design approval or a winning thickness. Choose a new output path for another study; existing evidence is never overwritten.

For a smaller task:

```bash
uv run --no-sync openmechanical prepare examples/mounting_bracket/problem.json --out runs/first-preview --json
uv run --no-sync openmechanical run examples/mounting_bracket/problem.json --out runs/first-solve --json
uv run --no-sync openmechanical verify examples/mounting_bracket/problem.json --out runs/first-verification --json
```

`prepare` performs no solve. `run` performs one solve and normally leaves numerical verification incomplete. `verify` runs three meshes. Exit code 6 from `verify` or `compare` means required verification did not pass; preserve and inspect its evidence.

## 4. Install the Codex skill

From the repository root in a Linux Codex environment:

```bash
mkdir -p ~/.codex/skills
cp -R skills/mechanical-fea ~/.codex/skills/
```

If that destination already exists, review/replace the existing skill rather than nesting another copy. Reload/restart the agent so it discovers the skill. Tell the agent where this checkout is, or set:

```bash
export OPENMECHANICAL_PROJECT="$PWD"
```

For Codex on Windows, copy `skills/mechanical-fea` into your Windows user profile's `.codex/skills` folder. Keep tool execution in WSL and give the agent both the WSL distribution and checkout path. Installing the skill alone does not install Python dependencies or CalculiX.

Example agent prompts:

> Use $mechanical-fea to run the supplied illustrative bracket study for 6, 8 and 10 mm thicknesses. Use a new output directory and explain the actual numerical and design statuses.

> Use $mechanical-fea to inspect my bracket problem JSON. Identify missing material/load/support data before running an analysis.

> Use $mechanical-fea to verify this supported bracket case across three meshes and link the report, raw peak stress, and regular-region convergence evidence.

The skill calls the same CLI you can run manually. It is not an independent solver, certification service, or MCP server.

## 5. Check the tools

```bash
uv run --no-sync pytest -q
uv run --no-sync ruff check src tests examples
uv run --no-sync python examples/qualify_backend.py --out runs/backend-check
```

The backend check executes actual axial, rotated axial, double-load and bending cases. For the separate three-mesh cantilever comparison:

```bash
uv run --no-sync python examples/m0_cantilever/benchmark.py --out runs/cantilever-check
```

See [professional-readiness.md](professional-readiness.md) for the exact measured scope and [tool-reference.md](tool-reference.md) for command outputs and limitations.
