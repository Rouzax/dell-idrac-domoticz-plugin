"""Redfish HTTP transport over the standard library. The only networking module.

Credentials are redacted from every message that can reach a log. An exception
raised here is caught by the plugin and logged, so its text must never carry the
iDRAC password.
"""

import base64
import json
import ssl
import time
import urllib.error
import urllib.request

ROOT = "/redfish/v1"
# Conventional ids on a 15G monolithic PowerEdge. Used only as a fallback when the
# collections cannot be read; resolve() replaces them with what the server reports.
DEFAULT_SYSTEM = "/redfish/v1/Systems/System.Embedded.1"
DEFAULT_CHASSIS = "/redfish/v1/Chassis/System.Embedded.1"
DEFAULT_MANAGER = "/redfish/v1/Managers/iDRAC.Embedded.1"

_REDACTED = "***"

# Dell's own reference scripts treat these as retryable rather than fatal: iDRAC returns them
# transiently while it is busy. Without a retry a single blip marks every device timed out.
_TRANSIENT_STATUS = frozenset({401, 500, 503})
_RETRY_ATTEMPTS = 3
_RETRY_SLEEP_SECONDS = 2.0


class RedfishError(Exception):
    pass


class RedfishClient:
    def __init__(self, host, username, password, verify_tls=False, timeout=30, opener=None):
        self.host = host
        self.username = username
        self.password = password
        self.timeout = timeout
        self._auth = base64.b64encode(f"{username}:{password}".encode()).decode()
        if opener is not None:
            self._opener = opener
        else:
            context = ssl.create_default_context()
            if not verify_tls:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            self._opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context))
        self._set_paths(DEFAULT_SYSTEM, DEFAULT_CHASSIS, DEFAULT_MANAGER)

    def _set_paths(self, system: str, chassis: str, manager: str) -> None:
        self.system = system
        self.chassis = chassis
        self.manager = manager
        self.thermal = chassis + "/Thermal"
        self.power = chassis + "/Power"
        self.sensors = chassis + "/Sensors"
        self.ethernet = system + "/EthernetInterfaces"
        self.storage_collection = system + "/Storage"
        self.faults = manager + "/LogServices/FaultList/Entries"
        system_id = system.rstrip("/").rsplit("/", 1)[-1]
        self.dell_attributes = f"{manager}/Oem/Dell/DellAttributes/{system_id}"

    def _first_member(self, collection_path: str, fallback: str) -> str:
        try:
            members = self.get(collection_path).get("Members") or []
        except RedfishError:
            return fallback
        for member in members:
            odata_id = member.get("@odata.id")
            if odata_id:
                return odata_id
        return fallback

    def resolve(self) -> bool:
        """Learn the real resource ids instead of assuming the conventional ones.

        Returns True only when all three collections were readable. False means at least one id
        is a conventional fallback rather than something the server reported, so the caller can
        try again rather than treating a guess as settled.
        """
        system = self._first_member(f"{ROOT}/Systems", DEFAULT_SYSTEM)
        chassis = self._first_member(f"{ROOT}/Chassis", DEFAULT_CHASSIS)
        manager = self._first_member(f"{ROOT}/Managers", DEFAULT_MANAGER)
        self._set_paths(system, chassis, manager)
        return not (
            system is DEFAULT_SYSTEM or chassis is DEFAULT_CHASSIS or manager is DEFAULT_MANAGER
        )

    def redact(self, text: str) -> str:
        out = str(text)
        for secret in (self.password, self._auth):
            if secret:
                out = out.replace(secret, _REDACTED)
        return out

    def _request(self, path: str, method: str = "GET", body=None) -> dict:
        url = f"https://{self.host}{path}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Authorization", f"Basic {self._auth}")
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        # Only GET is retried. A POST here can be a power action, and replaying one because the
        # first response was lost could power-cycle a server twice.
        attempts = _RETRY_ATTEMPTS if method == "GET" else 1
        raw = b""
        for attempt in range(attempts):
            last = attempt == attempts - 1
            try:
                with self._opener.open(request, timeout=self.timeout) as response:
                    raw = response.read()
                break
            except urllib.error.HTTPError as exc:
                if exc.code in _TRANSIENT_STATUS and not last:
                    time.sleep(_RETRY_SLEEP_SECONDS)
                    continue
                raise RedfishError(self.redact(f"HTTP {exc.code} for {path}")) from None
            except urllib.error.URLError as exc:
                # urllib wraps a CONNECT-phase timeout in URLError (do_open catches OSError and
                # re-raises it as URLError), so it would slip past the TimeoutError branch below
                # and be retried, which is exactly what that branch exists to prevent. A refused
                # connection is a different URLError and IS worth retrying: it fails in
                # milliseconds.
                if isinstance(exc.reason, TimeoutError):
                    raise RedfishError(
                        self.redact(f"timeout after {self.timeout}s for {path}")
                    ) from None
                if not last:
                    time.sleep(_RETRY_SLEEP_SECONDS)
                    continue
                raise RedfishError(self.redact(f"{type(exc).__name__} for {path}: {exc}")) from None
            except TimeoutError:
                # Deliberately NOT retried. A timeout has already spent its full budget, so a
                # retry multiplies the block. Measured during a real iDRAC restart: the recovering
                # controller accepts connections but does not answer, and three retries at the
                # default 30 s timeout would stall one poll for over 90 seconds.
                raise RedfishError(
                    self.redact(f"timeout after {self.timeout}s for {path}")
                ) from None
            except Exception as exc:
                if not last:
                    time.sleep(_RETRY_SLEEP_SECONDS)
                    continue
                raise RedfishError(self.redact(f"{type(exc).__name__} for {path}: {exc}")) from None
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except ValueError:
            raise RedfishError(self.redact(f"malformed JSON from {path}")) from None

    def get(self, path: str) -> dict:
        return self._request(path)

    def get_expanded(self, path: str, levels: int = 1) -> dict:
        joiner = "&" if "?" in path else "?"
        return self._request(f"{path}{joiner}$expand=*($levels={levels})")

    def select(self, path: str, attribute: str) -> dict:
        joiner = "&" if "?" in path else "?"
        return self._request(f"{path}{joiner}$select={attribute}")

    def post(self, path: str, body: dict) -> dict:
        return self._request(path, method="POST", body=body)

    def patch(self, path: str, body: dict) -> dict:
        return self._request(path, method="PATCH", body=body)
