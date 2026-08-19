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


def test_select_appends_the_select_query():
    opener = FakeOpener([{"Attributes": {}}])
    client = redfish_client.RedfishClient("10.0.0.1", "root", "p", opener=opener)
    client.select("/redfish/v1/Managers/X", "Attributes/ServerPwrMon.1.AccumulativePower")
    assert "$select=Attributes/ServerPwrMon.1.AccumulativePower" in opener.requests[0].full_url


def test_patch_uses_the_patch_verb_and_sends_json():
    opener = FakeOpener([{}])
    client = redfish_client.RedfishClient("10.0.0.1", "root", "p", opener=opener)
    client.patch("/redfish/v1/Chassis/X", {"LocationIndicatorActive": True})
    request = opener.requests[0]
    assert request.get_method() == "PATCH"
    assert json.loads(request.data) == {"LocationIndicatorActive": True}


def test_transport_errors_become_redfish_error():
    client = _client([OSError("connection refused")])
    with pytest.raises(redfish_client.RedfishError):
        client.get("/redfish/v1")


def test_redact_removes_the_password_from_text():
    client = _client([])
    assert "hunter2" not in client.redact("failed with hunter2 in the url")
    assert "***" in client.redact("failed with hunter2 in the url")


def test_redfish_error_message_never_contains_the_password():
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


def test_resolve_falls_back_when_a_collection_is_empty_or_unreadable():
    client = _client([{"Members": []}, OSError("nope"), {"Members": []}])
    client.resolve()
    assert client.system == redfish_client.DEFAULT_SYSTEM
    assert client.chassis == redfish_client.DEFAULT_CHASSIS
    assert client.manager == redfish_client.DEFAULT_MANAGER
