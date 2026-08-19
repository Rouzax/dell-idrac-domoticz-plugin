# Security

## The iDRAC password is stored in cleartext

Domoticz stores hardware credentials in its database as plain text. This is how Domoticz works generally, not a choice this plugin made, and no plugin can opt out of it.

What follows from that:

- **Treat your Domoticz database and its backups as secrets.** Anyone who can read `domoticz.db` can read the iDRAC password.
- **Use a dedicated iDRAC account, not `root`.** A read-only account is enough for everything on the [Monitoring devices](devices.md) page. Only [power control](control.md) needs more.
- **Do not reuse the password anywhere else.**

## The password never reaches the log

The plugin never logs the password at any debug level, including `Verbose`. Every message that can reach a log passes through a redaction step first, so a password that appears inside an exception string, a URL or an authorization header is replaced before the message is written.

This is verified rather than assumed: a full run at `Verbose` produced zero occurrences of the password anywhere in the Domoticz log.

## TLS verification is off by default

An iDRAC ships with a self-signed certificate, so certificate verification fails on a stock machine. The plugin therefore defaults **Verify TLS certificate** to off.

!!! warning "What 'off' actually means"
    The connection is still **encrypted**, so a passive observer on your network cannot read the password or the data. It is **not authenticated**, so an attacker who can redirect traffic could impersonate the iDRAC and collect the credentials you send it.

If you have installed a certificate that the machine running Domoticz trusts, turn verification on. That is the better configuration and it is one checkbox.

## What the plugin sends and where

The plugin talks to exactly one host: the address you configure. It uses HTTP Basic authentication over HTTPS, which is what Dell's own tooling does.

It makes no other outbound connections. There is no telemetry back to anyone, no update check and no third-party service.

## What it reads and writes

Monitoring is entirely read-only: every request is a `GET`.

The plugin can write to your server in exactly three ways, each behind its own opt-in setting, all of which are off by default:

| Request | What it does | Gate |
|---|---|---|
| `POST` to the system reset action | The power action you selected | **Allow Control**, plus **Allow Force Off and Power Cycle** for the two destructive ones |
| `PATCH` to the chassis | Turns the identify LED on or off | **Allow Control** |
| `PATCH` to the iDRAC attributes | Sets `Telemetry.1.EnableTelemetry` and `TelemetryPowerMetrics.1.EnableTelemetry` to `Enabled` | **Configure iDRAC telemetry** |

With all three settings at their defaults, the plugin cannot change anything on the server.

The telemetry write is worth calling out separately, because it is the one that is not about power control and so is easy to overlook. It exists only to unlock the [per-component power devices](devices.md#per-component-power-needs-a-licence), it writes those two attributes and nothing else, it fires only when per-component power was already found unavailable, and it is attempted at most once per plugin start. It announces itself in the log at Status level before it acts. See [Settings](settings.md#configure-idrac-telemetry).

A `POST` is never retried, even when the response is lost. Replaying a lost reset request could power-cycle a server that already obeyed the first one. Neither is a `PATCH`.

## Reporting a vulnerability

Open a [security advisory](https://github.com/Rouzax/dell-idrac-domoticz-plugin/security/advisories/new) rather than a public issue.
