# About

## What this is

A Domoticz plugin that monitors Dell PowerEdge servers through the iDRAC's Redfish API, written by [Rouzax](https://github.com/Rouzax).

It is **not affiliated with, endorsed by, or supported by Dell Technologies.** "Dell", "PowerEdge" and "iDRAC" are trademarks of their respective owners and are used here only to describe what the plugin talks to.

## What it has been tested against

Read live from a fleet of Dell PowerEdge machines spanning two generations: R440, R740xd2, DSS8440 (14G) and R750, R7525, R7515 (15G), on iDRAC firmware 7.00 and 7.20, both standalone and OpenManage-managed.

That run covered several states a single test machine cannot produce: GPU power and temperature from a 7-card DSS8440 and a 4-card R7525, servers reporting Critical health from a latched event log with no fault text behind it, NVMe drives, drives in pass-through mode, and machines advertising 39 telemetry reports.

## What it has not been tested against

- **iDRAC 7 and 8, and non-Dell Redfish.** Untested rather than known broken. The plugin discovers what a server offers instead of assuming it, so a missing endpoint should cost you that one subsystem rather than the whole poll.

If you have one, a report saying it worked is as useful as one saying it did not.

## Requirements recap

- Dell PowerEdge with an iDRAC that speaks Redfish, built for iDRAC 9 and 10.
- Domoticz with the Python plugin system enabled, Python 3.11 or newer.
- Standard library only. No third-party runtime dependencies.
- The coloured [bar graphs](devices.md#bar-graphs) additionally need a Domoticz build from 19 August 2026 or later. Everything else works on any Domoticz with plugin support.

## Contributing

Issues and pull requests are welcome at [Rouzax/dell-idrac-domoticz-plugin](https://github.com/Rouzax/dell-idrac-domoticz-plugin).

The test suite runs without any hardware, against recorded Redfish payloads:

```bash
pip install -r requirements-dev.txt
python3 -m pytest
```

Before opening a pull request, please also run:

```bash
ruff check . && ruff format --check .
pyright
```

If you have a PowerEdge model that is not covered, a sanitized payload capture is genuinely useful. Two of the bugs listed above came from exactly that. See `tools/capture_fixtures.py`, and read the sanitization test first: captures must be scrubbed before they go anywhere near a commit.

## Reporting a security issue

Open a [security advisory](https://github.com/Rouzax/dell-idrac-domoticz-plugin/security/advisories/new) rather than a public issue.

## License

MIT. See [LICENSE](https://github.com/Rouzax/dell-idrac-domoticz-plugin/blob/main/LICENSE).
