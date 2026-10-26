# NASA TMR backward-facing-step case

This is an independently generated OpenFOAM Foundation v14 case for a
two-dimensional, steady incompressible RANS study of the Driver–Seegmiller
backward-facing step. It is not copied from the OpenCFD 2606 example.

## Baseline assumptions

- Step height `H = 1` and reference speed `Uref = 1`, so the case is
  nondimensional with `Re_H = Uref*H/nu = 36,000` and `nu = 1/36,000`.
- The domain spans `x/H = -180` to `50`, with the step at `x/H = 0`, upstream
  floor at `y/H = 0`, downstream floor at `y/H = -1`, and top wall at
  `y/H = 8`. The NASA schematic shows the viscous walls beginning at
  `x/H = -110`; the inlet and outlet extents here are explicit study choices
  based on that schematic, not coordinates copied from a NASA grid.
- A uniform velocity enters at `x/H = -180`. Symmetry patches extend along the
  upper and lower boundaries to `x/H = -110`, where no-slip walls begin. The
  lower-wall boundary layer develops for 110H before the step. Its profile at
  `x/H = -4` must be checked against TMR before treating this as equivalent to
  the reference.
- The top wall is no-slip. The step and lower wall are no-slip. The outlet is
  zero-gradient for velocity with a fixed kinematic pressure reference.
- The baseline turbulence model is OpenFOAM Foundation v14 Spalart–Allmaras.
- The mesh has one cell through a thin spanwise extrusion and empty front/back
  patches. It is 2D and hexahedral, but it is an independently generated mesh,
  not a NASA TMR coordinate grid.
- The NASA profile coordinates use the downstream-floor origin; the model uses
  `y/H=-1` at that floor, so profile comparisons shift all NASA `y/H` values by
  `-1` before interpolation.
- The geometry and upstream boundary patches follow the TMR case schematic at
  <https://tmbwg.github.io/turbmodels/backstep_val.html>. The exact inlet and
  outlet extents remain study assumptions, and this generated mesh is not one
  of NASA's coordinate grids.

These are pilot assumptions, not established matches to every experimental
boundary condition. In particular, the uniform inlet and long developing duct
must be assessed using the `x/H = -4` profile. Do not tune the inflow or model
to force agreement with a single reattachment measurement.

## Run

From the repository root inside the configured Ubuntu 24.04 WSL distribution:

```bash
bash scripts/run_case_wsl.sh coarse
```

Use `medium` and `fine` only after checking the coarse run and available memory.
Each run is copied to a fresh directory under `$FOAM_RUN`, away from the slow
Windows-mounted project filesystem. The runner preserves the generated case,
environment record, input hashes, mesh logs, solver log, and post-processing
outputs in that run directory.

## Interpretation

The NASA reference gives `x/H_reattach = 6.26 ± 0.10`. Reattachment is the
zero crossing of the lower-wall skin-friction coefficient. This experimental
uncertainty must be kept separate from iterative, spatial-discretization, and
model-form uncertainty. A solver reaching its end time is not by itself a
convergence pass; the reported quantities also need to stabilize and the
three-grid sensitivity study must be assessed before numerical status can
pass.

The run script applies OpenFOAM Foundation v14's installed mesh-quality limits
through `system/meshQualityDict` and calls `checkMesh` with `-allTopology`,
`-allGeometry`, and `-meshQuality`. These quality limits are software checks;
they do not establish solution accuracy. The mesh levels use a uniform 1.5
linear refinement ratio so a three-grid discretization study can apply the
standard Richardson/GCI formulation when the quantity is in an asymptotic
range.

To keep the `blockMesh` interfaces conformal across the symmetry-to-wall
transition, the same vertical grading ratio is used in each block column. This
also refines the symmetry section near its boundaries; it is a mesh-layout
choice, not a wall boundary condition. The current coarse mesh uses a grading
ratio of 20 toward the lower wall and its reciprocal toward the top wall.
