# Verification readiness — 2026-10-26

Published result snapshots and the downloadable example report are in [evidence/](evidence/README.md). Raw solver workspaces are regenerated with the repository commands rather than bundled in Git. Local run names below identify the original retained experiments.

This checkpoint provides a reproducible engineering verification workflow for a narrow linear-static scope. It is suitable for a serious engineering software demonstration and for reviewing the supplied idealized cases. It has not been qualified as a general production analysis tool or approved for design sign-off.

## Supported and measured scope

- Python 3.12, CadQuery 2.8.0, Gmsh 4.12.1, CalculiX 2.21, isotropic linear elasticity, C3D10 solids, full fixed face, constant vector traction on planar triangle6 faces.
- Filleted L-bracket template with semantic boundaries re-resolved after parameter changes; one connected mesh, complete boundary membership, duplicate/orphan node rejection, positive adaptive minimum Jacobians, and quality checks.
- Exact quadratic load integration for the supported straight-sided surfaces, with independent force and moment resultants checked before execution. Unsupported curved load triangles are rejected.
- All-node displacement and reaction coverage; all four integration-point stress tensors for every C3D10. Unknown tables, repeated records, wrong time/step/increment, nonfinite records, or truncated output fail.
- Fresh exclusive run folders, solver timeout, bounded solver mesh size, retained logs/raw outputs, input normalization, source snapshots, dependency versions, solver binary hash, and artifact checksums.
- Separate execution, scoped numerical, and design statuses. An incomplete trend produces a nonzero verification CLI exit code.

Stress extraction and averaging conventions were checked against the [CalculiX 2.21 manual](https://www.dhondt.de/ccx_2.21.pdf), sections 5.1 and 7.52. DAT stress is at integration points; FRD stress is extrapolated/averaged and is not used for the reported assessment quantity.

## Independent backend benchmarks

Evidence: `runs/backend-qualification-01/qualification.json`.

| Case | Full-field displacement relative error | Full-field stress tensor relative error | Result |
|---|---:|---:|---|
| Uniform axial patch, nu=0 | 1.050e-7 | 1.485e-13 | passed |
| Same patch rotated 30 degrees and translated | 1.445e-7 | 9.811e-8 | passed |
| Doubled axial load | 5.243e-8 | 2.282e-13 | passed |
| Cantilever bending | 0.8186% from Timoshenko | not an analytical stress benchmark | passed |

Axial reference: u = sigma*x/E, uniform stress sigma=0.5 MPa, E=210000 MPa, length=200 mm. Poisson ratio zero avoids introducing a clamp boundary-layer mismatch into this exact patch. The bending comparison uses an area integral of loaded-face displacement rather than a changing arithmetic node mean. The earlier cantilever three-mesh benchmark remains documented separately in `benchmark-results.md`.

## Bracket refinement and fair candidate comparison

Evidence: `runs/bracket-conforming-study-01/comparison.json` and its standalone `report.html`. Every thickness uses 4, 2.828427, and 2 mm meshes and **295 N total force**, with candidate traction deliberately adjusted to its changing face area.

| Thickness | Mass kg | Finest area-mean deflection mm | Regular-region RMS stress MPa | Final displacement change | Final RMS change | Scoped numerical status |
|---:|---:|---:|---:|---:|---:|---|
| 6 mm | 0.334522 | 0.03109321 | 4.11319 | 0.13382% | 0.02624% | passed |
| 8 mm | 0.433432 | 0.01375357 | 2.44903 | 0.08719% | 0.01990% | passed |
| 10 mm | 0.529202 | 0.00733963 | 1.66653 | 0.06810% | 0.01542% | passed |

Criteria were declared before solving: displacement change <=2%, regular stress change <=5%, monotonic decreasing refinement increments, force/moment balance <=0.1%, geometry/coverage checks, and applicability screens. All nine conforming runs passed the declared checks. The fixed stress region spans x=55–75% of base length, y=20–80% of width, including the base thickness.

The first exploratory study selected whole elements by centroid without a conforming partition. It correctly remained incomplete for two candidates because stress oscillated as the sampled volume changed. The improved mesh conforms to the same predeclared region boundaries. It preserves the exact sampling volume on all meshes; it does not change the solid or relax thresholds. That earlier evidence remains in `runs/bracket-qualified-study-01/`.

The regular stress metric is volume-weighted RMS von Mises from four-point integration over straight tetrahedra. Raw global peak stresses are also retained: 28.0189 / 16.0809 / 10.6339 MPa on the finest meshes. They increase with refinement and are not qualified as converged stresses at an ideal fixed boundary. The RMS region does not substitute for investigating that behavior or for assessing other failure locations.

## Software checks and release gates

36 regression tests and Ruff pass locally in the locked WSL environment. Checks include a real solver-record fixture, malformed/truncated/nonfinite/duplicate records, exact quadratic load resultants, von Mises invariants, oscillatory convergence, real process timeout/failure control flow, stale-output rejection, unit scaling/sign rejection, direction overflow handling, excessive-refinement rejection, and preservation of failed aggregate statuses. Mock process tests do not count toward numerical qualification.

The GitHub Actions workflow runs the same numerical suite and bracket study with an explicit CalculiX 2.21 version guard. It has been prepared locally; no remote CI execution is claimed. The source archive and wheel build successfully. The wheel was installed into a separate environment synchronized from uv.lock, its import path was checked under site-packages, and all four independent numerical cases passed again (`runs/wheel-qualification-final/qualification.json`). The installed-wheel bracket CLI also passed a complete three-mesh verification (`runs/wheel-bracket-e2e/`).

The installed wheel also passed an end-to-end SI versus mm/MPa replay, including displacements, regular and peak stresses, load resultant, mesh counts and solver checks. Evidence is in `runs/wheel-unit-equivalence/unit-equivalence.json`. Metric tolerances were 1e-6 relative and 1e-10 absolute; force-resultant tolerances were 1e-10. Release artifact contents and hashes are recorded by `examples/check_distribution.py` in `dist/build-verification.json`.

## What prevents production design approval

Material grade, property provenance, allowables, displacement criteria, real mounting/bolt/contact behavior, load cases and factors, manufacturing details, fatigue/buckling requirements, and experimental or independently reviewed validation are not established for the illustrative bracket. Therefore design status remains **unassessed** and no winning thickness is selected.

Imported STEP workflow, pressure loads, curved-face traction, nonlinear material/deformation, assemblies/contact, general support patterns, and general multiple-step result parsing are outside the qualified scope. Input schemas may reserve future concepts; only the documented execution subset is supported. The numerical pass is limited to the declared regular-region/displacement verification policy.

CLI: `run` completes one solve and remains numerically incomplete until refinement; `verify` runs three meshes; `compare` runs three meshes per candidate at constant resultant force. `verify`/`compare` return exit code 6 when numerical verification is incomplete or failed. Solver/input failures return nonzero and retain available evidence.
