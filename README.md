# Printer Monitor

See every network printer in the office on one page: toner and paper levels, paper jams,
open covers, pages printed per day, and roughly when each toner will run out.
Messages are in plain English, Thai or Japanese, written for whoever walks up to the printer.

- **No dependencies.** Python 3.9+ standard library only, including a small built-in SNMP client.
- **Any brand.** Reads the standard Printer-MIB (RFC 3805) that network printers publish.
  Built and used daily on Konica Minolta bizhub devices.
- **Read-only.** It only sends SNMP GET requests; it never changes printer settings.

## Quick start

```
git clone https://github.com/tungtrue2518-del/printer-monitor
cd printer-monitor
copy printers.example.json printers.json      # then put your printers' names and IPs in it
python -m printer_monitor --once              # one-off check in the terminal
python -m printer_monitor                     # dashboard on http://127.0.0.1:8080
```

SNMP v1/v2c must be enabled on the printers (it usually is, community `public`).

### Terminal output

```
[OK  ] Warehouse        192.0.2.11      OK
       KONICA MINOLTA bizhub 367  52,300 pages  Toner (Black) 70%
[WARN] Front office     192.0.2.10      Black toner is nearly empty
       KONICA MINOLTA bizhub C251i  17,900 pages  Toner (Cyan) 94%, ... Toner (Black) 8%
[CRIT] Meeting room     192.0.2.12      Paper jam (+1 more)
```

`--once` exits with code 1 when any printer is critical, so it can drive a scheduled alert.

## Options

| Option | Default | |
|---|---|---|
| `--config` | `printers.json` | printer list |
| `--once` | | poll once, print, exit |
| `--lang` | `en` | `en`, `th` or `ja` for `--once` |
| `--host` / `--port` | `127.0.0.1` / `8080` | dashboard address; use `--host 0.0.0.0` to open it to the LAN |

`printers.json`:

| Key | |
|---|---|
| `community` | SNMP community for all printers (a printer can override it) |
| `pollSeconds` | how often the dashboard polls (default 180) |
| `historyFile` | where usage history is kept (default `printer_history.json` next to the config) |
| `printers` | list of `{ "name", "ip" }` |

## What it reports

| | Source (Printer-MIB) |
|---|---|
| Model | `sysDescr` |
| Toner, drums, waste box % | `prtMarkerSuppliesTable` |
| Paper per tray, empty / low | `prtInputTable` |
| Problems: jam, cover open, no paper, toner low/empty, output full, part end of life | `prtAlertTable` codes, explained in plain words with what to do |
| "Every tray is empty" and "not responding" | worked out by this tool (printers do not say it themselves) |
| Pages printed per day / month | `prtMarkerLifeCount`, recorded first and last reading per day |
| Toner run-out date | linear rate since the last cartridge change (needs a day of data and a 2% drop) |

Each printer gets one verdict: **ok**, **warning** (needs attention soon) or **critical** (cannot print until someone acts).

## JSON API

| | |
|---|---|
| `GET /api/status` | latest poll of every printer, with alerts and a one-line headline per language |
| `GET /api/usage` | pages today / this month, last 31 days, monthly totals, toner forecasts |
| `POST /api/refresh` | poll now |

## Tests

```
python -m unittest
```

## License

MIT
