import config


def _params(**overrides):
    base = {
        "Address": "192.168.0.10",
        "Username": "root",
        "Password": "secret",
        "AllowControl": "false",
        "AllowHardPowerActions": "false",
        "PollInterval": "30",
        "SlowEvery": "10",
        "EnableDrives": "true",
        "EnableVolumes": "true",
        "EnableNICs": "true",
        "EnablePSUs": "true",
        "DriveLifeFloor": "10",
        "VerifyTLS": "false",
        "RequestTimeout": "30",
        "DebugLevel": "0",
    }
    base.update(overrides)
    return base


def test_defaults_parse():
    cfg = config.parse_config(_params())
    assert cfg.address == "192.168.0.10"
    assert cfg.poll_interval == 30
    assert cfg.allow_control is False
    assert cfg.verify_tls is False


def test_booleans_accept_the_manifest_string_forms():
    assert config.parse_config(_params(AllowControl="true")).allow_control is True
    assert config.parse_config(_params(AllowControl="True")).allow_control is True
    assert config.parse_config(_params(EnableDrives="false")).enable_drives is False


def test_numeric_fields_are_clamped_to_their_manifest_range():
    assert config.parse_config(_params(PollInterval="1")).poll_interval == 15
    assert config.parse_config(_params(PollInterval="9999")).poll_interval == 600
    assert config.parse_config(_params(SlowEvery="0")).slow_every == 1


def test_garbage_numeric_falls_back_to_the_default():
    assert config.parse_config(_params(PollInterval="abc")).poll_interval == 30


def test_missing_keys_fall_back_to_defaults():
    cfg = config.parse_config({"Address": "h", "Username": "u", "Password": "p"})
    assert cfg.poll_interval == 30
    assert cfg.enable_drives is True


def test_address_is_stripped_of_a_scheme_and_trailing_slash():
    assert config.parse_config(_params(Address="https://10.0.0.5/")).address == "10.0.0.5"
