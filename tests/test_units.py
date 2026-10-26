import pytest

from openmechanical.contracts import Quantity
from openmechanical.units import to_si


def test_equivalent_length_units_convert_to_same_si_value():
    assert to_si(Quantity(value=25.4, unit="mm"), "meter") == pytest.approx(
        to_si(Quantity(value=0.0254, unit="m"), "meter")
    )


def test_pressure_is_converted_to_pascal():
    assert to_si(Quantity(value=210, unit="GPa"), "pascal") == pytest.approx(2.1e11)


def test_rejects_wrong_requested_dimension():
    with pytest.raises(ValueError, match="expected pascal"):
        to_si(Quantity(value=1, unit="mm"), "pascal")


@pytest.mark.parametrize("unit", ["0*m", "-1*m", "100*m"])
def test_quantity_unit_cannot_hide_a_scale_or_sign(unit):
    with pytest.raises(ValueError):
        to_si(Quantity(value=1, unit=unit), "meter")
