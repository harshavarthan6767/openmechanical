"""Explicit unit conversion helpers."""

from __future__ import annotations

import math

import pint

from .contracts import BoxGeometry, MountingBracketGeometry, ProblemSpec, Quantity

ureg = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)


def to_si(value: Quantity, dimensionality: str) -> float:
    """Convert a finite, unit-bearing quantity to SI base units."""
    if not math.isfinite(value.value):
        raise ValueError("quantity must be finite")
    try:
        result = (value.value * ureg.Unit(value.unit)).to_base_units()
    except (pint.errors.UndefinedUnitError, pint.errors.DimensionalityError) as exc:
        raise ValueError(f"invalid unit {value.unit!r}") from exc
    if result.dimensionality != ureg(dimensionality).dimensionality:
        raise ValueError(f"expected {dimensionality}, received {value.unit}")
    magnitude = float(result.magnitude)
    if not math.isfinite(magnitude) or magnitude <= 0:
        raise ValueError("converted quantity must be finite and positive")
    return magnitude


def validate_problem_units(problem: ProblemSpec) -> None:
    """Check every quantity against the dimension required by its field."""

    def check(quantity: Quantity, expected_unit: str, field: str) -> None:
        try:
            actual = ureg.Unit(quantity.unit)
            expected = ureg(expected_unit)
            if actual.dimensionality != expected.dimensionality:
                raise ValueError(
                    f"{field} expects units compatible with {expected_unit}, got {quantity.unit}"
                )
            to_si(quantity, expected_unit)
        except pint.errors.UndefinedUnitError as exc:
            raise ValueError(f"{field} uses unknown unit {quantity.unit!r}") from exc

    if isinstance(problem.geometry, BoxGeometry):
        for field in ("length", "width", "height"):
            check(getattr(problem.geometry, field), "meter", f"geometry.{field}")
    elif isinstance(problem.geometry, MountingBracketGeometry):
        for field in ("base_length", "width", "height", "thickness", "root_radius"):
            check(getattr(problem.geometry, field), "meter", f"geometry.{field}")
        base_length = to_si(problem.geometry.base_length, "meter")
        height = to_si(problem.geometry.height, "meter")
        thickness = to_si(problem.geometry.thickness, "meter")
        radius = to_si(problem.geometry.root_radius, "meter")
        if thickness >= min(base_length, height):
            raise ValueError("geometry.thickness must be smaller than the base and upright lengths")
        if thickness + radius >= min(base_length, height):
            raise ValueError("geometry.thickness plus root_radius exceeds the bracket envelope")
    else:
        geometry = problem.geometry
        check(
            Quantity(value=1, unit=geometry.declared_length_unit),
            "meter",
            "geometry.declared_length_unit",
        )
    check(problem.material.youngs_modulus, "pascal", "material.youngs_modulus")
    if problem.material.density is not None:
        check(problem.material.density, "kilogram / meter ** 3", "material.density")
    if problem.material.allowable_stress is not None:
        check(problem.material.allowable_stress, "pascal", "material.allowable_stress")
    check(problem.mesh.size, "meter", "mesh.size")
    for index, load in enumerate(problem.loads):
        check(load.magnitude, "pascal", f"loads[{index}].magnitude")


def canonical_problem_si(problem: ProblemSpec) -> dict[str, object]:
    """Serialize a supported box problem with all unit-bearing values in SI."""
    if isinstance(problem.geometry, BoxGeometry):
        length_fields = ("length", "width", "height")
    elif isinstance(problem.geometry, MountingBracketGeometry):
        length_fields = ("base_length", "width", "height", "thickness", "root_radius")
    else:
        raise ValueError("SI canonical serialization does not yet support STEP geometry")

    data = problem.model_dump(mode="json")
    geometry = data["geometry"]
    assert isinstance(geometry, dict)
    for field in length_fields:
        quantity = getattr(problem.geometry, field)
        geometry[field] = {"value": to_si(quantity, "meter"), "unit": "m"}

    material = data["material"]
    assert isinstance(material, dict)
    material["youngs_modulus"] = {
        "value": to_si(problem.material.youngs_modulus, "pascal"),
        "unit": "Pa",
    }
    if problem.material.density is not None:
        material["density"] = {
            "value": to_si(problem.material.density, "kilogram / meter ** 3"),
            "unit": "kg/m^3",
        }
    if problem.material.allowable_stress is not None:
        material["allowable_stress"] = {
            "value": to_si(problem.material.allowable_stress, "pascal"),
            "unit": "Pa",
        }

    loads = data["loads"]
    assert isinstance(loads, list)
    for index, load in enumerate(problem.loads):
        load_data = loads[index]
        assert isinstance(load_data, dict)
        load_data["magnitude"] = {"value": to_si(load.magnitude, "pascal"), "unit": "Pa"}

    mesh = data["mesh"]
    assert isinstance(mesh, dict)
    mesh["size"] = {"value": to_si(problem.mesh.size, "meter"), "unit": "m"}
    return data
