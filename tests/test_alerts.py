import unittest

from printer_monitor import alerts


def tray(state, manual=False):
    return {"name": "Tray", "state": state, "manualFeed": manual}


class ExplainTest(unittest.TestCase):
    def test_paper_empty_names_the_tray(self):
        a = alerts.explain(808, 4, 2, "No Paper Tray2")
        self.assertEqual(a["kind"], "paper_empty")
        self.assertEqual(a["tray"], 2)
        self.assertEqual(a["title"]["en"], "Tray 2 is out of paper")
        self.assertEqual(a["title"]["th"], "ถาด 2 กระดาษหมด")

    def test_toner_color_from_description(self):
        a = alerts.explain(1101, 3, 1, "Cyan Toner Empty")
        self.assertEqual(a["severity"], "critical")
        self.assertEqual(a["title"]["en"], "Cyan toner is empty")
        self.assertEqual(a["title"]["ja"], "シアントナー切れ")

    def test_unknown_code_keeps_printer_text(self):
        a = alerts.explain(9999, 3, None, "Fixing unit error")
        self.assertEqual(a["kind"], "other")
        self.assertEqual(a["severity"], "critical")
        self.assertEqual(a["title"]["en"], "Fixing unit error")


class SummarizeTest(unittest.TestCase):
    def test_ok(self):
        ordered, att = alerts.summarize(True, [alerts.explain(504)], [tray("ok")])
        self.assertEqual(att["level"], "ok")
        self.assertEqual(att["headline"]["en"], "OK")
        self.assertEqual(len(ordered), 1)          # info alerts are kept, just not counted

    def test_offline(self):
        _, att = alerts.summarize(False, [], [])
        self.assertEqual(att["level"], "critical")
        self.assertIn("not responding", att["headline"]["en"])

    def test_every_tray_empty_ignores_manual_feed(self):
        trays = [tray("empty"), tray("empty"), tray("ok", manual=True)]
        ordered, att = alerts.summarize(True, [], trays)
        self.assertEqual(ordered[0]["kind"], "paper_all_empty")
        self.assertEqual(att["critical"], 1)

    def test_critical_first_and_more_count(self):
        found = [alerts.explain(807, 4, 1, ""), alerts.explain(8, 3, None, "")]
        ordered, att = alerts.summarize(True, found, [tray("ok")])
        self.assertEqual(ordered[0]["kind"], "paper_jam")
        self.assertEqual(att["headline"]["en"], "Paper jam (+1 more)")


if __name__ == "__main__":
    unittest.main()
