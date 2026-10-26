# Cantilever benchmark results

Measured on 2026-10-26 with the installed CalculiX 2.21 workflow. This is an analytical displacement and equilibrium benchmark, not a bracket design assessment.

The independently computed Timoshenko reference is 0.763390476 mm, using a 200 x 20 x 10 mm beam, E=210 GPa, nu=0.3, a 100 N end load, and shear factor 5/6. The Euler-Bernoulli result is 0.761904762 mm. The analytical formula is documented in the [TU Delft Timoshenko beam exercise](https://oit.tudelft.nl/Finite-Elements-in-CEG/main/structural_linear/Exercises/pyjive_timoshenko.html).

| Mesh size (mm) | C3D10 elements | Deflection (mm) | Timoshenko difference | Change from preceding mesh |
|---:|---:|---:|---:|---:|
| 5.0000 | 2,003 | 0.757138981 | 0.8189% | — |
| 3.5355 | 5,195 | 0.757689427 | 0.7468% | 0.07265% |
| 2.5000 | 12,990 | 0.757934421 | 0.7147% | 0.03232% |

All three runs met the previously specified 2% analytical displacement target and 0.1% force/moment balance targets. Worst normalized force residual was 5.718e-7; worst moment residual was 7.253e-8. The final displacement change was below the 2% mesh sensitivity target, and refinement increments were monotonic and decreasing.

**Passed scope:** cantilever displacement and equilibrium. This cantilever benchmark does not establish stress convergence or physical validation. The separate bracket verification is described in [professional-readiness.md](professional-readiness.md). The actual 3D clamp and end-face deformation differ from beam theory; refinement need not eliminate the analytical difference. This earlier benchmark uses an arithmetic mean over loaded-end nodes; the hardened bracket/backend adapter uses an area integral.

Reproduce in WSL from the project directory:

```bash
uv run --no-sync python examples/m0_cantilever/benchmark.py --out runs/cantilever-benchmark-new
```

Choose a new output directory; the runner refuses to overwrite existing evidence. The frozen thresholds are written to `policy.json` before any solve. Raw solver evidence, exact inputs, CLI logs, per-run summaries, and aggregate `benchmark.json` are retained under `runs/cantilever-benchmark-01/`. This benchmark does not alter the individual runs' conservative full-verification status.
