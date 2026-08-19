import io
import json
import urllib.error

import pytest

import redfish_client


class FakeOpener:
    """Stands in for urllib's opener. Records requests, replays canned responses."""

    def __init__(self, responses):
        self.responses = responses
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append(request)
        payload = self.responses.pop(0)
        if isinstance(payload, Exception):
            raise payload
        body = json.dumps(payload).encode()
        return _FakeResponse(body)


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _client(responses):
    return redfish_client.RedfishClient(
        host="10.0.0.1",
        username="root",
        password="hunter2",
        opener=FakeOpener(responses),
    )


def test_get_returns_parsed_json():
    client = _client([{"Id": "System"}])
    assert client.get("/redfish/v1/Systems/X") == {"Id": "System"}


def test_get_sends_basic_auth():
    opener = FakeOpener([{"ok": True}])
    client = redfish_client.RedfishClient("10.0.0.1", "root", "hunter2", opener=opener)
    client.get("/redfish/v1")
    header = opener.requests[0].get_header("Authorization")
    assert header.startswith("Basic ")


def test_get_expanded_appends_the_expand_query():
    opener = FakeOpener([{"Members": []}])
    client = redfish_client.RedfishClient("10.0.0.1", "root", "p", opener=opener)
    client.get_expanded("/redfish/v1/Chassis/X/Sensors")
    assert "$expand=*($levels=1)" in opener.requests[0].full_url


def test_patch_uses_the_patch_verb_and_sends_json():
    opener = FakeOpener([{}])
    client = redfish_client.RedfishClient("10.0.0.1", "root", "p", opener=opener)
    client.patch("/redfish/v1/Chassis/X", {"LocationIndicatorActive": True})
    request = opener.requests[0]
    assert request.get_method() == "PATCH"
    assert json.loads(request.data) == {"LocationIndicatorActive": True}


def test_transport_errors_become_redfish_error(monkeypatch):
    monkeypatch.setattr(redfish_client.time, "sleep", lambda _s: None)
    client = _client([OSError("connection refused")])
    with pytest.raises(redfish_client.RedfishError):
        client.get("/redfish/v1")


def test_redact_removes_the_password_from_text():
    client = _client([])
    assert "hunter2" not in client.redact("failed with hunter2 in the url")
    assert "***" in client.redact("failed with hunter2 in the url")


def test_redfish_error_message_never_contains_the_password(monkeypatch):
    monkeypatch.setattr(redfish_client.time, "sleep", lambda _s: None)
    client = _client([OSError("auth failed for root:hunter2")])
    with pytest.raises(redfish_client.RedfishError) as excinfo:
        client.get("/redfish/v1")
    assert "hunter2" not in str(excinfo.value)


def _http_error(code):
    return urllib.error.HTTPError("https://x", code, "boom", {}, None)


def test_a_transient_500_is_retried_and_then_succeeds(monkeypatch):
    monkeypatch.setattr(redfish_client.time, "sleep", lambda _s: None)
    client = _client([_http_error(500), {"Id": "System"}])
    assert client.get("/redfish/v1/Systems/X") == {"Id": "System"}


def test_retry_gives_up_after_the_cap(monkeypatch):
    monkeypatch.setattr(redfish_client.time, "sleep", lambda _s: None)
    client = _client([_http_error(503)] * redfish_client._RETRY_ATTEMPTS)
    with pytest.raises(redfish_client.RedfishError):
        client.get("/redfish/v1")


def test_a_non_transient_status_is_not_retried(monkeypatch):
    monkeypatch.setattr(redfish_client.time, "sleep", lambda _s: None)
    opener = FakeOpener([_http_error(404), {"never": "reached"}])
    client = redfish_client.RedfishClient("10.0.0.1", "root", "p", opener=opener)
    with pytest.raises(redfish_client.RedfishError):
        client.get("/redfish/v1/missing")
    assert len(opener.requests) == 1


def test_a_timeout_is_not_retried(monkeypatch):
    """A timeout already spent its budget; retrying it multiplies how long one poll blocks."""
    monkeypatch.setattr(redfish_client.time, "sleep", lambda _s: None)
    opener = FakeOpener([TimeoutError("timed out"), {"never": "reached"}])
    client = redfish_client.RedfishClient("10.0.0.1", "root", "p", opener=opener)
    with pytest.raises(redfish_client.RedfishError) as excinfo:
        client.get("/redfish/v1")
    assert len(opener.requests) == 1
    assert "timeout" in str(excinfo.value).lower()


