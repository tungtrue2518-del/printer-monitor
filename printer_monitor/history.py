"""Usage history: pages printed per day / month and a toner run-out forecast.

One small JSON file. Per printer and per day it keeps only the FIRST and LAST
reading of the page counter and of each toner %, which is all a daily/monthly
report and a "runs out around ..." forecast need. A year of 20 printers is a
few hundred KB.
"""
import datetime
import json
import os
import threading
import time

KEEP_DAYS = 400
REFILL_JUMP = 5            # % rise between readings = a new cartridge was fitted
FORECAST_MIN_DROP = 2      # % drop needed before a forecast means anything
FORECAST_MIN_HOURS = 24    # ... observed over at least this long
SOON_DAYS = 14


def is_toner(name):
    n = (name or "").lower()
    return "toner" in n and "waste" not in n


def _note(day_map, day, value, stamp):
    """Record one reading into {day: {first, last, firstAt, lastAt}}; True if it changed."""
    cur = day_map.get(day)
    if cur is None:
        day_map[day] = {"first": value, "last": value, "firstAt": stamp, "lastAt": stamp}
        return True
    if cur["last"] != value:
        cur["last"], cur["lastAt"] = value, stamp
        return True
    cur["lastAt"] = stamp      # same value: only the timestamp moves (not worth a disk write)
    return False


def pages_by_day(pages):
    """{day: pages printed that day}. A day's usage = its last reading minus the
    previous day's last reading (or its own first reading on day one). A counter
    that went DOWN (board replaced / reset) restarts the count."""
    out, prev = {}, None
    for d in sorted(pages):
        first, last = pages[d]["first"], pages[d]["last"]
        base = prev if prev is not None and prev <= last else first
        out[d] = max(0, last - base)
        prev = last
    return out


def toner_forecast(series, current, now):
    """Linear rate since the most recent cartridge change.
    -> {"ratePerDay", "daysLeft", "emptyBy", "basisHours", "reason"} (reason set when no forecast)."""
    points = []
    for d in sorted(series):
        v = series[d]
        points.append((v["firstAt"], v["first"]))
        if v["lastAt"] != v["firstAt"]:
            points.append((v["lastAt"], v["last"]))
    if isinstance(current, int):
        points.append((now.isoformat(timespec="seconds"), current))
    start = 0
    for i in range(1, len(points)):
        if points[i][1] - points[i - 1][1] >= REFILL_JUMP:
            start = i                   # new cartridge: measure only from here
    points = points[start:]
    empty = {"ratePerDay": None, "daysLeft": None, "emptyBy": None, "basisHours": 0}
    if len(points) < 2:
        return {**empty, "reason": "just started collecting data"}
    t0 = datetime.datetime.fromisoformat(points[0][0])
    t1 = datetime.datetime.fromisoformat(points[-1][0])
    hours = (t1 - t0).total_seconds() / 3600
    drop = points[0][1] - points[-1][1]
    if hours < FORECAST_MIN_HOURS or drop < FORECAST_MIN_DROP:
        return {**empty, "basisHours": round(hours, 1),
                "reason": f"not enough data yet ({hours / 24:.1f} days observed, dropped {max(drop, 0)}%)"}
    rate = drop / (hours / 24)
    left = points[-1][1] / rate
    return {"ratePerDay": round(rate, 2), "daysLeft": round(left),
            "emptyBy": (t1 + datetime.timedelta(days=left)).date().isoformat(),
            "basisHours": round(hours, 1), "reason": ""}


class History:
    def __init__(self, path):
        self.path = path
        self._lock = threading.Lock()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.data = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            self.data = {}

    def _save(self):
        tmp = f"{self.path}.{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(40):       # Windows refuses the replace while a reader has the file open
            try:
                os.replace(tmp, self.path)
                return
            except PermissionError:
                if attempt == 39:
                    raise
                time.sleep(0.025)

    def record(self, printers, now=None):
        """printers = poll_all() result. Saves only when something changed."""
        now = now or datetime.datetime.now()
        day, stamp = now.date().isoformat(), now.isoformat(timespec="seconds")
        cutoff = (now.date() - datetime.timedelta(days=KEEP_DAYS)).isoformat()
        with self._lock:
            changed = False
            for ip, p in printers.items():
                if not p.get("snmp"):
                    continue
                entry = self.data.setdefault(ip, {"pages": {}, "toner": {}})
                entry["name"] = p.get("name")
                if isinstance(p.get("pageCount"), int):
                    changed |= _note(entry["pages"], day, p["pageCount"], stamp)
                for s in p.get("supplies") or []:
                    if is_toner(s.get("name")) and isinstance(s.get("percent"), int):
                        changed |= _note(entry["toner"].setdefault(s["name"], {}), day, s["percent"], stamp)
                for series in [entry["pages"], *entry["toner"].values()]:
                    for d in [d for d in series if d < cutoff]:
                        del series[d]
                        changed = True
            if changed:
                self._save()

    def report(self, printers, live, now=None):
        """Per printer: pages today / this month, last 31 days, months, toner forecasts."""
        now = now or datetime.datetime.now()
        today = now.date()
        month = today.strftime("%Y-%m")
        with self._lock:
            hist = json.loads(json.dumps(self.data))
        out = []
        for p in printers:
            h = hist.get(p["ip"], {"pages": {}, "toner": {}})
            per_day = pages_by_day(h.get("pages", {}))
            months = {}
            for d, n in per_day.items():
                months[d[:7]] = months.get(d[:7], 0) + n
            current = {s["name"]: s.get("percent") for s in (live.get(p["ip"]) or {}).get("supplies") or []}
            toner = []
            for name in sorted(set(h.get("toner", {})) | {n for n in current if is_toner(n)}):
                f = toner_forecast(h.get("toner", {}).get(name, {}), current.get(name), now)
                level = "unknown" if f["daysLeft"] is None else "soon" if f["daysLeft"] <= SOON_DAYS else "ok"
                toner.append({"name": name, "percent": current.get(name), "level": level, **f})
            out.append({
                "ip": p["ip"], "name": p["name"],
                "pagesToday": per_day.get(today.isoformat()),
                "pagesThisMonth": months.get(month),
                "historySince": min(per_day) if per_day else None,
                "daily": [{"date": (today - datetime.timedelta(days=i)).isoformat(),
                           "pages": per_day.get((today - datetime.timedelta(days=i)).isoformat())}
                          for i in range(30, -1, -1)],
                "monthly": [{"month": m, "pages": n} for m, n in sorted(months.items())],
                "toner": toner,
            })
        return {"generatedAt": now.isoformat(timespec="seconds"), "printers": out}
