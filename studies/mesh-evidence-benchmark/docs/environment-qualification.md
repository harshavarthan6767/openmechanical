# Environment qualification

The v0.1 pilot ran in WSL on Ubuntu 24.04 LTS with Python 3.12.3 and these
Ubuntu package versions:

| Package | Version |
|---|---|
| `gmsh` | `4.12.1+ds1-1.1build2` |
| `python3-gmsh` | `4.12.1+ds1-1.1build2` |
| `python3-numpy` | `1:1.26.4+ds-6ubuntu1` |
| `calculix-ccx` | `2.21-1` |

The run's `protocol.json` records Gmsh, NumPy, and CalculiX versions; the study
JSON also records the solver executable hash and all baseline, generated mesh,
deck, stdout, and stderr hashes. The full raw files are in the archived run.

The same package names can be installed on Ubuntu with:

```bash
sudo apt update
sudo apt install gmsh python3-gmsh python3-numpy calculix-ccx
```

Check the package versions before comparing a rerun with this result. Exact
results may vary with solver build and platform; report those versions and
hashes rather than assuming binary identity.
