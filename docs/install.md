# Installation

## Before you start

- **A Dell PowerEdge with an iDRAC that speaks Redfish.** Developed and verified against iDRAC 9
  on two 15G PowerEdge servers, one Intel and one AMD. Dell's own Redfish reference documents
  iDRAC 9 and 10. Older iDRAC generations and non-Dell Redfish are untested rather than known
  broken: the plugin discovers resource paths from the service instead of assuming them, and
  guards each subsystem separately, so an endpoint an older iDRAC lacks should degrade to a
  warning rather than break the poll.
- **An iDRAC account.** A read-only account is enough for monitoring. Power control and the
  identify LED additionally need Server Control privilege.
- **Network reachability** from the machine running Domoticz to the iDRAC, on HTTPS port 443.
- **Domoticz with the Python plugin system enabled**, Python 3.11 or newer.

The plugin uses only the Python standard library. There is nothing to `pip install`.

!!! tip "Create a dedicated account"
    Rather than reusing `root`, add a read-only iDRAC user for Domoticz. The password is stored in
    the Domoticz database in cleartext, so limiting what it can do limits what a database leak
    costs you. See [Security](security.md).

## Install

=== "Download a release"

    1. Download the plugin zip from the
       [releases page](https://github.com/Rouzax/dell-idrac-domoticz-plugin/releases).
    2. Unpack it into Domoticz's `plugins` directory so that `plugin.py` ends up at
       `plugins/dell-idrac/plugin.py`.
    3. Restart Domoticz.

=== "Clone the lean dist branch"

    The `dist` branch carries only the runtime files, so `git pull` keeps you updated without
    dragging in tests, docs or the site build.

    ```bash
    cd domoticz/plugins
    git clone -b dist https://github.com/Rouzax/dell-idrac-domoticz-plugin.git dell-idrac
    ```

    Then restart Domoticz. To update later:

    ```bash
    cd domoticz/plugins/dell-idrac && git pull
    ```

=== "Clone the full repository"

    Useful if you intend to run the tests or contribute.

    ```bash
    cd domoticz/plugins
    git clone https://github.com/Rouzax/dell-idrac-domoticz-plugin.git dell-idrac
    ```

## Confirm the plugin loaded

Restart Domoticz and look at the log. You want a line like:

```
Status: PluginSystem: Started, Python version '3.13.5', 3 plugin definitions loaded.
```

The count should be **one higher** than before you installed. If it did not go up, Domoticz could
not parse the plugin manifest, and the new hardware type will not appear in the list. See
[Troubleshooting](faq.md#no-new-hardware-type-appears-in-the-list).

## Add the hardware

1. Go to **Setup** then **Hardware**.
2. Choose type **Dell iDRAC Monitor**.
3. Fill in:
    - **iDRAC Address**: hostname or IP, with no scheme. If you paste `https://...` it is stripped
      for you.
    - **Username** and **Password**.
4. Leave everything else at its default for a first run. In particular leave **Allow Control** at
   `No`; you can turn it on later once you have seen the monitoring working.
5. Click **Add**.

Devices appear after the **first successful poll**, which is one poll interval later (30 seconds
at the default), not instantly. On a typical server you should see somewhere between 30 and 50
devices depending on how many fans, drives, volumes and NICs the machine has, grouped into
several Domoticz Devices by family.

!!! warning "onStart does no network I/O, on purpose"
    Domoticz starts hardware synchronously, so a plugin that contacted an unreachable server
    during startup would stall Domoticz itself for the length of a timeout. This plugin therefore
    contacts the iDRAC for the first time on the first heartbeat, not while starting. That is why
    a wrong address shows up as a log message one poll later rather than immediately.

## Verify it is working

Check the Domoticz log for a line like:

```
Status: Dell iDRAC Monitor: Dell iDRAC Monitor started for <your address>
```

followed a poll interval later by devices appearing under **Setup** then **Devices**, filtered by
the hardware name.

If the iDRAC cannot be reached you will instead see:

```
Error: Dell iDRAC Monitor: iDRAC unreachable, backing off 20s: ...
```

which tells you the address, credentials or network path needs attention. See
[Troubleshooting](faq.md).

## Updating

Replace the files and restart Domoticz. Your devices, their history and their unit numbers are
preserved: the plugin records which unit number belongs to which piece of hardware and never
reshuffles them.
