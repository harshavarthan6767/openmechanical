# Baseline meshes

These three Gmsh MSH files are copied byte-for-byte from the public OpenMechanical cantilever benchmark. Their SHA-256 hashes are recorded in `manifest.json` and verified by `scripts/run_benchmark.py` before the study starts.

| Mesh size | C3D10 elements | SHA-256 |
|---:|---:|---|
| 5.000000 mm | 2,003 | `932a32c519cafb63e72b3d71ea9119268ecb4a7c1dfbab42a016b417f81c6866` |
| 3.535534 mm | 5,195 | `bf8cd69de1b0b6fb6b79fed82a5503786696257b5cf5518c4a2e89a5668ea651` |
| 2.500000 mm | 12,990 | `96abc80839cd01e5edee46db9a6070237228e572704c76a0a9593f404dd8115b` |

Source: [`harshavarthan6767/openmechanical`](https://github.com/harshavarthan6767/openmechanical), `runs/cantilever-benchmark-01/mesh-{0,1,2}/cantilever.msh`. The project reuses these exact meshes to keep the initial samples tied to the existing analytical cantilever results. It then perturbs only nodes classified by Gmsh on the solid volume; nodes on the CAD boundary remain fixed.

The earlier local direct-OCC smoke mesh was superseded because it did not match the byte-pinned OpenMechanical baseline. It is retained under the ignored local `runs/` folder as a rejected prototype.
