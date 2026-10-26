# Implementation plan

## Decision gate

The Court rejected the broad proposal 12–0. This plan narrows it to the one-case pilot in [protocol v0.1](protocol-v0.1.md). The original verdict remains unchanged and does not itself assess the revised pilot. Do not treat the pilot as novel or technically validated until the literature and execution gates are met.

## P0 — implement and qualify the fixed cantilever protocol

1. Reuse the existing OpenMechanical cantilever case and CalculiX adapter; do not create a second solver workflow.
2. Generate perturbed variants of the three existing mesh sizes using fixed interior-node seeds and amplitudes from protocol v0.1.
3. Confirm that only volume-interior nodes move and all mesh-quality values are finite.
4. Freeze the code and protocol hashes before the 30-case execution.
5. Use the existing analytical Timoshenko estimate and 2% tip-displacement tolerance; keep this analytical estimate distinct from physical validation.

**Gate:** met for the recorded protocol run. The exact baselines reproduce the existing results; the deterministic perturbation set records all 30 planned sample attempts.

## P1 — evaluate quality measures against the measured response

1. Record per-element `minSICN`, `minSJ`, and `minDetJac` with minimum, 5th, 50th, and 95th percentiles.
2. Apply the fixed minSICN threshold probes 0.05, 0.10, and 0.20 from protocol v0.1.
3. Calculate tip displacement, error against Timoshenko, equilibrium residuals, and false-safe/false-reject counts.
4. Preserve every rejected mesh and failed solver run.

**Gate:** met for this declared case. All 30 attempts are accounted for, with 29 equilibrium-passing solver results and one explicitly retained invalid mesh. The report and JSON include sample hashes and statuses.

## P2 — make the go/no-go decision

1. Report results by mesh size and perturbation level; do not pool away the invalid mesh.
2. Re-read the literature and existing benchmark suites for the exact minSICN-to-tip-deflection decision.
3. Treat v0.1 as a negative/inconclusive screening result: all 29 solved cases met the 2% response target, so false-safe detection was not tested; probes 0.10 and 0.20 each rejected 9 accurate cases.
4. Do not recommend a quality cutoff. Any follow-up must use a new prospectively frozen protocol that deliberately spans response errors around and above 2%, and should include another geometry or response before making a broader claim.

**Gate:** no-go for a general mesh acceptance rule. The measured one-case result supports only the limited finding that the tested thresholds reject some accurate meshes and that this sample cannot evaluate detection of inaccurate responses.

The separate Court review of the cutoff recommendation returned **GUILTY, 9 to 3**. Its written finding says not to recommend a tested cutoff as reliable on this record. A future proposal needs solved cases on both sides of the 2% response limit and an explicit cost comparison for false rejections.

## P3 — publish with bounded claims

1. Publish protocol, scripts, environment versions, raw compact evidence, and machine-readable results.
2. Keep the parent repo's MIT code license; generate original benchmark output and preserve upstream terms.
3. Describe the scope as one fixed OpenMechanical cantilever configuration.
4. Keep design approval, safety, and broad solver reliability outside the claim.

**Gate:** the reproducibility command and artifacts work from a clean checkout before the study is published.

## Candidate CLI result schema

```json
{
  "schema": "mesh-response-benchmark.result/0.1",
  "case_id": "",
  "mesh_id": "",
  "solver": {},
  "mesh_generator": {},
  "element_family": "",
  "quality_metrics": {},
  "responses": {},
  "reference_errors": {},
  "equilibrium_checks": {},
  "execution_status": "completed|failed|incomplete",
  "input_hashes": {},
  "evidence_paths": []
}
```

The final numerical status is not inferred from solver exit code or mesh-quality thresholds alone.