def test_a_connect_phase_timeout_wrapped_in_urlerror_is_not_retried(monkeypatch):
    """urllib re-raises a connect-phase timeout as URLError, which must not reach the retry path.

    Without this, a firewall silently dropping SYN would cost three full timeouts per poll.
    """
    monkeypatch.setattr(redfish_client.time, "sleep", lambda _s: None)
    opener = FakeOpener([urllib.error.URLError(TimeoutError("timed out")), {"never": "reached"}])
    client = redfish_client.RedfishClient("10.0.0.1", "root", "p", opener=opener)
    with pytest.raises(redfish_client.RedfishError) as excinfo:
        client.get("/redfish/v1")
    assert len(opener.requests) == 1
    assert "timeout" in str(excinfo.value).lower()


def test_a_connection_refusal_is_retried(monkeypatch):
    """A refused connection fails in milliseconds, so retrying it is cheap and worth doing."""
    monkeypatch.setattr(redfish_client.time, "sleep", lambda _s: None)
    client = _client([urllib.error.URLError("refused"), {"Id": "System"}])
    assert client.get("/redfish/v1/Systems/X") == {"Id": "System"}


def test_a_post_is_never_retried(monkeypatch):
    """Replaying a POST could fire a power action twice. One attempt, always."""
    monkeypatch.setattr(redfish_client.time, "sleep", lambda _s: None)
    opener = FakeOpener([_http_error(500), {"never": "reached"}])
    client = redfish_client.RedfishClient("10.0.0.1", "root", "p", opener=opener)
    with pytest.raises(redfish_client.RedfishError):
        client.post("/redfish/v1/Systems/X/Actions/ComputerSystem.Reset", {"ResetType": "On"})
    assert len(opener.requests) == 1


def test_paths_default_to_the_conventional_ids_before_resolve():
    client = _client([])
    assert client.system == redfish_client.DEFAULT_SYSTEM
    assert client.sensors.endswith("/Sensors")


def test_resolve_learns_non_conventional_resource_ids():
    client = _client(
        [
            {"@odata.id": "/redfish/v1"},
            {"Members": [{"@odata.id": "/redfish/v1/Systems/Node1.Slot.3"}]},
            {"Members": [{"@odata.id": "/redfish/v1/Chassis/Node1.Slot.3"}]},
            {"Members": [{"@odata.id": "/redfish/v1/Managers/iDRAC.Modular.3"}]},
        ]
    )
    client.resolve()
    assert client.system == "/redfish/v1/Systems/Node1.Slot.3"
    assert client.thermal == "/redfish/v1/Chassis/Node1.Slot.3/Thermal"
    assert client.storage_collection == "/redfish/v1/Systems/Node1.Slot.3/Storage"
    # DellAttributes is keyed by the SYSTEM id but hangs off the MANAGER.
    assert client.dell_attributes == (
        "/redfish/v1/Managers/iDRAC.Modular.3/Oem/Dell/DellAttributes/Node1.Slot.3"
    )


def test_resolve_falls_back_when_a_collection_is_empty_or_unreadable(monkeypatch):
    monkeypatch.setattr(redfish_client.time, "sleep", lambda _s: None)
    client = _client(
        [{"@odata.id": "/redfish/v1"}, {"Members": []}, OSError("nope"), {"Members": []}]
    )
    client.resolve()
    assert client.system == redfish_client.DEFAULT_SYSTEM
    assert client.chassis == redfish_client.DEFAULT_CHASSIS
    assert client.manager == redfish_client.DEFAULT_MANAGER


def test_resolve_gives_up_immediately_when_the_service_root_is_unreachable(monkeypatch):
    """An unreachable iDRAC must cost ONE timeout, not four.

    Measured live on a blackholed address: the per-collection fallback swallowed three full
    RequestTimeouts inside resolve() before the poll added a fourth, blocking one onHeartbeat for
    120 s. Domoticz's own 60 s watchdog then logged the plugin thread as ended unexpectedly.
    Redfish mandates the service root, so a failure there is transport and must propagate.
    """
    monkeypatch.setattr(redfish_client.time, "sleep", lambda _s: None)
    opener = FakeOpener(
        [
            urllib.error.URLError(TimeoutError()),
            {"Members": [{"@odata.id": "/redfish/v1/Systems/NeverReached"}]},
        ]
    )
    client = redfish_client.RedfishClient("10.0.0.1", "root", "p", opener=opener)
    with pytest.raises(redfish_client.RedfishError):
        client.resolve()
    assert len(opener.requests) == 1
    assert opener.requests[0].full_url.endswith(redfish_client.ROOT)
    # And nothing was learned, so the caller has not latched a guess.
    assert client.system == redfish_client.DEFAULT_SYSTEM


