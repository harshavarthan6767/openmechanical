# Research and claim audit

**Research date:** 2026-10-26  
**Project status:** solver environment qualified with an official tutorial smoke run; the first mesh was rejected for geometry mismatch and a second corrected mesh failed the installed Foundation v14 mesh-quality policy. A third mesh with conformal grading passes full topology, geometry, and quality checks. Its coarse run reached iteration 12,000 but missed the SIMPLE residual controls. Mass balance passed the project pilot target, while the provisional reattachment estimate fell outside the NASA interval. No validation result is established; the three-grid study remains outstanding.

## Summary

The broad opportunity “build an agent that converts natural-language requirements into OpenFOAM cases” is no longer a defensible novelty claim. Published and public projects already cover natural-language-to-case workflows, execution repair, physical-field review, mesh checks, result reporting, and grid studies. CFDLLMBench already provides a substantial public benchmark for CFD knowledge, numerical reasoning, and OpenFOAM workflow execution. OpenCFD also publishes an official backward-facing-step validation example matching the same Driver–Seegmiller reference. AI CFD Scientist reports a physics-aware gate catching 14 of 16 planted silent failures in its study. A new generic assurance tool has not shown a gap these existing systems miss.

The supported technical claim is narrower: solver completion is not the same as verification or validation. NASA guidance calls for checking iterative convergence and conservation, studying spatial and temporal convergence, and comparing against accurate solutions for verification; validation compares against experimental evidence. This supports testing an independent, reference-based check. It does not prove that a new tool is needed or that existing tools miss a particular failure.

## Claims checked

| Claim | Finding | Evidence and limit |
|---|---|---|
| “CFD case setup is the best next project.” | Ranking is a hypothesis, not demand evidence. | The attached report ranks this area first but expressly calls its ranking a product/engineering judgment. It contains no customer interviews, adoption data, or competitor comparison. |
| “OpenFOAM requires a complex workflow.” | Supported. | The Foundation v14 guide covers solver modules, case setup, numerical schemes, mesh generation, boundary conditions, turbulence/transport models, and post-processing. It describes roughly 150 applications and 150 libraries/modules. |
| “Current AI agents cannot complete CFD tasks.” | Too broad and stale. | CFDLLMBench found large gaps in its tested models and tasks. Later Foam-Agent work reports 88.2% execution success on its Basic tier and 62.5% on its Advanced tier. Those are benchmark-specific and do not prove broad engineering reliability. |
| “A completed OpenFOAM run can still be physically wrong.” | Supported as a verification/validation principle. | CFDLLMBench and Foam-Agent distinguish implementation, execution, convergence, and solution fidelity; NASA's V&V guidance calls for evidence beyond process exit. |
| “A new assurance layer adds unique value.” | Not established. | AgentCFD already documents applicability/conservation checks, result evidence, mesh checks, and three-grid GCI. AI CFD Scientist reports a vision-based gate for silent failures. No head-to-head experiment has shown a failure these tools accept. |
| “A backward-facing-step case can provide a measurable reference.” | Supported. | NASA's TMR gives the Driver–Seegmiller case, experimental profiles, `Re_H ≈ 36,000`, grid families, and `x/H_reattach = 6.26 ± 0.10`. Matching geometry, boundary conditions, flow assumptions, and solver line still needs careful implementation. |
| “A new backward-step assurance workflow would be distinct.” | Not established; the benchmark has strong existing coverage. | OpenCFD publishes a `simpleFoam` backward-facing-step example using `blockMesh` and k-omega SST against the same experiment. AgentCFD documents mesh, conservation, result, and grid checks. AI CFD Scientist reports vision-based detection of 14/16 planted silent failures. These are different releases and bounded results; they do not prove all checks are equivalent, but they make a new-tool novelty claim untenable without a head-to-head study. |

## Competitive and benchmark landscape

### OpenFOAM Foundation

