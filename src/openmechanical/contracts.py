"""Versioned input contracts for the OpenMechanical CLI."""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PositiveFinite = Annotated[float, Field(gt=0, allow_inf_nan=False)]
Finite = Annotated[float, Field(allow_inf_nan=False)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Quantity(StrictModel):
    value: PositiveFinite
    unit: str = Field(min_length=1)


class Material(StrictModel):
    name: str = Field(min_length=1)
    youngs_modulus: Quantity
    poisson_ratio: Finite
    density: Quantity | None = None
    allowable_stress: Quantity | None = None

    @field_validator("poisson_ratio")
    @classmethod
    def validate_poisson_ratio(cls, value: float) -> float:
        if not math.isfinite(value) or not -1.0 < value < 0.5:
            raise ValueError("isotropic Poisson ratio must be finite and in (-1, 0.5)")
        return value


class BoxGeometry(StrictModel):
    kind: Literal["box"] = "box"
    length: Quantity
    width: Quantity
    height: Quantity


class MountingBracketGeometry(StrictModel):
    kind: Literal["mounting_bracket"] = "mounting_bracket"
    base_length: Quantity
    width: Quantity
    height: Quantity
    thickness: Quantity
    root_radius: Quantity


class StepGeometry(StrictModel):
    kind: Literal["step"] = "step"
    path: str = Field(min_length=1)
    declared_length_unit: str = Field(min_length=1)


class Load(StrictModel):
    kind: Literal["traction", "pressure"]
    region: str = Field(min_length=1)
    magnitude: Quantity
    direction: tuple[Finite, Finite, Finite] | None = None

    @field_validator("direction")
    @classmethod
    def normalize_direction(cls, value):
        if value is None:
            return None
        scale = max(abs(x) for x in value)
        if scale == 0:
            raise ValueError("direction must be nonzero")
        scaled = tuple(x / scale for x in value)
        norm = math.hypot(*scaled)
        return tuple(x / norm for x in scaled)


class Constraint(StrictModel):
    kind: Literal["fixed"]
    region: str = Field(min_length=1)


class MeshPolicy(StrictModel):
    element_order: Literal[2] = 2
    size: Quantity
    minimum_minsicn: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] = 0.0


class ProblemSpec(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    name: str = Field(min_length=1)
    analysis: Literal["linear_static"]
    geometry: BoxGeometry | MountingBracketGeometry | StepGeometry
    material: Material
    loads: tuple[Load, ...] = Field(min_length=1)
    constraints: tuple[Constraint, ...] = Field(min_length=1)
    mesh: MeshPolicy

    @model_validator(mode="after")
    def validate_load_directions(self) -> ProblemSpec:
        for load in self.loads:
            if load.kind == "traction":
                if load.direction is None or math.isclose(
                    math.sqrt(sum(x * x for x in load.direction)), 0
                ):
                    raise ValueError("traction requires a nonzero direction vector")
            elif load.direction is not None:
                raise ValueError("pressure direction is determined by the selected surface normal")
        return self


def validate_problem(data: object) -> ProblemSpec:
    """Validate an untrusted JSON-decoded problem object."""
    return ProblemSpec.model_validate(data)
