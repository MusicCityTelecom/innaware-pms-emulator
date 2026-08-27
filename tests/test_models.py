import pytest
from pydantic import ValidationError

from innaware_pms_emulator.models import InterfaceConfig


def base_config(**overrides):
    data = {
        "name": "test",
        "purpose": "pms",
        "protocol": "FIAS",
        "transport": "serial",
        "serial_device": "COM3",
    }
    data.update(overrides)
    return data


def test_serial_defaults_are_valid():
    config = InterfaceConfig.model_validate(base_config())
    assert config.baud_rate == 9600
    assert config.data_bits == 8
    assert config.parity == "N"
    assert config.stop_bits == 1
    assert config.flow_control == "none"


def test_serial_allows_seven_even_one_and_half_stop_bits():
    config = InterfaceConfig.model_validate(base_config(data_bits=7, parity="e", stop_bits=1.5, flow_control="xonxoff"))
    assert config.data_bits == 7
    assert config.parity == "E"
    assert config.stop_bits == 1.5
    assert config.flow_control == "xonxoff"


@pytest.mark.parametrize(
    "field,value",
    [
        ("data_bits", 9),
        ("parity", "X"),
        ("stop_bits", 3),
        ("flow_control", "magic"),
    ],
)
def test_invalid_serial_parameters_fail_closed(field, value):
    with pytest.raises(ValidationError):
        InterfaceConfig.model_validate(base_config(**{field: value}))
