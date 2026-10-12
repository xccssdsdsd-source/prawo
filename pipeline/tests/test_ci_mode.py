"""Testy trybu --ci i obslugi pustych odpowiedzi (swiezo ogloszone akty)."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import update_data as u  # noqa: E402


class Empty:
    def get(self, url):
        return 200, b""


def target(kat="podstawowe"):
    return {"kind": "main", "kategoria": kat, "status": "obowiązujący", "changeDate": "2026-10-12T00:00:00",
            "item": {"textHTML": True, "textPDF": True, "year": 2026, "pos": 1}}


class EmptyBody(unittest.TestCase):
    def test_empty_200_is_no_text_with_retry_not_failure(self):
        d = Path(tempfile.mkdtemp())
        r = u.run_job(Empty(), d, {"key": "DU/2026/1", "mode": "add", "target": target(), "entry": None})
        self.assertEqual(r["outcome"], "no_text")
        self.assertTrue(r.get("retry"))

    def test_apply_result_sets_retry_until_and_plan_retries(self):
        store = u.Store(Path(tempfile.mkdtemp()), True)
        t = target()
        counters = {"added": 0, "changed": 0, "same": 0, "failed": 0, "no_text": 0}
        u.apply_result(store, {"key": "DU/2026/1", "outcome": "no_text", "retry": True, "reason": "x"}, t, counters)
        e = store.manifest["DU/2026/1"]
        self.assertTrue(e["no_text"])
        self.assertGreaterEqual(e["retry_until"], datetime.now().date().isoformat())
        meta = type("M", (), {"targets": {"DU/2026/1": t}, "ok_years": {("DU", 2026)}, "status_by_key": {}})()
        plan = u.make_plan(store.manifest, meta, Path(tempfile.mkdtemp()), False)
        self.assertIn("DU/2026/1", plan["add"])          # ponowienie mimo tego samego changeDate
        e["retry_until"] = (datetime.now() - timedelta(days=1)).date().isoformat()
        plan = u.make_plan(store.manifest, meta, Path(tempfile.mkdtemp()), False)
        self.assertNotIn("DU/2026/1", plan["add"])       # po terminie - koniec ponawiania


class CiPlan(unittest.TestCase):
    def setUp(self):
        self.t = target()
        self.manifest = {"DU/2026/1": {"status": "obowiązujący", "changeDate": "2026-10-12T00:00:00",
                                       "kategoria": "podstawowe", "files": ["podstawowe/DU_2026_1.html"]}}
        self.meta = type("M", (), {"targets": {"DU/2026/1": self.t}, "ok_years": {("DU", 2026)},
                                   "status_by_key": {}})()

    def tearDown(self):
        u.CI_MODE = False

    def test_without_ci_missing_local_file_is_repaired(self):
        u.CI_MODE = False
        plan = u.make_plan(self.manifest, self.meta, Path(tempfile.mkdtemp()), False)
        self.assertEqual(plan["repair"], ["DU/2026/1"])

    def test_ci_missing_local_file_is_not_repaired(self):
        u.CI_MODE = True
        plan = u.make_plan(self.manifest, self.meta, Path(tempfile.mkdtemp()), False)
        self.assertEqual(plan["repair"], [])
        self.assertEqual(plan["unchanged"], 1)

    def test_ci_changed_date_is_checked(self):
        u.CI_MODE = True
        self.t["changeDate"] = "2026-10-13T00:00:00"
        plan = u.make_plan(self.manifest, self.meta, Path(tempfile.mkdtemp()), False)
        self.assertEqual(plan["check"], ["DU/2026/1"])


if __name__ == "__main__":
    unittest.main()
