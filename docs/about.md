# About

## What this is

A Domoticz plugin that monitors Dell PowerEdge servers through the iDRAC's Redfish API, written
by [Rouzax](https://github.com/Rouzax).

It is **not affiliated with, endorsed by, or supported by Dell Technologies.** "Dell",
"PowerEdge" and "iDRAC" are trademarks of their respective owners and are used here only to
describe what the plugin talks to.

## How it was built

Every behaviour on these pages was checked against a real server rather than inferred from
documentation, and several of the plugin's rules exist because a real machine contradicted the
obvious assumption:

- A physical power supply was unplugged and re-seated to capture a genuinely degraded payload,
  which revealed that Dell's OEM rollups use `Error` where standard Redfish uses `Critical`, and
  that a rollup can stay red while every individual component reports healthy.
- A second server, with its host powered off and its iDRAC still up, revealed that the chassis
  inlet sensor has a **different id** depending on the model, and that a powered-off host reports
  its maximum DIMM temperature as `-128.0`, a sentinel that would have been written into a
  temperature device permanently.
- The iDRAC was restarted twice to measure what an outage actually looks like, which is why
  refused connections are retried and timeouts are not.
- Two separate defects were found only by reading source: one in CPython's `urllib`, which wraps a
  connect-phase timeout in a different exception class than you would expect, and one in the
  Domoticz core, which does not expose the device attribute the plugin was originally written to
  set.

## Requirements recap

- Dell PowerEdge with an iDRAC that speaks Redfish. Verified on iDRAC 9, on two 15G servers.
- Domoticz with the Python plugin system enabled, Python 3.11 or newer.
- Standard library only. No third-party runtime dependencies.

## Contributing

Issues and pull requests are welcome at
[Rouzax/dell-idrac-domoticz-plugin](https://github.com/Rouzax/dell-idrac-domoticz-plugin).

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

If you have a PowerEdge model that is not covered, a sanitized payload capture is genuinely
useful. Both defects listed above came from exactly that. See `tools/capture_fixtures.py`, and
read the sanitization test first: captures must be scrubbed before they go anywhere near a commit.

## Reporting a security issue

Open a
[security advisory](https://github.com/Rouzax/dell-idrac-domoticz-plugin/security/advisories/new)
rather than a public issue.

## License

MIT. See
[LICENSE](https://github.com/Rouzax/dell-idrac-domoticz-plugin/blob/main/LICENSE).
