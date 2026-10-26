"""python -m printer_monitor [--config printers.json] [--once] [--lang en|th|ja] [--port 8080]"""
import argparse
import sys

from . import monitor

LEVEL_MARK = {"ok": "OK  ", "warning": "WARN", "critical": "CRIT"}


def print_once(cfg, lang):
    result = monitor.poll_all(cfg["printers"], cfg["community"])
    for p in result.values():
        att = p["attention"]
        toner = ", ".join(f"{s['name']} {s['percent']}%" for s in p["supplies"]
                          if s["percent"] is not None and "toner" in s["name"].lower())
        pages = f"{p['pageCount']:,} pages" if p["pageCount"] is not None else ""
        print(f"[{LEVEL_MARK[att['level']]}] {p['name']:<16} {p['ip']:<15} {att['headline'][lang]}")
        detail = "  ".join(x for x in (p["model"] or "", pages, toner) if x)
        if detail:
            print(f"       {detail}")
    return 1 if any(p["attention"]["level"] == "critical" for p in result.values()) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="printer_monitor", description="Network printer status over SNMP")
    ap.add_argument("--config", default="printers.json")
    ap.add_argument("--once", action="store_true", help="poll once, print a table and exit (exit code 1 = something critical)")
    ap.add_argument("--lang", default="en", choices=("en", "th", "ja"))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args(argv)
    cfg = monitor.load_config(args.config)
    if args.once:
        return print_once(cfg, args.lang)
    from . import web
    web.serve(cfg, args.config, args.host, args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
