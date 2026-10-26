"""Poll a list of network printers: model, status, supplies, trays, alerts, page count."""
import datetime
import json
import threading

from . import alerts
from .snmp import Session, tcp_reachable

OID_SYSDESCR = "1.3.6.1.2.1.1.1.0"
OID_SYSUPTIME = "1.3.6.1.2.1.1.3.0"
OID_PRINTER_STATUS = "1.3.6.1.2.1.25.3.5.1.1.1"     # hrPrinterStatus
OID_PAGE_COUNT = "1.3.6.1.2.1.43.10.2.1.4.1.1"      # prtMarkerLifeCount: pages printed since manufacture
OID_SUPPLY = "1.3.6.1.2.1.43.11.1.1"                # .6 description .8 max capacity .9 current level
OID_INPUT = "1.3.6.1.2.1.43.8.2.1"                  # .9 max capacity .10 current level .13 name
OID_ALERT = "1.3.6.1.2.1.43.18.1.1"                 # .2 severity .5 group index .7 code .8 description .9 time

STATUS_TEXT = {1: "other", 2: "unknown", 3: "idle", 4: "printing", 5: "warmup"}


def load_config(path):
    """printers.json -> {"community": str, "pollSeconds": int, "printers": [{"name", "ip", ...}]}"""
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("community", "public")
    cfg.setdefault("pollSeconds", 180)
    for p in cfg["printers"]:
        if "name" not in p or "ip" not in p:
            raise ValueError(f"every printer needs a name and an ip: {p!r}")
    return cfg


def read_supplies(s):
    supplies = []
    for row in s.table(OID_SUPPLY, {6: "name", 8: "max", 9: "level"}).values():
        level, cap = row.get("level"), row.get("max")
        percent = None
        if isinstance(level, int) and isinstance(cap, int) and cap > 0 and level >= 0:
            percent = max(0, min(100, round(level * 100 / cap)))
        supplies.append({"name": str(row.get("name") or "").strip(), "percent": percent})
    return supplies


def read_trays(s):
    trays = []
    for row in s.table(OID_INPUT, {13: "name", 9: "capacity", 10: "level"}).values():
        name = str(row.get("name") or "").strip()
        level, cap = row.get("level"), row.get("capacity")
        if level == 0:
            state = "empty"
        elif level == -3:
            state = "ok"            # Printer-MIB: "at least one sheet, exact amount unknown"
        elif isinstance(level, int) and isinstance(cap, int) and cap > 0 and level >= 0:
            state = "low" if level * 100 / cap <= 10 else "ok"
        else:
            state = "unknown"
        trays.append({"name": name, "level": level, "capacity": cap, "state": state,
                      "manualFeed": any(w in name.lower() for w in ("bypass", "manual"))})
    return trays


def read_alerts(s, now):
    uptime = s.get(OID_SYSUPTIME)
    rows = s.table(OID_ALERT, {2: "severity", 5: "group", 7: "code", 8: "desc", 9: "time"})
    found = []
    for r in rows.values():
        a = alerts.explain(r.get("code"), r.get("severity"), r.get("group"), r.get("desc"))
        t = r.get("time")
        # alert time and sysUpTime are both 1/100 s since the printer booted
        raised = None
        if isinstance(uptime, int) and isinstance(t, int) and 0 < t <= uptime:
            raised = now - datetime.timedelta(seconds=(uptime - t) / 100)
        a["raisedAt"] = raised.isoformat(timespec="seconds") if raised else None
        found.append(a)
    return found


def poll_printer(ip, community="public", now=None):
    now = now or datetime.datetime.now()
    with Session(ip, community) as s:
        model = s.get(OID_SYSDESCR)
        if model is None:
            # SNMP off or wrong community: still tell "powered on" from "gone"
            online = tcp_reachable(ip, 80) or tcp_reachable(ip, 9100)
            found, attention = alerts.summarize(online, [], [])
            return {"online": online, "snmp": False, "model": None, "status": None, "supplies": [],
                    "trays": [], "alerts": found, "attention": attention, "pageCount": None}
        trays = read_trays(s)
        found, attention = alerts.summarize(True, read_alerts(s, now), trays)
        status = s.get(OID_PRINTER_STATUS)
        pages = s.get(OID_PAGE_COUNT)
        return {"online": True, "snmp": True, "model": model.strip(),
                "status": STATUS_TEXT.get(status, "unknown"), "supplies": read_supplies(s),
                "trays": trays, "alerts": found, "attention": attention,
                "pageCount": pages if isinstance(pages, int) else None}


def poll_all(printers, community="public"):
    """Polls every printer in parallel: a powered-off printer costs seconds of
    timeouts and should not delay the others. -> {ip: result}"""
    found = {}

    def run(p):
        try:
            data = poll_printer(p["ip"], p.get("community", community))
        except Exception as exc:                    # one bad device must not break the sweep
            fa, att = alerts.summarize(False, [], [])
            data = {"online": False, "snmp": False, "model": None, "status": None, "supplies": [],
                    "trays": [], "alerts": fa, "attention": att, "pageCount": None, "error": repr(exc)}
        found[p["ip"]] = {**p, **data}

    threads = [threading.Thread(target=run, args=(p,), daemon=True) for p in printers]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return {p["ip"]: found[p["ip"]] for p in printers if p["ip"] in found}
