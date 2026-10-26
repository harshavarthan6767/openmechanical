# Coarse baseline run: 2026-10-26

This archive records the OpenFOAM Foundation v14 coarse run
`nasa-tmr-backstep-coarse-20261026T165738Z`. The solver ran to iteration
12,000 on the 128,256-cell mesh. It did not meet the declared SIMPLE residual
controls; treat all solution comparisons as provisional.

## Recorded outcomes

- `checkMesh`: passed with the case's declared mesh-quality policy.
- Relative inlet/outlet volumetric-flux imbalance: `4.76625e-6%`; project
  pilot threshold: `0.1%`.
- First lower-wall negative-to-positive skin-friction crossing:
  `x/H=6.07586`; NASA reference: `6.26 ± 0.10`. The computed point is outside
  the published interval.
- Five mean-velocity profile RMSE values and their sample counts are in
  `analysis-result.json`; they are provisional because the solve did not
  converge and the three-grid study is incomplete.

## Files

- `result.json`, `analysis-result.json`: run record and independently rerun
  project analysis.
- `input-sha256.txt`: hashes of the exact case inputs used by the runner.
- `case/system/blockMeshDict`: generated mesh dictionary named in the input
  hash manifest.
- `environment.txt`: OpenFOAM package build identifier.
- `log.blockMesh`, `log.checkMesh`, `log.foamRun`: raw generation, quality,
  and solver logs.
- `case/postProcessing/`: sampled lower-wall shear, velocity profiles, and
  inlet/outlet flux histories used by the analysis.

The original full run directory remains in the author's WSL `FOAM_RUN`
directory. This compact archive contains the files referenced by the analysis.