def test_resolve_probes_the_service_root_before_the_collections():
    opener = FakeOpener(
        [
            {"@odata.id": "/redfish/v1"},
            {"Members": [{"@odata.id": "/redfish/v1/Systems/S"}]},
            {"Members": [{"@odata.id": "/redfish/v1/Chassis/C"}]},
            {"Members": [{"@odata.id": "/redfish/v1/Managers/M"}]},
        ]
    )
    client = redfish_client.RedfishClient("10.0.0.1", "root", "p", opener=opener)
    assert client.resolve() is True
    assert [r.full_url.rsplit("/redfish", 1)[-1] for r in opener.requests] == [
        "/v1",
        "/v1/Systems",
        "/v1/Chassis",
        "/v1/Managers",
    ]


def test_metric_report_ids_are_discovered_not_assumed():
    """Report NAMES differ by how the machine is licensed and managed.

    A Datacenter iDRAC serves Dell's built-in "PowerMetrics". A machine managed by OpenManage
    Enterprise with the Advanced licence instead carries the Power Manager Plugin's own reports,
    named "OME-PMP-Power-A", "OME-PMP-Power-B" and so on, and the built-in ones return a licence
    error. Hardcoding either name finds nothing on the other machine.
    """
    opener = FakeOpener(
        [
            {
                "Members": [
                    {"@odata.id": "/redfish/v1/TelemetryService/MetricReports/OME-PMP-Power-A"},
                    {"@odata.id": "/redfish/v1/TelemetryService/MetricReports/OME-PMP-Thermal"},
                ]
            }
        ]
    )
    client = redfish_client.RedfishClient("10.0.0.1", "root", "p", opener=opener)
    assert client.metric_report_ids() == [
        "/redfish/v1/TelemetryService/MetricReports/OME-PMP-Power-A",
        "/redfish/v1/TelemetryService/MetricReports/OME-PMP-Thermal",
    ]
    assert opener.requests[0].full_url.endswith("/TelemetryService/MetricReports")


def test_metric_report_ids_is_empty_when_telemetry_is_unlicensed(monkeypatch):
    """An unlicensed iDRAC answers the collection with a licence error, not an empty list."""
    monkeypatch.setattr(redfish_client.time, "sleep", lambda _s: None)
    client = _client([_http_error(400)])
    with pytest.raises(redfish_client.RedfishError):
        client.metric_report_ids()


def test_metric_report_ids_tolerates_a_collection_with_no_members():
    client = _client([{}])
    assert client.metric_report_ids() == []


def test_the_idrac_attribute_path_is_derived_from_the_manager_not_the_system():
    """Telemetry attributes live under the MANAGER id, not the system id.

    dell_attributes points at DellAttributes/<system id>, which is where power and thermal
    settings live. The telemetry switches are under DellAttributes/<manager id>, a different
    resource, and writing to the wrong one silently does nothing useful.
    """
    opener = FakeOpener(
        [
            {"@odata.id": "/redfish/v1"},
            {"Members": [{"@odata.id": "/redfish/v1/Systems/Node1.Slot.3"}]},
            {"Members": [{"@odata.id": "/redfish/v1/Chassis/Node1.Slot.3"}]},
            {"Members": [{"@odata.id": "/redfish/v1/Managers/iDRAC.Modular.3"}]},
        ]
    )
    client = redfish_client.RedfishClient("10.0.0.1", "root", "p", opener=opener)
    client.resolve()
    assert client.dell_attributes.endswith("/DellAttributes/Node1.Slot.3")
    assert client.idrac_attributes.endswith("/DellAttributes/iDRAC.Modular.3")
    assert client.idrac_attributes.startswith("/redfish/v1/Managers/iDRAC.Modular.3/")
