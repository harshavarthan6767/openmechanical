# Mesh Quality and Response Error Benchmark

**Status: frozen 30-attempt pilot complete for the declared cantilever case. The broad tool proposal was rejected by the Court 12–0. Twenty-nine samples ran and passed equilibrium; one mesh was retained as invalid. All solved tip errors were below 0.83%, so this pilot cannot show whether a minSICN cutoff catches inaccurate responses.**

This pilot tests whether a mesh-quality score can warn when predicted cantilever bending error exceeds 2%. It starts from the exact three meshes archived in the published OpenMechanical cantilever benchmark, varies interior-node positions while preserving all boundary nodes, and compares tip deflection with a Timoshenko beam estimate. The result is limited to this case, element family, mesh generator, and solver version; it did not produce any over-limit response case.

The broad proposal for a general agentic mesh-assurance tool failed structured review. Existing software and research already cover mesh generation, quality measures, and numerical error assessment; this pilot makes no novelty claim. The full broad-proposal verdict is recorded locally under `.court/` and is not a technical peer review.

A separate 12-juror Court review of whether these pilot results justify recommending a minSICN cutoff returned **GUILTY, 9 to 3**. The judge's sentence is: “Do not recommend a tested cutoff as reliable on this record.” This is an adversarial review of the claim, not scientific peer review. The complete transcript is retained locally under `.court/` and excluded from the public release.

The pilot reuses the existing OpenMechanical cantilever meshes and expands their three refinement points into a controlled perturbation study. A separate direct-OCC smoke mesh was superseded because it did not use the exact baseline mesh files. The selected baseline inputs are hash-pinned under [data/base-meshes](data/base-meshes/README.md). The project does not yet cover a plate with a hole, adaptive meshing, or other solvers.

## Pilot result

The fixed set records 30 attempts: 29 solver-completed meshes and one invalid
5 mm mesh at `0.01h`, seed 23. The invalid mesh kept boundary nodes fixed but
had negative minimum SICN, SJ, and determinant Jacobian; it was not sent to the
solver. Every solved sample passed the equilibrium check and had a tip
deflection error between `0.7147%` and `0.8292%` against the Timoshenko
estimate. The largest relative force and moment residuals were `3.824e-6` and
`2.117e-7`.

| Minimum SICN probe | False rejects among 29 response-accurate meshes | False safe |
|---:|---:|---:|
| 0.05 | 1 | 0 |
| 0.10 | 9 | 0 |
| 0.20 | 9 | 0 |

These are project-defined probes, not standard acceptance limits. Because no
solved sample exceeded the 2% response-error target, zero false-safe cases do
not show that any probe detects inaccurate results. The measured false rejects
show that these cutoffs can reject accurate meshes in this one template.

The [full report, JSON results, protocol and compressed raw artifacts](docs/evidence/run-20261026T175200Z/)
preserve sample-level hashes and statuses. A useful follow-up would first
freeze a new protocol that spans response errors around and above 2%, then add
an independent geometry or response before recommending any mesh screen.

## Current documents

- [Research and claim audit](docs/research.md)
- [Implementation plan](docs/implementation-plan.md)
- [Frozen pilot protocol](docs/protocol-v0.1.md)
- [Qualified WSL environment](docs/environment-qualification.md)
- [Run results and full raw evidence](docs/evidence/run-20261026T175200Z/)

## Reproduce the pilot

The qualified environment used Ubuntu 24.04 LTS under WSL, Python 3.12.3,
Gmsh Python module 4.12.1, NumPy 1.26.4, and CalculiX 2.21 (`ccx` on `PATH`).
See the [environment record](docs/environment-qualification.md) for package
versions. From the project root in a matching Linux or WSL environment:

```bash
python3 scripts/run_benchmark.py --smoke --out runs/baseline-smoke
python3 scripts/run_benchmark.py --out runs/full-pilot
```

Each output path must be new. The full command writes the fixed 30-attempt
protocol, summary, per-sample JSON, generated meshes, CalculiX decks, and raw
solver outputs. The first command is a one-sample smoke and cannot replace the
full run.

## Scope limits

The study will not claim that a geometric quality score proves solution accuracy, that a low-quality mesh always creates a large error, that one solver or mesher is generally superior, or that an AI agent is novel. It will report each benchmark's assumptions, reference uncertainty, element and solver limitations, quality thresholds, and complete run provenance. The report will distinguish mesh admissibility, numerical verification, and physical validation.
