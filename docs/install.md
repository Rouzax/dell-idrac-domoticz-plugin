# Installation

## Before you start

- **A Dell PowerEdge with an iDRAC that speaks Redfish.** Built for iDRAC 9 and 10. Older iDRAC generations and non-Dell Redfish are untested rather than known broken: the plugin asks the server what it offers instead of assuming, and handles each subsystem separately, so an endpoint your iDRAC lacks costs you that one subsystem rather than the whole poll.
- **An iDRAC account.** A read-only account is enough for monitoring. Power control and the identify LED additionally need Server Control privilege.
- **Network reachability** from the machine running Domoticz to the iDRAC, on HTTPS port 443.
- **Domoticz with the Python plugin system enabled**, Python 3.11 or newer.

The plugin uses only the Python standard library. There is nothing to `pip install`.

!!! tip "Create a dedicated account"
    Rather than reusing `root`, add a read-only iDRAC user for Domoticz. The password is stored in the Domoticz database in cleartext, so limiting what it can do limits what a database leak costs you. See [Security](security.md).

!!! note "Bar graphs need a recent Domoticz"
    Everything on this site works on any Domoticz with the Python plugin system. The coloured threshold bars described under [Bar graphs](devices.md#bar-graphs) additionally need a build that includes the plugin `Color` fix ([domoticz/domoticz#6968](https://github.com/domoticz/domoticz/pull/6968), merged 19 August 2026). On an older build Domoticz discards the bands and the cards show no bar. Nothing else is affected, and no error is logged.

## Step 1: Install the plugin

Pick whichever way suits you. All three put the plugin at `.../domoticz/plugins/dell-idrac/plugin.py`.

=== "Git dist branch (recommended)"

    The leanest install and the easiest to update: the `dist` branch carries only the files needed to run the plugin, with none of the tests, docs or site build.

    ```bash
    cd /opt/domoticz/plugins            # adjust to your Domoticz install path
    git clone -b dist --single-branch https://github.com/Rouzax/dell-idrac-domoticz-plugin.git dell-idrac
    ```

    To update later:

    ```bash
    cd /opt/domoticz/plugins/dell-idrac && git pull
    ```

=== "Download a release (no git)"

    1. Open the [releases page](https://github.com/Rouzax/dell-idrac-domoticz-plugin/releases) and download `dell-idrac-vX.Y.Z.zip` from the latest release.
    2. Unzip it into your Domoticz `plugins` directory. The zip already contains a `dell-idrac` folder, so you end up with `.../domoticz/plugins/dell-idrac/plugin.py`.

    To update, download the newer zip and replace the folder.

=== "Full repository (developers)"

    Useful only if you intend to run the tests or contribute. It pulls in the test suite, the fixtures and the documentation source as well as the plugin.

    ```bash
    cd /opt/domoticz/plugins
    git clone https://github.com/Rouzax/dell-idrac-domoticz-plugin.git dell-idrac
    ```

    To update, run `git pull` inside the folder, the same as the dist branch.

Whichever route you take, `plugin.py` must sit directly inside its own folder under `plugins`. The folder name itself does not matter, but `dell-idrac` is what the release zip and the docs use.

## Step 2: Restart Domoticz

Domoticz only scans the plugins directory at startup, so restart the Domoticz service or container now.

## Step 3: Confirm the plugin loaded

Look at the Domoticz log after the restart. You want a line like:

```
Status: PluginSystem: Started, Python version '3.13.5', 3 plugin definitions loaded.
```

The count should be **one higher** than before you installed. If it did not go up, Domoticz could not parse the plugin manifest, and the new hardware type will not appear in the list. See [Troubleshooting](faq.md#no-new-hardware-type-appears-in-the-list).

## Step 4: Add the hardware

1. Go to **Setup** then **Hardware**.
2. Choose type **Dell iDRAC Monitor**.
3. Fill in:
    - **iDRAC Address**: hostname or IP, with no scheme. If you paste `https://...` it is stripped for you.
    - **Username** and **Password**.
4. Leave everything else at its default for a first run. In particular leave **Allow Control** at `No`; you can turn it on later once you have seen the monitoring working.
5. Click **Add**.

Devices appear after the **first successful poll**, which is one poll interval later (30 seconds at the default), not instantly. On a typical server you should see somewhere between 30 and 50 devices depending on how many fans, drives, volumes and NICs the machine has, grouped into several Domoticz Devices by family. See [One Domoticz Device per family](internals.md#one-domoticz-device-per-family) for why there is more than one entry.

!!! tip "Domoticz has to be willing to accept new devices"
    If the hardware is added but no devices ever appear, check **Setup** then **Settings** then **System** and make sure **Accept new Hardware Devices** is enabled. Domoticz silently drops devices from new hardware while that is off.

!!! warning "onStart does no network I/O, on purpose"
    Domoticz starts hardware synchronously, so a plugin that contacted an unreachable server during startup would stall Domoticz itself for the length of a timeout. This plugin therefore contacts the iDRAC for the first time on the first heartbeat, not while starting. That is why a wrong address shows up as a log message one poll later rather than immediately.

## Verify it is working

Check the Domoticz log for a line like:

```
Status: Dell iDRAC Monitor: Dell iDRAC Monitor started for <your address>
```

followed a poll interval later by devices appearing under **Setup** then **Devices**, filtered by the hardware name.

If the iDRAC cannot be reached you will instead see:

```
Error: Dell iDRAC Monitor: iDRAC unreachable, backing off 20s: ...
```

which tells you the address, credentials or network path needs attention. See [Troubleshooting](faq.md).

## Updating

If you installed from the `dist` branch:

```bash
cd /opt/domoticz/plugins/dell-idrac && git pull
```

Otherwise replace the files with the newer release. Either way, restart Domoticz afterwards.

Your devices, their history and their unit numbers are preserved: the plugin records which unit number belongs to which piece of hardware and never reshuffles them.
