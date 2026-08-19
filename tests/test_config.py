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
    # Floor is 20, not 15: the heartbeat ticks every 10 s, so every selectable PollInterval must
    # be a multiple of 10 or the setting would quietly poll later than it claims.
    assert config.parse_config(_params(PollInterval="1")).poll_interval == 20
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


def test_an_unrecognised_boolean_keeps_the_field_default_not_false():
    """EnableDrives defaults ON. A typo must not silently disable drive monitoring."""
    cfg = config.parse_config(_params(EnableDrives="enable"))
    assert cfg.enable_drives is True
    assert any("EnableDrives" in w for w in cfg.warnings)


def test_recognised_false_forms_still_disable():
    for value in ("false", "no", "0", "off", "FALSE"):
        assert config.parse_config(_params(EnableDrives=value)).enable_drives is False


def test_clamping_is_reported_not_silent():
    cfg = config.parse_config(_params(PollInterval="9999"))
    assert cfg.poll_interval == 600
    assert any("PollInterval" in w and "600" in w for w in cfg.warnings)


def test_unreadable_numeric_is_reported():
    cfg = config.parse_config(_params(PollInterval="abc"))
    assert cfg.poll_interval == 30
    assert any("PollInterval" in w for w in cfg.warnings)


def test_a_clean_config_reports_no_warnings():
    assert config.parse_config(_params()).warnings == ()
