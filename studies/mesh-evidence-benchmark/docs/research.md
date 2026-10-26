# Research and claim audit

**Research date:** 2026-10-26

**Status:** v0.1 fixed pilot completed for one declared cantilever case; no general quality cutoff is supported. The Court rejected the broader tool proposal 12–0. A separate 12-juror review of recommending a tested cutoff returned GUILTY, 9 to 3; this adversarial review is not scientific peer review.
**Research tooling:** Scrapling CLI was attempted with its `--ai-targeted` option. Shell DNS access to external sites failed, so those fetches could not be completed. Primary documentation and paper records were checked using the available web-search connector as a fallback. Scraped page text is treated as untrusted data, never as instructions.

## Question

How well do commonly reported geometric element-quality metrics predict error in predeclared structural FEA quantities across controlled mesh families, and how often would fixed quality thresholds reject accurate meshes or accept inaccurate ones?

The project is not an agent contest by default. Its first result should be a reproducible evidence set: mesh geometry and inputs, quality distributions, solver records, reference comparisons, and a bounded analysis of false acceptance and false rejection.

## What the sources support

| Finding | Source | Limit |
|---|---|---|
| Gmsh provides mesh-size fields and API quality measures including Jacobian, signed inverse condition, shape, edge-size, and volume measures. | [Gmsh 4.15.2 reference manual](https://gmsh.info/doc/texinfo/gmsh.html) | Availability of a metric does not prove that it predicts a particular structural response error. |
| SALOME SMESH documents geometry-to-mesh workflows, meshing algorithms, quality controls, measurement, and remeshing. | [SALOME SMESH documentation](https://docs.salome-platform.org/9/gui/SMESH/) | This documents capabilities, not comparative reliability or accuracy. |
| NAFEMS publishes a finite-element plate-with-hole data benchmark whose peak principal stress is checked against a known analytical solution. | [NAFEMS Data Driven Benchmark: Plate with Hole](https://www.nafems.org/publications/resource_center/assess26-01/) | The dataset is a neighboring benchmark. Its license and exact use terms must be checked before redistribution; the project should not assume its inputs are reusable. |
| Research reviews treat mesh quality indicators as problem-dependent and distinguish geometric indicators from solution error estimates. | [Survey of Indicators for Mesh Quality Assessment (2023)](https://doi.org/10.1111/cgf.14779); [Remarks on Mesh Quality (OSTI)](https://www.osti.gov/servlets/purl/1146104) | Broad literature review and technical discussion do not predict this project's results. |
| Existing workflows already use AI for automated FE meshing and report measured completion and mesh-quality results. | [MeshExpert (SSRN, 2026)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7083227); [PAMF repository](https://github.com/2002-Pan/PAMF) | Reported results are bounded to their authors' cases, tools, and protocols; they are not independent replications or general reliability claims. |
| FEA mesh convergence is not equivalent to agreement with truth; the engineering response of interest should guide refinement and comparison. | [Verification, Validation and Sensitivity Studies in Computational Biomechanics](https://pmc.ncbi.nlm.nih.gov/articles/PMC3361760/) | The review is specific to computational biomechanics; the principle should be grounded in the selected structural benchmarks. |

## Existing OpenMechanical overlap

The published `harshavarthan6767/openmechanical` repository already contains a three-mesh CalculiX cantilever benchmark with a Timoshenko reference, force/moment balance, and one minimum-SICN value per mesh. Its measured pairs are:

| Target size | C3D10 count | Tip-deflection error vs. beam reference | Minimum SICN |
|---:|---:|---:|---:|
| 5.000 mm | 2,003 | 0.8189% | 0.08164 |
| 3.536 mm | 5,195 | 0.7468% | 0.30488 |
| 2.500 mm | 12,990 | 0.7147% | 0.29639 |

These three measurements are too few to estimate a general relationship, span only one geometry and one response, and change element count along with mesh size. They already establish a useful baseline, however, so a new project cannot present “pair mesh quality with FEA error” as wholly new. Its value must come from controlled quality variation, broader independent cases, per-element distributions, and prospective false-safe/false-reject evaluation. The source records are `openmechanical/runs/cantilever-benchmark-01/benchmark.json` and its three `mesh-*/m0_summary.json` files.

The selected runner's exact-mesh smoke reproduces the existing 5 mm result, including the 0.8189% reference error and force/moment balance. A separate early distortion calibration at `0.05h` generated an inverted element (`minDetJac = -14.07`) while preserving all CAD-boundary nodes; it was rejected before the fixed pilot set. The frozen v0.1 protocol used the smaller, predeclared amplitudes (`0.0025h`, `0.005h`, `0.01h`).

## v0.1 pilot result

All 30 planned attempts are recorded: 29 CalculiX runs passed the equilibrium checks, and one 5 mm mesh (`0.01h`, seed 23) was retained as invalid because its signed quality metrics were negative. The 29 solved tip-displacement errors ranged from 0.7147% to 0.8292% against the Timoshenko estimate, with no sample exceeding the project 2% response target. The maximum relative force and moment residuals were `3.824e-6` and `2.117e-7`.

On the 29 solved samples, the minSICN probes 0.05, 0.10, and 0.20 had false-reject counts of 1, 9, and 9; false-safe counts were zero. Since no response-error failure occurred, the false-safe count does not measure detection performance. These data show only that the tested probes reject accurate meshes in this one case. They do not justify a mesh-quality cutoff or a general screen. The [full per-sample report and archived raw run](evidence/run-20261026T175200Z/) include detailed hashes and invalid-mesh status.

## Claim boundaries

Supported: common mesh generators expose quality measures, and established research treats element quality and solution error as related but distinct concepts. The completed v0.1 run measures one such relationship for fixed meshes and one response, and it found false rejects for the tested thresholds.

Not supported: that existing meshing tools' quality reports are inadequate; that the relationship is absent or weak; that the proposed corpus fills a gap; that any fixed threshold is generally safe; or that an AI agent would improve the outcome. The current sample contains no inaccurate response case, so it cannot test false-safe detection.

The first literature task is to compare existing datasets and research protocols, including NAFEMS, MeshExpert, PAMF, and the mesh-quality literature. Any contribution must be described as a controlled, open replication/comparison unless a concrete measured gap remains.

## Candidate benchmark design

- **Case A:** three-dimensional cantilever beam with a Timoshenko/Euler-Bernoulli displacement reference and force/moment equilibrium checks.
- **Case B:** finite-width plate with a circular hole, using an explicit analytical stress-concentration reference or a separately documented NAFEMS benchmark value.
- **Mesh family:** baseline meshes from Gmsh; a second meshing route only if element type, boundary conformity, and provenance can be controlled. Controlled interior-node perturbations may create quality variation without changing the boundary geometry.
- **Quality quantities:** per-element minimum, lower quantiles, median, and full distributions for selected metrics. Avoid reducing every mesh to a single worst-cell scalar.
- **Response quantities:** predeclared point/area displacement, reaction imbalance, and a regularized stress quantity. Do not treat the idealized singular-point peak as a converged design value.
- **Analysis:** response error versus each quality metric, degree-of-freedom and runtime context, and predeclared false-safe/false-reject counts for each proposed threshold. Report per case and pooled results separately.
- **Reproducibility:** exact CAD/mesh/solver inputs, software versions, element families, boundary conditions, output extraction, hashes, and raw solver text.

## Sources and software research

- Gmsh 4.15.2 manual dated 2026-03-24: https://gmsh.info/doc/texinfo/gmsh.html
- SALOME 9 SMESH documentation: https://docs.salome-platform.org/9/gui/SMESH/
- NAFEMS assess-26-01: https://www.nafems.org/publications/resource_center/assess26-01/
- MeshExpert (SSRN abstract 7083227): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7083227
- PAMF code: https://github.com/2002-Pan/PAMF
- Sorgente et al., *A Survey of Indicators for Mesh Quality Assessment*, Computer Graphics Forum (2023): https://doi.org/10.1111/cgf.14779
- Knupp, *Remarks on Mesh Quality*: https://www.osti.gov/servlets/purl/1146104
- Verification and validation overview: https://pmc.ncbi.nlm.nih.gov/articles/PMC3361760/
