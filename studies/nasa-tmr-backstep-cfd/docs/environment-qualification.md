# P0 environment qualification

**Date:** 2026-10-26  
**Status:** passed for environment and tutorial smoke check only. NASA TMR validation has not been run.

## Environment

| Item | Observed value |
|---|---|
| WSL distribution | `OpenFOAM-UBU` (Ubuntu 24.04 LTS) |
| Solver distribution | OpenFOAM Foundation 14 |
| Ubuntu package version | `20261008` |
| Main solver executable | `/opt/openfoam14/platforms/linux64GccDPInt32Opt/bin/foamRun` |
| Mesh tools | `blockMesh`, `checkMesh` available after sourcing `/opt/openfoam14/etc/bashrc` |
| Gmsh | `4.12.1`; not used for this smoke check |

The OpenFOAM environment was sourced in each shell command. The user's shell startup file was not changed.

## Smoke check

Ran the OpenFOAM Foundation v14 packaged `incompressibleFluid/pitzDailySteady` tutorial, which the Foundation's Ubuntu instructions use as its getting-started example.

| Stage | Result |
|---|---|
| `foamVersion` | `OpenFOAM-14` |
| `foamRun -help` | completed successfully |
| `blockMesh` | completed successfully |
| `checkMesh` | `Mesh OK` |
| `foamRun` | completed; reported `SIMPLE solution converged in 285 iterations` |
| Run directory | `/root/OpenFOAM/root-14/run/cfd-workflow-assurance-pitzDaily-smoke-20261026/pitzDailySteady` |

The tutorial's solver logs are retained in that WSL run directory. The tutorial is not geometrically or physically equivalent to NASA's backward-facing-step validation case; its result is installation evidence only.

## Reproduce

From PowerShell in the project directory:

```powershell
wsl.exe -d OpenFOAM-UBU -- bash -lc '. /opt/openfoam14/etc/bashrc; mkdir -p "$FOAM_RUN/cfd-workflow-assurance-smoke"; cd "$FOAM_RUN/cfd-workflow-assurance-smoke"; cp -r "$FOAM_TUTORIALS/incompressibleFluid/pitzDailySteady" .; cd pitzDailySteady; blockMesh; checkMesh; foamRun'
```

This smoke check does not establish numerical verification or experimental validation. Those remain separate gates for the NASA TMR case.
