# OpenMechanical execution reference

Run from the checkout, or pass `--project "$OPENMECHANICAL_PROJECT"` to `uv run`.

```bash
uv run --locked openmechanical doctor --json
uv run --locked openmechanical validate examples/mounting_bracket/problem.json --json
uv run --locked openmechanical prepare examples/mounting_bracket/problem.json --out runs/preview-new --json
uv run --locked openmechanical run examples/mounting_bracket/problem.json --out runs/solve-new --json
uv run --locked openmechanical verify examples/mounting_bracket/problem.json --out runs/verify-new --json
uv run --locked openmechanical compare examples/mounting_bracket/problem.json --thickness-mm 6 8 10 --out runs/study-new --json
```

`verify` and `compare` apply to the bracket template. Use `examples/m0_cantilever/problem.json` with `run` for the cantilever proof. Each output path must be new; inspect a failed directory before choosing another path.

## Input contract

Start from the appropriate repository example and preserve `schema_version: "1.0"`. Set values from the user's supplied data, keeping quantities explicit, e.g. `{"value": 210, "unit": "GPa"}`. The typed schema rejects unknown fields, invalid magnitudes, and unsupported analysis names. CLI `validate` checks the schema/units; command-specific execution still has narrower supported geometry and load rules.

Bracket geometry fields are `base_length`, `width`, `height`, `thickness`, and `root_radius`. A thickness plus root radius must fit within the bracket envelope, and the predefined regular stress region must remain clear of the root. Material requires `youngs_modulus` and `poisson_ratio`; `density` enables mass. The illustrative material is not certified property data.

The bracket has one `fixed` constraint on `mount_face`, and one `traction` on `loaded_pad` with direction `[0, 0, -1]`. Traction magnitude has stress units (Pa/MPa), not force units. `compare` records the baseline resultant and preserves it across thicknesses. `mesh.size` has length units; `element_order` is 2. The example sets `minimum_minsicn: 0.01`.

## Outputs and statuses

- `run`: `result.json`, original/canonical inputs, geometry and boundary manifests, preview, and `solver/` containing deck, DAT/FRD and logs.
- `verify`: `verification.json`, a frozen `study-policy.json`, and three complete `mesh-*` records.
- `compare`: `comparison.json`, `comparison-policy.json`, per-candidate verification, `report.html`, and convergence images.
- `prepare`: CAD/mesh/previews only; `analysis_status` remains `not_run`.

Read the result structure appropriate to the command. In a comparison the candidate data are in `candidates[i].verification`, and individual solves are in its `runs` list. Numerical passing requires all declared checks and convergence trends. Design remains unassessed because whole-part strength criteria and material provenance have not been established.

Common statuses: `execution_status: completed|failed`; `numerical_status: passed|failed|incomplete`; `design_status: unassessed`. Exit 0 can mean successful execution of a single numerically incomplete solve; exit 6 signals failed/incomplete required verification. Other nonzero codes are input, dependency, or execution failures; inspect the JSON/logs instead of interpreting the code as an engineering margin.

The regular stress region is fixed at x=55–75% of base length, y=20–80% of width, across the base thickness. Its conforming partition preserves physical volume across meshes. The raw global peak is retained separately and may grow at the ideal clamp. Do not claim the RMS metric certifies all locations.
