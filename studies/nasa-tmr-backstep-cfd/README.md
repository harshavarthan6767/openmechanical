# OpenFOAM Backward-Step Reproduction Study

**Status: coarse baseline executed; mesh audit and mass balance pass, while iterative convergence and experimental validation remain incomplete.**

This project documents a reproducible OpenFOAM Foundation v14 study of NASA's two-dimensional backward-facing-step experiment. It records the case assumptions, solver and mesh, run evidence, numerical sensitivity, and comparison with the published measurements. It is a case study, not a new CFD agent or an assurance product.

The primary reference is NASA's two-dimensional backward-facing-step validation case based on Driver and Seegmiller's experiment. NASA's Turbulence Modeling Resource gives the case conditions, experimental profiles, and measured reattachment point `x/H = 6.26 ± 0.10`. The planned runtime is OpenFOAM Foundation v14 on Ubuntu 24.04 under WSL. The solver install and the Foundation's packaged tutorial smoke check passed. Two early meshes were rejected: the first omitted NASA's upstream symmetry sections, and the second passed topology checks but failed the full quality policy. The selected 128,256-cell mesh follows the schematic, starts the walls at `x/H = -110`, and passes topology, geometry, and mesh-quality checks.

The coarse baseline ran to iteration 12,000, but did not meet the declared SIMPLE residual controls, so the numerical result remains incomplete. The measured relative inlet/outlet flux imbalance is `4.77e-6%`, below the project's `0.1%` pilot threshold. The first lower-wall negative-to-positive skin-friction crossing is `x/H = 6.07586`, which is `0.18414H` below NASA's central value and outside the reported interval `[6.16, 6.36]`. This comparison is provisional because the solve did not converge and no grid-sensitivity study has been completed. Velocity-profile RMSE values are archived as provisional as well. The run logs, hashes, sampled profiles, and machine-readable analysis are in [the baseline evidence directory](docs/evidence/run-20261026T165738Z/).

## Why this is narrow

The earlier opportunity report ranked broad CFD case setup first, but that order was a product judgment, not evidence of unmet demand. Current research found multiple systems that already generate, execute, and check OpenFOAM workflows, plus an official OpenCFD backward-step example. AI CFD Scientist also reports a physics-aware gate that caught 14 of 16 planted silent failures in its bounded study. Those results do not establish broad reliability, but they rule out claims that the area is untouched. This project therefore asks a bounded reproducibility question instead of claiming a new assurance capability.

The Court reviewed an earlier, broader assurance-workflow proposition and rejected it **12–0**. That verdict remains in force for the tool proposition. This study narrows the work to a reproducible case and makes no distinct-assurance claim; the narrower study has not had a separate Court review. The trial transcript is retained locally and is not part of this release. The Court review is a project decision record, not scientific validation.

## Study definition

| Item | Initial definition |
|---|---|
| Reference workflow | Steady RANS of the NASA 2D backward-facing step |
| Intended users | CFD students and engineers reproducing a public turbulence-model validation case |
| Solver line | OpenFOAM Foundation v14; do not silently mix with OpenCFD releases |
| Reference quantity | Reattachment location `x/H`, compared with the published experimental value and uncertainty |
| Numerical evidence | Mesh checks, convergence history, mass conservation, three-grid sensitivity/GCI, and exact input/software hashes |
| Intended use | Open-source engineering portfolio and reproducible case study; not a safety or compliance claim |
| Environment | WSL Ubuntu 24.04; OpenFOAM Foundation v14 package `20261008`; Gmsh 4.12.1 |
| P0 smoke check | Official `pitzDailySteady`: `blockMesh`, `checkMesh` (`Mesh OK`), and `foamRun` passed; SIMPLE converged in 285 iterations |
| Current gate | Diagnose why the baseline misses residual controls and the reattachment interval; then rerun and complete the three-grid sensitivity study before making validation claims |

## Research gate

Do not call this a distinct tool or publish a performance claim until the project has:

1. Reproduced the named case with a documented OpenFOAM v14 build and complete input provenance.
2. Declared thresholds before the study, then reported iterative convergence, mass-balance error, mesh-quality results, and grid sensitivity for `x/H`.
3. Compared the result with the NASA experimental reference and reported numerical and experimental uncertainty separately.
4. Compared the case assumptions and reported quantities with the official OpenCFD example while keeping the Foundation and OpenCFD releases explicitly separate.

These are research gates, not universal CFD standards. A failed or incomplete gate must stay visible in the report. Any future claim that this work adds a distinct assurance capability needs a separate failure-injection comparison against existing systems; this project makes no such claim.

## Research and plan

- [Research and claim audit](docs/research.md)
- [Implementation plan](docs/implementation-plan.md)
- [P0 environment qualification record](docs/environment-qualification.md)
- [NASA TMR reference data provenance](data/reference/README.md)
- [Case assumptions and run instructions](cases/nasa-tmr-backstep/README.md)
- [Mesh audit and rejected prototypes](docs/evidence/mesh-audit.md)
- [Baseline run evidence and analysis](docs/evidence/run-20261026T165738Z/analysis-result.json)

## Tooling used for this research

The Scrapling CLI (v0.4.15) and its official `scrapling-official` Codex skill were used in the research workflow. A direct Scrapling fetch attempt failed because the environment could not resolve the external host; no scraped page content is included in this repository. Public technical claims were cross-checked against official and primary sources. The `court` skill was used for a structured review of the broader assurance-tool proposition; that verdict is a project decision record, not scientific evidence. Solver claims rely on the archived run artifacts and published reference data.
