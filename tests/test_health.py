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


def _red(mode="N+m", status="OK", min_needed=1, supplies=2):
    return model.Redundancy(
        name="System Board PS Redundancy",
        mode=mode,
        health=status,
        min_needed=min_needed,
        supplies=supplies,
    )


def _attrs(policy="A/B Grid Redundant", hot_spare="Disabled", primary="PSU1"):
    return model.DellAttrs(
        accumulative_power=None,
        peak_watts=None,
        powered_on_seconds=None,
        redundancy_policy=policy,
        hot_spare=hot_spare,
        hot_spare_primary=primary,
    )


def test_redundancy_text_leads_with_the_configured_policy():
    """Measured across eight Dell servers: Mode is "N+m" on EVERY ONE of them, whatever the
    redundancy policy is set to. Building the text from the mode alone therefore rendered the
    identical sentence for "A/B Grid Redundant" and "PSU Redundant", so changing the policy on
    the iDRAC could never change the card. The configured policy is the only field that moves.
    """
    assert health.redundancy_health(_red(), _attrs()) == (
        health.LEVEL_OK,
        "A/B Grid Redundant, 2 supplies (1 needed)",
    )
    assert health.redundancy_health(_red(), _attrs(policy="PSU Redundant"))[1] == (
        "PSU Redundant, 2 supplies (1 needed)"
    )


def test_redundancy_text_names_the_primary_supply_not_the_spare():
    """The named supply is the one CARRYING the load, not the one parked.

    Measured on a DSS8440 with primaries "PSU1 and PSU3": those two delivered 288 W and 307 W
    while PSU2 and PSU4 sat at 0 W. Reading ", hot spare PSU1" therefore labelled the working
    supply as the spare, which is the opposite of what the server means.
    """
    level, text = health.redundancy_health(_red(), _attrs(hot_spare="Enabled"))
    assert (level, text) == (
        health.LEVEL_OK,
        "A/B Grid Redundant, 2 supplies (1 needed), hot spare, primary PSU1",
    )


def test_hot_spare_primary_is_shown_verbatim_because_it_can_name_several():
    """A live DSS8440 reports RapidOnPrimaryPSU as "PSU1 and PSU3". It is not a single token,
    and Dell's phrasing goes through untouched rather than being reworded to "PSU1 + PSU3"."""
    _, text = health.redundancy_health(_red(), _attrs(hot_spare="Enabled", primary="PSU1 and PSU3"))
    assert text.endswith("hot spare, primary PSU1 and PSU3")


def test_hot_spare_enabled_without_a_named_primary_still_says_so():
    _, text = health.redundancy_health(_red(), _attrs(hot_spare="Enabled", primary=None))
    assert text.endswith("hot spare enabled")


def test_hot_spare_disabled_adds_nothing():
    _, text = health.redundancy_health(_red(), _attrs(hot_spare="Disabled"))
    assert "hot spare" not in text


def test_a_missing_policy_falls_back_to_the_redfish_mode():
    """Non-Dell Redfish serves the generic Redundancy object and none of the Dell attributes."""
    _, text = health.redundancy_health(_red(), _attrs(policy=None))
    assert text == "Redundant, 2 supplies (1 needed)"


def test_a_fault_reports_the_fault_and_not_the_policy():
    """When redundancy is lost, what the operator needs is the failure, not the configuration
    that is no longer being met."""
    assert health.redundancy_health(_red(status="Critical"), _attrs(hot_spare="Enabled")) == (
        health.LEVEL_RED,
        "Redundancy lost",
    )


def test_redundancy_text_is_plain_english_with_the_counts():
    """ "N+m" is Redfish jargon and was leaking straight onto the dashboard.

    Every number here is reported by the server: MinNumNeeded and the size of the RedundancySet.
    """
    assert health.redundancy_health(_red()) == (
        health.LEVEL_OK,
        "Redundant, 2 supplies (1 needed)",
    )


def test_redundancy_text_translates_every_redfish_mode():
    modes = {
        "N+m": "Redundant",
        "Failover": "Failover",
        "Sharing": "Load sharing",
        "Sparing": "Sparing",
        "NotRedundant": "Not redundant",
    }
    for mode, expected in modes.items():
        level, text = health.redundancy_health(_red(mode=mode))
        assert text.startswith(expected), (mode, text)
        assert level == health.LEVEL_OK


def test_an_unrecognised_mode_is_shown_verbatim_rather_than_guessed():
    _, text = health.redundancy_health(_red(mode="Frobnicated"))
    assert text.startswith("Frobnicated")


def test_redundancy_faults_say_what_happened():
    assert health.redundancy_health(_red(status="Critical")) == (
        health.LEVEL_RED,
        "Redundancy lost",
    )
    assert health.redundancy_health(_red(status="Warning")) == (
        health.LEVEL_ORANGE,
        "Redundancy degraded",
    )


def test_redundancy_without_counts_still_reads_sensibly():
    level, text = health.redundancy_health(_red(min_needed=None, supplies=None))
    assert (level, text) == (health.LEVEL_OK, "Redundant")


def test_redundancy_with_an_unknown_status_is_grey():
    level, text = health.redundancy_health(_red(status=None))
    assert level == health.LEVEL_GREY
    assert "Unknown" in text


def test_a_latched_rollup_with_no_fault_text_still_names_the_subsystem():
    """From a real PowerEdge R750 reporting Critical with an EMPTY fault list.

    Dell rollups latch, so a machine can be red with nothing currently wrong and no message to
    show. The tile must still say WHY it is red, or the user sees a red device and no reason.
    """
    system = model.parse_system(load("r750", "system"))
    assert system.health == "Critical"
    assert model.parse_faults(load("r750", "faults")) == []
    level, text = health.system_health(system.health, system.rollups)
    assert level == health.LEVEL_RED
    assert text == "Critical: SEL"


def test_a_healthy_group_under_a_non_redundant_policy_does_not_print_the_contradiction():
    """The server is disagreeing with itself: it reports a healthy redundancy group while the
    configured policy says there is none. Leading with the policy would put "Not Redundant,
    2 supplies (1 needed)" on a GREEN tile, so the group's own wording wins instead.
    """
    level, text = health.redundancy_health(
        _red(), _attrs(policy="Not Redundant", hot_spare="Enabled")
    )
    assert (level, text) == (health.LEVEL_OK, "Redundant, 2 supplies (1 needed)")


def test_is_not_redundant_tolerates_a_qualifier_on_dells_wording():
    assert health.is_not_redundant("Not Redundant")
    assert health.is_not_redundant("  not redundant (something)  ")
    assert not health.is_not_redundant("A/B Grid Redundant")
    assert not health.is_not_redundant(None)
