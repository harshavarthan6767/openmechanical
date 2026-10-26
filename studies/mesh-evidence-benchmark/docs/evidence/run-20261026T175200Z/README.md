# Mesh-response pilot evidence

This is the archived output for the frozen protocol v0.1 run. It covers 30
predeclared attempts: three byte-pinned baseline meshes and 27 controlled
interior-node distortions across three amplitudes and three seeds.

## Outcomes

- 30 of 30 attempts are accounted for; 29 ran CalculiX and passed the
  equilibrium checks. One `5 mm`, `0.01h`, seed-23 mesh was invalid and was
  retained without a solver run. It preserved all boundary nodes; its minimum
  SICN was `-0.00709`, minimum SJ `-0.09298`, and minimum determinant Jacobian
  `-1.62007`.
- All 29 solved samples had tip-deflection errors from `0.7147%` to `0.8292%`
  against the Timoshenko estimate, below the project `2%` target. Maximum
  relative force and moment residuals were `3.824e-6` and `2.117e-7`.
- The minimum-SICN probes `0.05`, `0.10`, and `0.20` falsely rejected `1`, `9`,
  and `9` of the 29 response-accurate meshes, respectively. No response-error
  failure occurred, so zero false-safe cases do not demonstrate that these
  probes detect an inaccurate result.

## Files

- `report.md`: all 30 sample rows and threshold counts.
- `benchmark.json`: detailed per-sample metrics, solver and input hashes, and
  declared statuses.
- `protocol.json`: exact programmatic case, measures, thresholds, mesh inputs,
  and tool versions.
- `raw-run.zip`: full raw run directory, including generated meshes, decks,
  CalculiX `.dat` and `.frd` files, stdout/stderr, and each sample's JSON.
- `SHA256SUMS.txt`: hashes for the top-level evidence files.

The run is complete for this declared pilot because every planned sample is
either solved or explicitly recorded as an invalid mesh. It does not establish
a generally useful mesh-quality cutoff or validate any engineering design.
