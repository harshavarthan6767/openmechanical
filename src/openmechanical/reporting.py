"""Standalone HTML evidence reports generated from retained solver results."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

import matplotlib

from .solver import sha256, write_json


def _image(path):
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def write_comparison_report(root: Path, summary: dict) -> None:
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(1, 3, figsize=(15, 4.4))
    for candidate in summary["candidates"]:
        runs = candidate["verification"]["runs"]
        counts = [r["mesh"]["elements"] for r in runs]
        curves = [
            [abs(r["result"]["area_mean_loaded_displacement_mm"][2]) for r in runs],
            [r["stress"]["roi_rms_von_mises_MPa"] for r in runs],
            [r["stress"]["raw_peak_von_mises_MPa"] for r in runs],
        ]
        for axis, values in zip(axes, curves, strict=True):
            axis.plot(counts, values, "o-", label=f"{candidate['thickness_mm']:g} mm")
    for axis, title, unit in zip(
        axes,
        ("Loaded-face area mean", "Fixed-region RMS von Mises", "Raw global peak (not qualified)"),
        ("Deflection [mm]", "Stress [MPa]", "Stress [MPa]"),
        strict=True,
    ):
        axis.set_xscale("log")
        axis.set_xlabel("C3D10 elements")
        axis.set_ylabel(unit)
        axis.set_title(title)
        axis.grid(alpha=0.25)
        axis.legend()
    figure.tight_layout()
    plot = root / "convergence.png"
    figure.savefig(plot, dpi=160)
    figure.savefig(root / "convergence.svg")
    plt.close(figure)

    overview, histories = [], []
    for index, candidate in enumerate(summary["candidates"]):
        verification = candidate["verification"]
        final = verification["runs"][-1]
        mass = final["mass_kg"]
        values = [
            f"{candidate['thickness_mm']:g}",
            verification["numerical_status"],
            f"{mass:.6f}" if mass is not None else "not supplied",
            f"{abs(final['result']['area_mean_loaded_displacement_mm'][2]):.8f}",
            f"{final['stress']['roi_rms_von_mises_MPa']:.5f}",
            f"{final['stress']['raw_peak_von_mises_MPa']:.5f}",
            f"{100 * verification['displacement_convergence']['relative_changes'][-1]:.5f}%",
            f"{100 * verification['stress_convergence']['relative_changes'][-1]:.5f}%",
        ]
        overview.append("<tr>" + "".join(f"<td>{html.escape(v)}</td>" for v in values) + "</tr>")
        rows = []
        sizes = json.loads((root / f"candidate-{index}/study-policy.json").read_text())[
            "mesh_sizes_m"
        ]
        for mesh_index, (size, result) in enumerate(zip(sizes, verification["runs"], strict=True)):
            values = [
                f"{size * 1000:.6g}",
                str(result["mesh"]["elements"]),
                f"{abs(result['result']['area_mean_loaded_displacement_mm'][2]):.9f}",
                f"{result['stress']['roi_rms_von_mises_MPa']:.7f}",
                f"{result['force_residual_relative']:.3e}",
                f"{result['moment_residual_relative']:.3e}",
            ]
            cells = "".join(f"<td>{html.escape(v)}</td>" for v in values)
            link = f"candidate-{index}/mesh-{mesh_index}/result.json"
            rows.append(f'<tr>{cells}<td><a href="{link}">Run evidence</a></td></tr>')
        histories.append(
            f"<h3>{candidate['thickness_mm']:g} mm thickness</h3><table><tr>"
            "<th>Mesh mm</th><th>Elements</th><th>Deflection mm</th><th>RMS stress MPa</th>"
            "<th>Force residual</th><th>Moment residual</th><th>Evidence</th></tr>"
            + "".join(rows)
            + "</table>"
        )
    boundary = root / "candidate-0/mesh-0/geometry/boundary-preview.png"
    document = f"""<!doctype html><html lang="en"><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>OpenMechanical bracket verification</title>
    <style>body{{font:16px system-ui;max-width:1400px;margin:32px auto;padding:20px;color:#17202a}}
    table{{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}}
    th,td{{border:1px solid #d6dce2;padding:10px;text-align:left}}
    th{{background:#eff4f9}}img{{max-width:100%;height:auto}}
    .status{{padding:16px;background:#fff2cf;border-left:5px solid #bc8500}}
    .scroll{{overflow-x:auto}}p{{max-width:1000px;line-height:1.55}}</style>
    <h1>Mounting bracket verification</h1>
    <p class="status"><strong>Numerical status: {html.escape(summary["numerical_status"])}.</strong>
    Scope: equilibrium, geometry, loaded-face displacement and regular-region stress sensitivity.
    <strong>Design status: unassessed. No winning design selected.</strong></p>
    <p>Each thickness uses three systematically refined quadratic tetrahedral meshes and
    the same total force of {summary["total_force_N"]:.9g} N. Candidate traction is explicitly
    adjusted for its load-face area. The rear mounting face is fully fixed. Material values
    are supplied illustrative inputs; allowables and design criteria have not been established.</p>
    <div class="scroll"><table><tr><th>Thickness mm</th><th>Numerical status</th><th>Mass kg</th>
    <th>Mean deflection mm</th><th>Regular RMS MPa</th><th>Raw peak IP MPa</th>
    <th>Final deflection change</th><th>Final RMS change</th></tr>
    {"".join(overview)}</table></div>
    <h2>Refinement history</h2><img alt="Three-mesh convergence histories" src="{_image(plot)}">
    <p>The global raw peak is retained with its element and integration-point ID in each result.
    It is not a qualified stress at an ideal clamp.
    The regular-region RMS does not replace it.</p>
    <h2>Boundary conditions</h2><img style="max-width:760px" alt="Blue fixed face, red loaded face"
    src="{_image(boundary)}">
    <h2>Acceptance policy</h2>
    <p>Final changes must be ≤2% in loaded-face displacement and ≤5% in regular-region RMS stress,
    with monotonic, decreasing increments. All force and moment residuals must be ≤0.1%,
    and geometry, coverage, warning and applicability screens must pass.
    Failed or oscillatory studies remain failed or incomplete.</p>
    <p>Stress tensors are read at all four C3D10 integration points, rather than from averaged
    nodal contours. The fixed stress region spans x=55–75% of base length, y=20–80% of width,
    and the base thickness. A conforming internal partition preserves the same physical sampling
    volume across meshes without changing the solid. RMS uses volume-weighted four-point
    quadrature in affine tetrahedra. It does not assess every possible failure location.</p>
    <p>Displacement is integrated over the loaded face using quadratic shape functions.
    Linear-displacement and elastic-strain screens do not establish material strength.
    Experimental validation and whole-part design approval remain outstanding.</p>
    <h2>Run evidence</h2>{"".join(histories)}
    <p><a href="comparison.json">Full results</a> ·
    <a href="comparison-policy.json">Load policy</a> ·
    <a href="report-provenance.json">Report provenance</a></p></html>"""
    (root / "report.html").write_text(document, encoding="utf-8")
    write_json(
        root / "report-provenance.json",
        {
            "generator_sha256": sha256(Path(__file__)),
            "comparison_sha256": sha256(root / "comparison.json"),
            "report_sha256": sha256(root / "report.html"),
            "convergence_png_sha256": sha256(plot),
        },
    )
