# Mesh audit history

The study retains the rejected meshes because each exposed a distinct failure
that basic `blockMesh` success or `Mesh OK` alone would not catch.

| Prototype | Geometry and mesh | Result | Decision |
|---|---|---|---|
| `nasa-tmr-backstep-coarse-20261026T161422Z` | 94,976 hex cells; no-slip walls started at the inlet | Passed basic topology checks, but disagreed with the NASA schematic, which shows symmetry sections before the viscous walls start at `x/H=-110`. Its profile also disagreed with the experiment. | Rejected before validation. |
| `nasa-tmr-backstep-corrected-mesh-20261026-01` | 128,256 hex cells; schematic geometry and patches; grading ratio 100 | Failed Foundation v14 mesh-quality checks: minimum cell determinant `0.000192` against the installed `0.001` threshold, and 520 faces below the installed `0.05` interpolation-weight limit. | Stopped; thresholds were kept unchanged. |
| `nasa-tmr-backstep-quality-mesh-20261026-03` | 128,256 hex cells; same geometry with conformal grading ratio 20 | Passed full topology, geometry, and quality checks. Maximum aspect ratio `71.775`; minimum determinant `0.002099`; minimum face interpolation weight `0.09179`; zero non-orthogonality; maximum skewness `6.95e-13`. | Selected for the coarse baseline. |

The quality limits are from the OpenFOAM Foundation v14 installed
`etc/caseDicts/mesh/generation/meshQualityDict` and are preserved in the case at
`cases/nasa-tmr-backstep/system/meshQualityDict`. The default limits are
software checks, not accuracy criteria. Grid convergence and comparison with
NASA's measurements are separate gates.

## Coarse baseline outcome

The selected mesh ran to iteration 12,000. The mesh check passed, and the
relative inlet/outlet flux imbalance was `4.76625e-6%` against the project's
`0.1%` pilot target. The run did **not** satisfy the declared SIMPLE residual
controls. The first lower-wall negative-to-positive skin-friction crossing was
`x/H=6.07586`, outside NASA's `6.26 ± 0.10` interval. The comparison is
provisional pending iterative convergence and a three-grid sensitivity study.
The case must not be described as validated.

Selected run logs, input hashes, flow-rate records, sampled profiles, and the
machine-readable analysis are archived under
[`run-20261026T165738Z`](run-20261026T165738Z/). The full run directory remains
in WSL; the archived files are sufficient to inspect this reported baseline,
but are not a substitute for the planned full-grid study.
