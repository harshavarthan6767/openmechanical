# Pilot protocol v0.1 — controlled mesh distortion on a 3D cantilever

**Status:** frozen protocol; execution status is reported in the README and generated run artifacts. A revised one-sample `0.01h` smoke preceded the fixed study and is excluded from its sample count.  
**Decision addressed:** whether the current OpenMechanical minimum-SICN mesh guard is a useful screen for a specified tip-deflection accuracy target on its verified cantilever case.

## Toolchain and physical case

- Geometry: rectangular beam, `L=200 mm`, `b=20 mm`, `h=10 mm`.
- Material: isotropic linear elastic, `E=210000 MPa`, `ν=0.3`.
- Boundary conditions: full fixed support at one end, uniform traction over the opposite end face.
- Load: total resultant `100 N` in the negative z direction.
- Element: second-order tetrahedra, CalculiX `C3D10`.
- Toolchain: pinned C3D10 meshes from OpenMechanical, Gmsh `4.12.1` for quality extraction and controlled perturbation, project deck writer, CalculiX `2.21`.
- Independent reference: Timoshenko beam estimate `0.763390476190476 mm` for the mean loaded-end z displacement. It is an analytical engineering approximation for the rectangular beam, not a 3D exact solution or experimental validation.
- Primary response: mean loaded-end z displacement.
- Response error: `abs(FEA - Timoshenko) / abs(Timoshenko)`. A response passes the project target if relative error is at most `2%`, matching the existing cantilever benchmark policy.
- Equilibrium controls: integrated load, net force residual, and net moment residual. Use the existing OpenMechanical policies and retain raw solver evidence.

## Mesh sample design

Three target sizes are the existing baseline: `5.0`, `5/sqrt(2)`, and `2.5 mm`. For each size:

1. Start from the byte-pinned meshes listed in [the baseline mesh manifest](../data/base-meshes/manifest.json); keep each original mesh as the zero-distortion baseline.
2. Generate controlled variants by perturbing only mesh nodes classified inside the volume, with displacement amplitude `0.0025h`, `0.005h`, and `0.01h` times the requested target size. A separate calibration attempt at `0.05h` produced an inverted element (`minDetJac < 0`) and was rejected before the fixed pilot protocol; its evidence is retained locally.
3. Use three predeclared seeds per nonzero amplitude. Keep all CAD-boundary nodes fixed so the model boundary, support faces, and loaded face remain unchanged.
4. This gives `3 × (1 baseline + 3 amplitudes × 3 seeds) = 30` planned mesh samples. Invalid or inverted meshes are retained as failed mesh-generation samples and are not solved.
5. Reject a perturbation only for a predeclared reason: boundary moved beyond `1e-10 mm`, non-finite node coordinates, or minimum signed quality `<= 0`. Record each rejection with the seed, amplitude, and metric values available.

## Mesh measures and threshold probes

For each valid C3D10 mesh, record per-element values and mesh-level minimum, 5th percentile, median, and 95th percentile for:

- Gmsh `minSICN` (primary shape-quality measure);
- Gmsh `minSJ` (secondary signed-Jacobian measure);
- Gmsh `minDetJac` (validity/Jacobian measure).

Store mesh size, node and element counts, the hash of the moved mesh, seed, amplitude, and all Gmsh settings. The primary gate under study is minimum `minSICN`; analyze three project-defined threshold probes: `0.05`, `0.10`, and `0.20`. These are experimental policy values, not universal or vendor-endorsed acceptance limits.

For each threshold, count:

- **False safe:** the mesh passes the `minSICN` threshold but tip-displacement error exceeds 2%.
- **False reject:** the mesh fails the `minSICN` threshold but tip-displacement error is at most 2%.

Also report mesh rejection and solver failure rates. Report per-target-size results and the pooled count separately. Use descriptive correlation only; the designed 30-run sample does not support population-wide claims.

## Provenance and controls

- Freeze protocol and code hash before generating the perturbation set.
- Produce meshes in fresh output directories with deterministic seeds.
- Hash each source spec, mesh, CalculiX deck, solver executable, and result.
- Preserve raw CalculiX stdout, stderr, `.dat`, `.frd`, and input deck for each solved case.
- Keep geometry, load, support, material, element family, solver, and result extraction fixed while varying target size and controlled interior distortion.
- Report all invalid meshes, non-convergence, and failed runs. Do not change the mesh policy or error threshold after examining results.

## Project and release plan

- **Owner:** Harsh (project owner); Codex implementation support under the user's direction.
- **Estimated effort:** 16–24 focused engineering hours for mesh perturbation, extraction, analysis, and documentation. This is a planning estimate, not a recorded commitment.
- **Schedule:** one working week after WSL access is available; first deliverable is the 30-case pilot report.
- **External software cost:** `$0` planned; use the already installed open-source toolchain and local hardware. Hardware/runtime cost is not estimated.
- **Opportunity cost:** defer a separate parametric-CAD feature until this pilot establishes whether its measurement is useful.
- **Code license:** MIT, consistent with the parent OpenMechanical source. Generated meshes, metrics, and results are project-generated; upstream software and reference sources keep their own terms.
- **Reliance limits:** educational and tool-evaluation evidence for one idealized linear-elastic cantilever only; no design approval, safety finding, certification, or general acceptance rule.

## Exit criteria

Publish the pilot only if all 30 samples are either solved or explicitly accounted for; baseline and distorted runs are reproducible; equilibrium checks are reported; false-safe and false-reject counts are computed for all three fixed thresholds; the independent reference and limitations are clear; and a literature review identifies a specific unmeasured comparison. If the result only repeats existing work without a useful decision, publish the replication honestly or stop the project instead of claiming novelty.
