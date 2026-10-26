import datetime
import os
import tempfile
import unittest

from printer_monitor import history

T0 = datetime.datetime(2026, 10, 1, 9, 0)


def reading(pages, black):
    return {"192.0.2.10": {"name": "Office", "snmp": True, "pageCount": pages,
                           "supplies": [{"name": "Toner (Black)", "percent": black},
                                        {"name": "Waste Toner Box", "percent": 50}]}}


class PagesTest(unittest.TestCase):
    def test_daily_usage(self):
        pages = {"2026-10-01": {"first": 100, "last": 150},
                 "2026-10-02": {"first": 150, "last": 230}}
        self.assertEqual(history.pages_by_day(pages), {"2026-10-01": 50, "2026-10-02": 80})

    def test_counter_reset(self):
        pages = {"2026-10-01": {"first": 900, "last": 1000},
                 "2026-10-02": {"first": 5, "last": 25}}
        self.assertEqual(history.pages_by_day(pages)["2026-10-02"], 20)


class ForecastTest(unittest.TestCase):
    def series(self, values):
        return {(T0 + datetime.timedelta(days=i)).date().isoformat():
                {"first": v, "last": v, "firstAt": (T0 + datetime.timedelta(days=i)).isoformat(),
                 "lastAt": (T0 + datetime.timedelta(days=i)).isoformat()}
                for i, v in enumerate(values)}

    def test_linear_forecast(self):
        f = history.toner_forecast(self.series([50, 45, 40]), None, T0 + datetime.timedelta(days=2))
        self.assertEqual(f["ratePerDay"], 5.0)
        self.assertEqual(f["daysLeft"], 8)
        self.assertEqual(f["emptyBy"], "2026-10-11")

    def test_new_cartridge_restarts(self):
        f = history.toner_forecast(self.series([10, 5, 100, 98]), None, T0 + datetime.timedelta(days=3))
        self.assertEqual(f["ratePerDay"], 2.0)
        self.assertEqual(f["daysLeft"], 49)

    def test_not_enough_data(self):
        f = history.toner_forecast(self.series([80]), None, T0)
        self.assertIsNone(f["daysLeft"])
        self.assertTrue(f["reason"])


class HistoryFileTest(unittest.TestCase):
    def test_record_and_report(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "history.json")
            h = history.History(path)
            h.record(reading(1000, 60), T0)
            h.record(reading(1040, 58), T0 + datetime.timedelta(hours=8))
            h.record(reading(1100, 55), T0 + datetime.timedelta(days=1, hours=8))
            self.assertTrue(os.path.exists(path))
            h2 = history.History(path)                       # survives a restart
            now = T0 + datetime.timedelta(days=1, hours=8)
            rep = h2.report([{"name": "Office", "ip": "192.0.2.10"}], reading(1100, 55), now)
            p = rep["printers"][0]
            self.assertEqual(p["pagesToday"], 60)
            self.assertEqual(p["pagesThisMonth"], 100)
            self.assertEqual([t["name"] for t in p["toner"]], ["Toner (Black)"])   # waste box excluded
            # 60% -> 55% over 32 hours = 3.75%/day, 55 / 3.75 = 14.7 days
            self.assertEqual(p["toner"][0]["ratePerDay"], 3.75)
            self.assertEqual(p["toner"][0]["daysLeft"], 15)


if __name__ == "__main__":
    unittest.main()
