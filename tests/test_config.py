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


def test_name_affixes_are_taken_exactly_as_typed():
    """Whitespace is load-bearing here: "SERVER1 - " needs its trailing space, and stripping it
    would glue the prefix to the device name."""
    cfg = config.parse_config({"NamePrefix": "SERVER1 - ", "NameSuffix": "_TESTSRV"})
    assert cfg.name_prefix == "SERVER1 - "
    assert cfg.name_suffix == "_TESTSRV"


def test_missing_name_affixes_default_to_empty():
    cfg = config.parse_config({})
    assert cfg.name_prefix == ""
    assert cfg.name_suffix == ""


def test_an_overlong_affix_is_clamped_and_reported():
    """Domoticz stores a device name in a VARCHAR(100) and the longest name the plugin
    generates is already 35 characters, so an unbounded affix could truncate a real name."""
    cfg = config.parse_config({"NamePrefix": "x" * 40})
    assert len(cfg.name_prefix) == config.MAX_AFFIX
    assert any("NamePrefix" in note for note in cfg.warnings)


def test_an_affix_at_the_limit_is_not_reported():
    cfg = config.parse_config({"NameSuffix": "y" * config.MAX_AFFIX})
    assert cfg.name_suffix == "y" * config.MAX_AFFIX
    assert not any("NameSuffix" in note for note in cfg.warnings)


def test_formatted_card_text_defaults_on():
    assert config.parse_config({}).rich_card_text is True


def test_formatted_card_text_can_be_switched_off():
    assert config.parse_config({"RichCardText": "false"}).rich_card_text is False


def test_an_unrecognised_formatted_card_text_value_keeps_the_default():
    cfg = config.parse_config({"RichCardText": "perhaps"})
    assert cfg.rich_card_text is True
    assert any("RichCardText" in note for note in cfg.warnings)


def test_energy_counters_defaults_on():
    cfg = config.parse_config({"Address": "h"})
    assert cfg.energy_counters is True


def test_energy_counters_can_be_turned_off():
    cfg = config.parse_config({"Address": "h", "EnergyCounters": "false"})
    assert cfg.energy_counters is False