OpenFOAM Foundation v14 was released on 14 July 2026. Its Ubuntu instructions support 24.04 and WSL, and the v14 user guide documents modular solver use (`foamRun` plus a solver module), case configuration, meshing, boundary conditions, physical models, and post-processing. The pilot will pin this Foundation line; Foundation and OpenCFD releases have different release and case behavior and must not be silently mixed.

### CFDLLMBench

The 2026 journal version of CFDLLMBench includes CFDQuery, CFDCodeBench, and FoamBench: 90 conceptual questions, 24 code tasks, and 110 Basic plus 16 Advanced OpenFOAM workflow tasks. The authors report baseline results including 14% on CFDCodeBench and 34% on FoamBench for their best tested model. These baseline numbers are not a statement about every current model: later systems report improved results on the same benchmark.

### Foam-Agent

Foam-Agent is published in *Computer Methods in Applied Mechanics and Engineering*. Its paper describes a six-agent OpenFOAM workflow and reports 88.2% execution success on 110 FoamBench Basic tasks and 62.5% on its out-of-distribution Advanced tier. It also reports a separate field-level fidelity metric, so the headline execution rate should not be described as an accuracy rate.

### AI CFD Scientist

The 2026 preprint presents literature-grounded CFD exploration built on Foam-Agent. It reports that its vision-language physics gate detected 14 of 16 planted silent failures in the study. That is a bounded result for those experiments, not a general guarantee. This directly challenges claims that independent physical checks are absent from existing systems.

### AgentCFD

The public pre-alpha repository describes executable workflows for OpenFOAM, including case preparation, solver execution, mesh checks, result recovery, pressure-loss evidence, and a three-grid GCI workflow. It therefore overlaps materially with a general verification-first workflow. Its README positions the OpenFOAM runtime and Python package as separate license/runtime boundaries. The project's current behavior and acceptance policy have not been independently audited in this research.

### Existing backward-step implementation

OpenCFD's 2606 documentation contains a backward-facing-step validation example based on Driver and Seegmiller. It documents `simpleFoam`, `blockMesh`, k-omega SST, `Re_H = 36,000`, and the NASA reattachment reference. This is a useful published comparison point, but it belongs to the OpenCFD release line and must not be treated as a Foundation v14 case or copied without an explicit compatibility review.

## Proposed reference case

NASA's Turbulence Modeling Resource describes the two-dimensional backward-facing-step validation case from Driver and Seegmiller. The case has a momentum-thickness Reynolds number of 5,000, approximately 36,000 based on step height, a pre-step boundary layer about `1.5H` thick, and a straight top wall for the cited comparison. The measured reattachment point is `x/H = 6.26 ± 0.10`; velocity, turbulence, skin-friction, and pressure data are available from the page.

The comparison is sensitive to inflow development, boundary conditions, turbulence model, and grid. The pilot must reproduce the documented case instead of reusing a visually similar tutorial and assuming equivalence. The reference uncertainty `±0.10` is experimental evidence; project-specific numerical uncertainty must be reported separately.

## Local environment evidence

