import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from openmechanical.bracket import prepare_bracket_mesh
from openmechanical.contracts import validate_problem
from openmechanical.solver import Mesh, assemble_traction, parse_dat, solve, von_mises
from openmechanical.verification import aggregate_numerical_status, convergence

FIXTURE = Path(__file__).parent / "fixtures/ccx221_excerpt.dat"


def test_real_solver_fixture_has_exact_expected_records():
    data = parse_dat(FIXTURE, {1, 2}, {1, 2}, {903})
    assert data["rf"][1][2] == pytest.approx(1.840020)
    assert len(data["s"]) == 4


@pytest.mark.parametrize(
    "mutation",
    [
        lambda s: s[: s.rfind("       903   4")],
        lambda s: s.replace("1.265642E+01", "nan"),
        lambda s: s.replace("0.1000000E+01", "0.2000000E+01"),
        lambda s: s.replace("S T E P       1", "S T E P       2"),
        lambda s: s.replace("903   4", "903   3"),
        lambda s: s.replace("INCREMENT     1", "INCREMENT     2"),
        lambda s: s.replace("set EALL", "set WRONG"),
        lambda s: s + " malformed\n",
    ],
)
def test_corrupt_solver_results_cannot_pass(tmp_path, mutation):
    path = tmp_path / "damaged.dat"
    path.write_text(mutation(FIXTURE.read_text()))
    with pytest.raises(ValueError):
        parse_dat(path, {1, 2}, {1, 2}, {903})


def triangle_mesh():
    xyz = np.array(
        [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0.5, 0, 0], [0.5, 0.5, 0], [0, 0.5, 0]], dtype=float
    )
    return Mesh(dict(enumerate(xyz, 1)), {}, {}, set(), [(1, 2, 3, 4, 5, 6)], {})


def test_quadratic_traction_matches_analytic_force_and_moment():
    mesh = triangle_mesh()
    traction = np.array([2.0, -3.0, 4.0])
    loads, info = assemble_traction(mesh, traction)
    np.testing.assert_allclose(info["force_N"], 0.5 * traction, atol=1e-14)
    np.testing.assert_allclose(
        info["moment_Nmm"], np.cross([1 / 3, 1 / 3, 0], 0.5 * traction), atol=1e-14
    )
    for n in (1, 2, 3):
        np.testing.assert_allclose(loads[n], 0, atol=1e-14)
    for n in (4, 5, 6):
        np.testing.assert_allclose(loads[n], traction / 6, atol=1e-14)


def test_curved_load_face_is_rejected_instead_of_integrated_as_flat():
    mesh = triangle_mesh()
    mesh.coordinates[4][2] = 0.1
    with pytest.raises(ValueError, match="curved"):
        assemble_traction(mesh, np.array([0.0, 0.0, 1.0]))


def test_von_mises_invariants():
    assert von_mises([10, 10, 10, 0, 0, 0]) == 0
    assert von_mises([-10, 0, 0, 0, 0, 0]) == 10
    assert von_mises([0, 0, 0, 10, 0, 0]) == pytest.approx(10 * np.sqrt(3))


def test_similar_values_do_not_pass_oscillatory_or_worsening_refinement():
    assert convergence([1, 1.01, 1.005], 0.02)["status"] == "incomplete"
    assert convergence([1, 1.001, 1.003], 0.02)["status"] == "incomplete"
    assert convergence([1, 1.01], 0.02)["status"] == "incomplete"
    assert convergence([1, 1.01, 1.012], 0.02)["status"] == "passed"


@pytest.mark.skipif(os.name != "posix", reason="solver execution lane is Linux/WSL")
@pytest.mark.parametrize(
    "behavior,exception,error",
    [
        ("import time; time.sleep(5)", subprocess.TimeoutExpired, "solver_timeout"),
        ("print('Job finished'); raise SystemExit(2)", RuntimeError, "solver_failure"),
    ],
)
def test_solver_failure_retains_evidence(tmp_path, monkeypatch, behavior, exception, error):
    executable = tmp_path / "fake-ccx"
    executable.write_text(f"#!{sys.executable}\n{behavior}\n")
    executable.chmod(0o755)
    monkeypatch.setattr("openmechanical.solver.shutil.which", lambda _: str(executable))
    out = tmp_path / "run"
    with pytest.raises(exception):
        solve(triangle_mesh(), 210000.0, 0.3, np.array([0.0, 0.0, 1.0]), out, timeout=0.2)
    assert json.loads((out / "failure.json").read_text())["error"] == error
    assert (out / "solver.stdout.txt").exists()
    assert not (out / "result.json").exists()


def test_stale_run_cannot_be_reused(tmp_path):
    out = tmp_path / "run"
    out.mkdir()
    marker = out / "result.json"
    marker.write_text('"old result"')
    with pytest.raises(FileExistsError):
        solve(triangle_mesh(), 210000.0, 0.3, np.array([0.0, 0.0, 1.0]), out)
    assert marker.read_text() == '"old result"'


def test_failed_or_missing_candidates_cannot_be_upgraded_to_passed():
    assert aggregate_numerical_status([]) == "incomplete"
    assert aggregate_numerical_status(["passed", "incomplete"]) == "incomplete"
    assert aggregate_numerical_status(["passed", "failed"]) == "failed"
    assert aggregate_numerical_status(["passed", "passed"]) == "passed"


def test_extreme_refinement_is_rejected_before_meshing(tmp_path):
    fixture = Path(__file__).parents[1] / "examples/mounting_bracket/problem.json"
    problem = json.loads(fixture.read_text())
    problem["mesh"]["size"] = {"value": 1e-200, "unit": "mm"}
    with pytest.raises(ValueError, match="budget"):
        prepare_bracket_mesh(validate_problem(problem), tmp_path / "excessive")
    assert not (tmp_path / "excessive/bracket.step").exists()
