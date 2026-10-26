# Mesh response pilot report

**Study status:** complete_for_declared_case

This report is limited to one idealized linear-elastic cantilever, Gmsh, C3D10 elements, and CalculiX. It is not a general mesh acceptance rule or a design validation.

## Attempt accounting

- Planned and recorded attempts: 30 / 30
- Solver-completed samples: 29
- Equilibrium checks passed: 29
- Invalid meshes retained without solving: 1
- Solver or unclassified failures: 0
- Responses above the 2% project target: 0

## Samples

| Size (mm) | Distortion | Seed | Elements | Min SICN | Tip error (%) | Force residual | Moment residual | Status |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 5 | 0 | 11 | 2003 | 0.08164 | 0.8189 | 4.269e-07 | 7.253e-08 | completed |
| 5 | 0.0025 | 11 | 2003 | 0.07843 | 0.8193 | 1.491e-06 | 3.925e-08 | completed |
| 5 | 0.0025 | 23 | 2003 | 0.05956 | 0.8195 | 1.063e-06 | 1.208e-07 | completed |
| 5 | 0.0025 | 37 | 2003 | 0.07419 | 0.8194 | 1.431e-06 | 1.120e-07 | completed |
| 5 | 0.005 | 11 | 2003 | 0.07517 | 0.8211 | 1.930e-07 | 9.569e-08 | completed |
| 5 | 0.005 | 23 | 2003 | 0.03740 | 0.8215 | 1.313e-06 | 6.160e-08 | completed |
| 5 | 0.005 | 37 | 2003 | 0.06680 | 0.8213 | 4.145e-07 | 4.184e-08 | completed |
| 5 | 0.01 | 11 | 2003 | 0.06851 | 0.8286 | 8.517e-07 | 8.466e-08 | completed |
| 5 | 0.01 | 23 | — | — | — | — | — | invalid_mesh |
| 5 | 0.01 | 37 | 2003 | 0.05217 | 0.8292 | 3.219e-06 | 2.117e-07 | completed |
| 3.536 | 0 | 11 | 5195 | 0.30488 | 0.7468 | 5.718e-07 | 4.705e-08 | completed |
| 3.536 | 0.0025 | 11 | 5195 | 0.28651 | 0.7471 | 1.224e-06 | 3.270e-08 | completed |
| 3.536 | 0.0025 | 23 | 5195 | 0.29350 | 0.7472 | 5.821e-07 | 3.970e-08 | completed |
| 3.536 | 0.0025 | 37 | 5195 | 0.29913 | 0.7475 | 7.892e-07 | 8.832e-08 | completed |
| 3.536 | 0.005 | 11 | 5195 | 0.26628 | 0.7484 | 3.824e-06 | 1.994e-07 | completed |
| 3.536 | 0.005 | 23 | 5195 | 0.28047 | 0.7485 | 5.140e-07 | 2.386e-08 | completed |
| 3.536 | 0.005 | 37 | 5195 | 0.29109 | 0.7490 | 4.766e-07 | 7.042e-08 | completed |
| 3.536 | 0.01 | 11 | 5195 | 0.22563 | 0.7535 | 1.820e-06 | 9.472e-08 | completed |
| 3.536 | 0.01 | 23 | 5195 | 0.23682 | 0.7538 | 5.615e-07 | 8.229e-08 | completed |
| 3.536 | 0.01 | 37 | 5195 | 0.25746 | 0.7547 | 9.828e-07 | 7.415e-08 | completed |
| 2.5 | 0 | 11 | 12990 | 0.29639 | 0.7147 | 5.378e-07 | 4.324e-08 | completed |
| 2.5 | 0.0025 | 11 | 12990 | 0.28944 | 0.7150 | 2.602e-07 | 1.416e-08 | completed |
| 2.5 | 0.0025 | 23 | 12990 | 0.28356 | 0.7150 | 5.744e-07 | 3.106e-08 | completed |
| 2.5 | 0.0025 | 37 | 12990 | 0.28423 | 0.7150 | 5.121e-07 | 1.972e-08 | completed |
| 2.5 | 0.005 | 11 | 12990 | 0.26765 | 0.7157 | 9.201e-07 | 6.650e-08 | completed |
| 2.5 | 0.005 | 23 | 12990 | 0.26413 | 0.7157 | 3.333e-07 | 1.813e-08 | completed |
| 2.5 | 0.005 | 37 | 12990 | 0.26213 | 0.7159 | 1.280e-07 | 8.758e-09 | completed |
| 2.5 | 0.01 | 11 | 12990 | 0.21933 | 0.7186 | 3.459e-07 | 2.747e-08 | completed |
| 2.5 | 0.01 | 23 | 12990 | 0.22509 | 0.7187 | 9.482e-07 | 4.073e-08 | completed |
| 2.5 | 0.01 | 37 | 12990 | 0.21757 | 0.7190 | 3.998e-07 | 7.795e-09 | completed |

## Fixed threshold probes

| minSICN minimum | False safe | False reject | Solved samples |
|---:|---:|---:|---:|
| 0.05 | 0 | 1 | 29 |
| 0.10 | 0 | 9 | 29 |
| 0.20 | 0 | 9 | 29 |

These threshold values are project probes, not universal engineering limits. Correlations are descriptive and do not support generalization beyond the declared case.

All solver-completed samples met the 2% response target. Therefore, zero false-safe cases do not show that any minSICN threshold detects unacceptable response error; this sample did not contain a response failure to detect.