- WSL distribution: Ubuntu 24.04 LTS (`OpenFOAM-UBU`).
- Gmsh 4.12.1: `/usr/bin/gmsh` is present.
- OpenFOAM Foundation v14 package `20261008` is installed in WSL. After sourcing `/opt/openfoam14/etc/bashrc`, `foamVersion` returns `OpenFOAM-14` and `foamRun`, `blockMesh`, and `checkMesh` resolve.
- The Foundation `pitzDailySteady` tutorial completed `blockMesh`, `checkMesh`, and `foamRun`; the mesh check said `Mesh OK` and SIMPLE converged in 285 iterations. This only checks the software path and is not evidence for the NASA case.
- The NASA experimental files and source/local hashes are recorded in `data/reference/README.md`. The first prototype had 94,976 hexahedral cells and passed basic `checkMesh`, but it started no-slip upper and lower walls at the inlet instead of including the symmetry sections shown in NASA's schematic before the walls begin at `x/H=-110`. It is not treated as a benchmark result. Its solve did not meet residual controls, and its `x/H=1` profile disagreed sharply with the experimental data; this is diagnostic evidence from an invalid setup only. The second prototype had the corrected symmetry/wall patches but failed Foundation v14's installed quality limits: minimum cell determinant `0.000192` (limit `0.001`) and 520 faces with interpolation weights below `0.05`. That partial solve was stopped. The third prototype preserves the same quality thresholds and passes all checks with 128,256 hexahedral cells, maximum aspect ratio `71.78`, minimum determinant `0.00210`, minimum face interpolation weight `0.0918`, zero non-orthogonality, and maximum skewness `6.95e-13`. Its run reached iteration 12,000 without meeting the SIMPLE residual controls. Relative inlet/outlet flux imbalance was `4.76625e-6%`, below the project's `0.1%` pilot target. The first lower-wall negative-to-positive skin-friction crossing was `x/H=6.07586`, outside NASA's `6.26 ± 0.10` interval. This comparison and the archived profile RMSE values are provisional; iterative convergence and three-grid sensitivity remain outstanding. Full logs, hashes, selected profile data, and machine-readable analysis are archived under `docs/evidence/run-20261026T165738Z/`.

## Court review

The court skill's 12-juror process rejected the broad assurance-workflow proposition **GUILTY, 12 to 0**. The three repeated concerns were: no named workflow/user, no demonstrated advantage over existing systems, and no testable pilot specification. It credited the technical distinction between successful execution and validation, but found that distinction alone did not justify a new project. The process was adapted using Codex agents; it was not run inside Claude Code and does not validate CFD physics. The technical claims were separately checked against primary sources, and the proposed case still needs numerical validation.

The project now narrows to an independent, version-pinned Foundation v14 reproduction and transparent comparison with NASA's reference. This is a research/portfolio deliverable, not a claim of distinct software value. The court's commercial “paid pilot” condition does not match the user's stated open-source portfolio goal, so the study will not claim to validate willingness to pay or market demand. The prior guilty verdict remains in force for the broad assurance-workflow proposition.

## Sources

1. OpenFOAM Foundation, [v14 release](https://openfoam.org/version/14/) and [Ubuntu/WSL installation instructions](https://openfoam.org/download/14-ubuntu/).
2. OpenFOAM Foundation, [OpenFOAM v14 User Guide](https://doc.cfd.direct/openfoam/user-guide/).
3. Somasekharan et al., [CFDLLMBench (2026)](https://arxiv.org/abs/2509.20374), with [code and data](https://github.com/NLR-Theseus/cfdllmbench/).
4. Yue et al., [Foam-Agent (2026)](https://arxiv.org/abs/2505.04997), [paper project](https://github.com/csml-rpi/Foam-Agent).
5. Somasekharan et al., [AI CFD Scientist (2026)](https://arxiv.org/abs/2605.06607), [code](https://github.com/csml-rpi/AI-CFD-Scientist).
6. Luo, [AgentCFD repository](https://github.com/haoming-luo/agentcfd).
7. NASA/Turbulence Modeling Working Group, [TMR Backward-Facing Step](https://tmbwg.github.io/turbmodels/backstep_val.html), [published mesh topology files](https://github.com/TMBWG/turbmodels/tree/main/Backstep_grids), and [experimental data repository](https://github.com/TMBWG/turbmodels/tree/main/Backstep_validation). The repository contents should be version-pinned and checked for redistribution terms before any data are copied into a release.
8. NASA Glenn/NPARC, [CFD Verification Assessment](https://www.grc.nasa.gov/www/wind/valid/tutorial/verassess.html), [V&V Overview](https://www.grc.nasa.gov/www/wind/valid/tutorial/overview.html), and [case documentation guidelines](https://www.grc.nasa.gov/www/wind/valid/document.html).
9. OpenCFD, [Backward-facing-step verification and validation example](https://doc.openfoam.com/2606/examples/verification-validation/turbulent/backward-facing-step/). This example is from the OpenCFD 2606 release line, not Foundation v14.
