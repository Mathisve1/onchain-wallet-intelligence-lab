from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
COLLECTOR=ROOT/"research/archive_inventory/r10a_implementation/collector.py"
SPEC=importlib.util.spec_from_file_location("r10a_collector",COLLECTOR)
assert SPEC and SPEC.loader
mod=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(mod)


class R10AImplementationTests(unittest.TestCase):
    def test_partition_aggregator_counts_before_inside_after_without_wallet_retention(self) -> None:
        summary=mod.new_summary('"5a9941a240118a57f77a4c3ee95b8430-3"',b'x')
        agg=mod.TimestampAggregator(summary)
        block={
            "local_time":"2025-07-27T09:15:00",
            "block_time":"2025-07-27T09:15:00+00:00",
            "block_number":1,
            "events":[
                ["0x"+"1"*40,{"time":1753606799999}],
                ["0x"+"2"*40,{"time":1753607700000}],
                ["0x"+"3"*40,{"time":1753610400000}],
            ],
        }
        agg.add_line(json.dumps(block,separators=(",",":")).encode())
        out=agg.finalize()
        self.assertEqual(out["fill_time_count"],3)
        self.assertEqual(out["fill_time_before_path_hour_count"],1)
        self.assertEqual(out["fill_time_inside_path_hour_count"],1)
        self.assertEqual(out["fill_time_after_path_hour_count"],1)
        self.assertEqual(out["alignment_classification"],"FILL_TIME_SPILLS_OUTSIDE_PATH_HOUR")
        self.assertEqual(out["local_time_parseable_with_explicit_timezone_count"],0)
        self.assertEqual(out["local_time_not_explicitly_zoned_count"],1)
        self.assertNotIn("wallet_address",json.dumps(out))

    def test_strict_alignment_classification(self) -> None:
        summary=mod.new_summary('"5a9941a240118a57f77a4c3ee95b8430-3"',b'x')
        agg=mod.TimestampAggregator(summary)
        block={"local_time":"x","block_time":"2025-07-27T09:00:00Z","block_number":1,"events":[["0x"+"a"*40,{"time":1753606800000}]]}
        agg.add_line(json.dumps(block).encode())
        self.assertEqual(agg.finalize()["alignment_classification"],"FILL_TIME_STRICT_PATH_HOUR_ALIGNED")

    def test_signed_request_is_exact_one_object_requester_pays(self) -> None:
        host,path,headers=mod.build_signed_request(datetime(2026,8,10,11,0,tzinfo=timezone.utc),{"AWS_ACCESS_KEY_ID":"A","AWS_SECRET_ACCESS_KEY":"S","AWS_SESSION_TOKEN":"T"})
        self.assertEqual(host,"hl-mainnet-node-data.s3.ap-northeast-1.amazonaws.com")
        self.assertEqual(path,"/node_fills_by_block/hourly/20250727/9.lz4")
        self.assertEqual(headers["If-Match"],'"5a9941a240118a57f77a4c3ee95b8430-3"')
        self.assertEqual(headers["x-amz-request-payer"],"requester")

    def test_no_economic_fields_processed(self) -> None:
        source=COLLECTOR.read_text()
        for token in ("closedPnl","feeToken","startPosition","sum_abs_px","wallet_feature"):
            self.assertNotIn(token,source)

    def test_dedicated_validator_passes(self) -> None:
        done=subprocess.run([sys.executable,str(ROOT/"governance/validate_r10a_implementation.py")],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(done.returncode,0,done.stdout+done.stderr)
        self.assertIn("R10A_IMPLEMENTATION_VALID",done.stdout)


if __name__=="__main__": unittest.main()
