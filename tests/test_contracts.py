import pytest
from pydantic import ValidationError

from openmechanical.contracts import validate_problem
from openmechanical.units import canonical_problem_si, validate_problem_units


def valid_problem():
    return {
        "schema_version": "1.0",
        "name": "axial coupon",
        "analysis": "linear_static",
        "geometry": {
            "kind": "box",
            "length": {"value": 100, "unit": "mm"},
            "width": {"value": 10, "unit": "mm"},
            "height": {"value": 5, "unit": "mm"},
        },
        "material": {
            "name": "test steel",
            "youngs_modulus": {"value": 210, "unit": "GPa"},
            "poisson_ratio": 0.3,
            "density": {"value": 7850, "unit": "kg/m^3"},
            "allowable_stress": {"value": 250, "unit": "MPa"},
        },
        "loads": [
            {
                "kind": "traction",
                "region": "end",
                "magnitude": {"value": 1, "unit": "MPa"},
                "direction": [1, 0, 0],
            }
        ],
        "constraints": [{"kind": "fixed", "region": "base"}],
        "mesh": {"element_order": 2, "size": {"value": 2, "unit": "mm"}},
    }


def test_accepts_complete_explicit_problem_and_units():
    problem = validate_problem(valid_problem())
    validate_problem_units(problem)
    assert problem.material.youngs_modulus.value == 210


def test_canonical_problem_serializes_quantities_in_si():
    canonical = canonical_problem_si(validate_problem(valid_problem()))
    assert canonical["geometry"]["length"] == {"value": 0.1, "unit": "m"}
    assert canonical["material"]["youngs_modulus"] == {"value": 210e9, "unit": "Pa"}
    assert canonical["loads"][0]["magnitude"] == {"value": 1e6, "unit": "Pa"}
    assert canonical["mesh"]["size"] == {"value": 0.002, "unit": "m"}
    validate_problem_units(validate_problem(canonical))


def test_bracket_geometry_contract_converts_units_and_checks_envelope():
    data = valid_problem()
    data["geometry"] = {
        "kind": "mounting_bracket",
        "base_length": {"value": 80, "unit": "mm"},
        "width": {"value": 50, "unit": "mm"},
        "height": {"value": 60, "unit": "mm"},
        "thickness": {"value": 6, "unit": "mm"},
        "root_radius": {"value": 15, "unit": "mm"},
    }
    problem = validate_problem(data)
    validate_problem_units(problem)
    assert canonical_problem_si(problem)["geometry"]["thickness"] == {"value": 0.006, "unit": "m"}

    data["geometry"]["thickness"] = {"value": 50, "unit": "mm"}
    with pytest.raises(ValueError, match="thickness plus root_radius"):
        validate_problem_units(validate_problem(data))


def test_rejects_unknown_fields():
    data = valid_problem()
    data["shell_command"] = "rm -rf /"
    with pytest.raises(ValidationError):
        validate_problem(data)


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_rejects_nonpositive_or_nonfinite_quantity(value):
    data = valid_problem()
    data["geometry"]["length"]["value"] = value
    with pytest.raises(ValidationError):
        validate_problem(data)


def test_rejects_zero_traction_direction():
    data = valid_problem()
    data["loads"][0]["direction"] = [0, 0, 0]
    with pytest.raises(ValidationError):
        validate_problem(data)


def test_rejects_dimensionally_wrong_length_unit():
    data = valid_problem()
    data["geometry"]["length"]["unit"] = "MPa"
    problem = validate_problem(data)
    with pytest.raises(ValueError, match="geometry.length expects"):
        validate_problem_units(problem)


def test_rejects_unknown_unit():
    data = valid_problem()
    data["mesh"]["size"]["unit"] = "handwave"
    problem = validate_problem(data)
    with pytest.raises(ValueError, match="unknown unit"):
        validate_problem_units(problem)


def test_large_direction_is_normalized_without_overflow():
    data = valid_problem()
    data["loads"][0]["direction"] = [1e300, 0, 0]
    assert validate_problem(data).loads[0].direction == (1.0, 0.0, 0.0)
