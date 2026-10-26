# NASA TMR experimental reference data

These tabulated files come from the NASA Turbulence Modeling Resource (TMR)
`Backstep_validation` directory. TMR describes them as Driver and Seegmiller's
experimental bottom-wall skin friction, wall pressure, and velocity/turbulence
profiles for the two-dimensional backward-facing-step case.

## Provenance

- Source repository: <https://github.com/TMBWG/turbmodels/tree/main/Backstep_validation>
- Case page: <https://tmbwg.github.io/turbmodels/backstep_val.html>
- Repository revision: `main` as fetched on 2026-10-26; the source files are
  pinned below by Git blob SHA because this checkout was downloaded through the
  GitHub contents API.
- Source repository license: CC0 1.0 Universal; see `LICENSE-CC0-1.0.txt` and
  <https://github.com/TMBWG/turbmodels/blob/main/LICENSE>.

| Local file | TMR Git blob SHA | Local SHA-256 | Contents |
|---|---|---|---|
| `cf.exp.dat` | `3f862df5611cf07c767d375c32c18e67116055da` | `CD9B6434B7956BC58E859DE6AF654CD7F891E25303BABF1DD8633D6C58F74276` | Bottom-wall skin-friction coefficient and reported error |
| `cp.expnew.dat` | `357c307c030f9cbbc31fadd7669185e13ebb3468` | `2B3EC9F8D8025B958D6DDCF6767DAAF3C93083D45EF350A8CF9C4B46F93A882A` | Wall-pressure coefficient |
| `profiles.exp.dat` | `45a839629ee4fd444a80b3833eebedcda019786e` | `23E8B44DB52BFC36C66AF6B743A4080C34F0165EB213A3DB29C0914E12CF598D` | Mean velocity and turbulence statistics at several streamwise stations |

The files are preserved as source data, not altered or re-digitized. Confirm the
hashes with `Get-FileHash data/reference/*.dat -Algorithm SHA256` on Windows or
`sha256sum data/reference/*.dat` on Linux before using them.

The NASA data are experimental reference measurements. Their uncertainty is
not the numerical uncertainty of this reproduction. Results must report those
separately and must describe differences in geometry, inflow, wall conditions,
and turbulence model before making a validation claim.
