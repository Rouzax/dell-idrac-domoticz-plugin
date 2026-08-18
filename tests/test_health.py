import health
import model
from tests.fixture_loader import load


def test_alert_level_maps_redfish_status():
    assert health.alert_level("OK") == health.LEVEL_OK
    assert health.alert_level("Warning") == health.LEVEL_ORANGE
    assert health.alert_level("Critical") == health.LEVEL_RED
    assert health.alert_level(None) == health.LEVEL_GREY
    assert health.alert_level("Nonsense") == health.LEVEL_GREY


def test_system_health_all_ok_does_not_list_subsystems():
    level, text = health.system_health("OK", {"CPURollupStatus": "OK", "PSRollupStatus": "OK"})
    assert level == health.LEVEL_OK
    assert text == "OK"


def test_system_health_names_only_the_unhappy_subsystems():
    level, text = health.system_health(
        "Warning",
        {"CPURollupStatus": "OK", "PSRollupStatus": "Warning", "StorageRollupStatus": "Warning"},
    )
    assert level == health.LEVEL_ORANGE
    assert text == "Warning: PS, Storage"


def test_system_health_worst_level_wins_over_overall():
    level, text = health.system_health("OK", {"StorageRollupStatus": "Critical"})
    assert level == health.LEVEL_RED
    assert text == "Critical: Storage"


def test_dell_reports_error_where_redfish_reports_critical():
    """Measured against a real PSU pull: Dell OEM rollups say "Error", not "Critical"."""
    assert health.alert_level("Error") == health.LEVEL_RED
    assert health.alert_level("error") == health.LEVEL_RED
    assert health.alert_level("Failed") == health.LEVEL_RED
    assert health.alert_level("Non-Critical") == health.LEVEL_ORANGE


def test_real_psu_failure_turns_red_and_names_ps():
    """The device must name the failing subsystem, not merely raise the level.

    Runs against a capture taken live with one PSU AC cord pulled.
    """
    info = model.parse_system(load("degraded", "system"))
    level, text = health.system_health(info.health, info.rollups)
    assert level == health.LEVEL_RED
    assert "PS" in text
    # The aggregate rollup must not be listed as if it were a subsystem.
    assert "SystemHealth" not in text


def test_healthy_capture_stays_green_and_names_nothing():
    info = model.parse_system(load("t550", "system"))
    assert health.system_health(info.health, info.rollups) == (health.LEVEL_OK, "OK")


def test_real_failed_psu_status_maps_red():
    psus = model.parse_power(load("degraded", "power"))
    dead = next(p for p in psus if p.input_watts == 0.0)
    assert health.simple_health(dead.health, "OK")[0] == health.LEVEL_RED


def test_non_recoverable_maps_red():
    assert health.alert_level("Non-Recoverable") == health.LEVEL_RED
    assert health.alert_level("NonRecoverable") == health.LEVEL_RED


def test_an_unmapped_status_surfaces_its_raw_value():
    """An absent status and an unrecognised one must be distinguishable in the UI."""
    level, text = health.simple_health("Frobnicated", "OK")
    assert level == health.LEVEL_GREY
    assert "Frobnicated" in text
    assert health.simple_health(None, "OK") == (health.LEVEL_GREY, "Unknown")


def test_system_health_unknown_when_nothing_is_known():
    level, text = health.system_health(None, {})
    assert level == health.LEVEL_GREY
    assert text == "Unknown"


def _drive(**kw):
    base = {
        "id": "Disk.Bay.0",
        "name": "SSD 0",
        "media_type": "SSD",
        "capacity_bytes": 100,
        "health": "OK",
        "failure_predicted": False,
        "life_left_pct": 100,
    }
    base.update(kw)
    return model.Drive(**base)


def test_drive_health_ok():
    level, text = health.drive_health(_drive(), life_floor_pct=10)
    assert level == health.LEVEL_OK
    assert "SSD" in text and "100%" in text


def test_drive_health_predicted_failure_forces_orange():
    level, text = health.drive_health(_drive(failure_predicted=True), life_floor_pct=10)
    assert level == health.LEVEL_ORANGE
    assert "failure predicted" in text.lower()


def test_drive_health_low_life_forces_orange():
    level, text = health.drive_health(_drive(life_left_pct=4), life_floor_pct=10)
    assert level == health.LEVEL_ORANGE
    assert "4%" in text


def test_drive_health_critical_status_beats_predicted_failure():
    level, _ = health.drive_health(
        _drive(health="Critical", failure_predicted=True), life_floor_pct=10
    )
    assert level == health.LEVEL_RED


def test_drive_health_missing_life_is_not_treated_as_zero():
    level, _ = health.drive_health(_drive(life_left_pct=None), life_floor_pct=10)
    assert level == health.LEVEL_OK
