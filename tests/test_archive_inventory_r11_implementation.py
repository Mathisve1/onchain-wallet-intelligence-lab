from __future__ import annotations

import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "research/archive_inventory"
PERMISSION = BASE / "r11_implementation/R11_PERMISSION_POLICY.json"
SELECTION = BASE / "r11/R11_72H_SELECTION.json"


class R11ImplementationTests(unittest.TestCase):
    def test_permission_policy_is_exact_72_object_allowlist(self) -> None:
        permission = json.loads(PERMISSION.read_text(encoding="utf-8"))
        selection = json.loads(SELECTION.read_text(encoding="utf-8"))
        allow = permission["Statement"][0]
        expected = [f"arn:aws:s3:::hl-mainnet-node-data/{row['key']}" for row in selection["exact_targets"]]
        self.assertEqual(allow["Action"], "s3:GetObject")
        self.assertEqual(allow["Resource"], expected)
        self.assertEqual(len(expected), len(set(expected)))
        self.assertEqual(len(expected), 72)
        self.assertTrue(all("*" not in arn for arn in expected))
        compact = json.dumps(permission, separators=(",", ":"), ensure_ascii=True)
        self.assertLessEqual(len(compact), 10240)

    def test_active_day_count_tracks_distinct_utc_path_dates(self) -> None:
        from research.archive_inventory.r11_implementation import collector

        agg = collector.R11Aggregator()
        address = "0x" + "1" * 40
        for index, day in enumerate((28, 29), start=1):
            hour = f"2025-07-{day:02d}T00:00:00Z"
            millis = int(datetime(2025, 7, day, 0, 30, tzinfo=timezone.utc).timestamp() * 1000)
            target = {"path_hour_utc": hour, "key": f"node_fills_by_block/hourly/202507{day:02d}/0.lz4", "size": 1, "etag": '"x"', "known_sha256": None}
            per_hour = {"block_record_count":0,"event_pair_count":0,"local_path_block_path_record_count":0,"local_path_block_previous_record_count":0,"fill_time_before_path_hour_count":0,"fill_time_inside_path_hour_count":0,"fill_time_after_path_hour_count":0,"before_fills_in_local_path_block_previous_records":0,"record_anchored_alignment_violation_count":0}
            record = {
                "local_time": f"2025-07-{day:02d}T00:30:00.000",
                "block_time": f"2025-07-{day:02d}T00:30:00.000",
                "block_number": index,
                "events": [[address, {"coin":"BTC","side":"A","time":millis,"px":"100","sz":"1","closedPnl":"0","tid":index,"crossed":False,"liquidation":None}]],
            }
            agg.add_line(json.dumps(record, separators=(",", ":")).encode(), target, per_hour)
        output, summary = agg.render()
        rows = [json.loads(line) for line in output.decode().splitlines()]
        self.assertEqual(summary["wallet_feature_row_count"], 1)
        self.assertEqual(rows[0]["active_hour_count"], 2)
        self.assertEqual(rows[0]["active_day_count"], 2)
        self.assertEqual(rows[0]["fill_count"], 2)

    def test_workflow_candidates_are_inert_and_uninstalled(self) -> None:
        preflight = BASE / "r11_implementation/workflows/hyperliquid-archive-r11-role-preflight.yml"
        data = BASE / "r11_implementation/workflows/hyperliquid-archive-r11-72h-persistence.yml"
        self.assertTrue(preflight.exists())
        self.assertTrue(data.exists())
        self.assertFalse((ROOT / ".github/workflows/hyperliquid-archive-r11-role-preflight.yml").exists())
        self.assertFalse((ROOT / ".github/workflows/hyperliquid-archive-r11-72h-persistence.yml").exists())
        self.assertIn("workflow_dispatch:", preflight.read_text(encoding="utf-8"))
        self.assertIn("workflow_dispatch:", data.read_text(encoding="utf-8"))

    def test_dedicated_validator_passes(self) -> None:
        done = subprocess.run([sys.executable, "governance/validate_r11_implementation.py"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("R11_IMPLEMENTATION_VALID", done.stdout)


if __name__ == "__main__":
    unittest.main()
