"""Tests for the L2 cohort pipeline's ``discover`` path (phase 5).

Split out of ``test_live_data_cohort_pipeline.py`` (T5b-FIX) to keep both
files under the repository's line limit. No network: the tape session is a
fake runner and the candidate reader is either that runner's own in-memory
log or a hand-written fake.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from research.wallet_copyability.live_data_collector.cohort_pipeline import (
    DEFAULT_CANDIDATE_ORDER,
    UNMEASURED_COINS,
    discover,
    excluded_coins,
    iterations_for_seconds,
    partition_coins,
    read_candidate_file,
)

EVAL_WALLET = "0x" + "11" * 20
MAKER_WALLET = "0x" + "22" * 20


def _silent(_message: str) -> None:
    """Swallow the progress lines the commands print."""


class FakeSessionRunner:
    """A tape session that discovers a fixed batch of wallets each time."""

    def __init__(self, batches: list[list[str]]) -> None:
        self.batches = batches
        self.calls: list[tuple[tuple[str, ...], int, int]] = []
        self.found: list[str] = []

    def __call__(self, coins, index: int, max_iterations: int) -> dict:
        self.calls.append((tuple(coins), index, max_iterations))
        batch = self.batches[index] if index < len(self.batches) else []
        self.found.extend(batch)
        return {"run_id": f"session-{index}", "wallets_discovered": len(batch)}

    def read_candidates(self, limit: int) -> list[str]:
        return list(dict.fromkeys(self.found))[:limit]


class DiscoveryFilterTests(unittest.TestCase):
    def test_spot_and_hip3_coins_never_reach_the_subscription(self) -> None:
        kept, dropped = partition_coins(["BTC", "@107", "xyz:GOLD", "ETH"])
        self.assertEqual(kept, ("BTC", "ETH"))
        self.assertEqual(dropped, ("@107", "xyz:GOLD"))

    def test_the_three_unmeasured_coins_are_always_recorded_as_excluded(self) -> None:
        self.assertEqual(UNMEASURED_COINS, ("xyz:BRENTOIL", "xyz:CRWV", "xyz:CXMT"))
        self.assertEqual(
            excluded_coins(["BTC", "@107"]),
            ("@107", "xyz:BRENTOIL", "xyz:CRWV", "xyz:CXMT"),
        )

    def test_a_session_length_becomes_a_frame_budget(self) -> None:
        # 1000 frames in 254 seconds on the L1 tape, so five minutes is ~1181.
        self.assertEqual(iterations_for_seconds(254.0), 1000)
        self.assertGreater(iterations_for_seconds(300.0), iterations_for_seconds(60.0))


class DiscoverTests(unittest.TestCase):
    def test_it_stops_as_soon_as_the_target_is_reached(self) -> None:
        runner = FakeSessionRunner([["0xa"], ["0xb", "0xc"], ["0xd"]])
        clock = iter(range(1, 100))
        report = discover(
            coins=["BTC", "@107", "xyz:GOLD"],
            run_session=runner,
            read_candidates=runner.read_candidates,
            target=3,
            max_sessions=5,
            session_seconds=254.0,
            clock_ms=lambda: next(clock),
            log=_silent,
        )
        self.assertEqual(len(runner.calls), 2, "a third session ran past the target")
        self.assertEqual(report["candidate_count"], 3)
        self.assertEqual(report["candidates"], ["0xa", "0xb", "0xc"])
        self.assertEqual(report["coins"], ["BTC"])
        self.assertEqual(report["target"], 3)
        self.assertEqual([call[0] for call in runner.calls], [("BTC",), ("BTC",)])
        self.assertEqual(runner.calls[0][2], 1000)
        self.assertIn("xyz:BRENTOIL", report["excluded_coins"])
        self.assertEqual([entry["candidates_after"] for entry in report["sessions"]], [1, 3])

    def test_the_session_cap_bounds_a_run_that_never_reaches_the_target(self) -> None:
        runner = FakeSessionRunner([["0xa"], [], []])
        report = discover(
            coins=["BTC"],
            run_session=runner,
            read_candidates=runner.read_candidates,
            target=600,
            max_sessions=2,
            log=_silent,
        )
        self.assertEqual(len(runner.calls), 2)
        self.assertEqual(report["candidate_count"], 1)

    def test_a_failed_session_is_recorded_and_the_run_continues(self) -> None:
        def runner(coins, index, max_iterations):
            if index == 0:
                raise RuntimeError("socket closed")
            return {"wallets_discovered": 1}

        report = discover(
            coins=["BTC"],
            run_session=runner,
            read_candidates=lambda limit: ["0xa"],
            target=600,
            max_sessions=2,
            log=_silent,
        )
        self.assertIn("RuntimeError: socket closed", report["sessions"][0]["error"])
        self.assertEqual(len(report["sessions"]), 2)

    def test_the_discover_file_is_written_and_reads_back(self) -> None:
        runner = FakeSessionRunner([[EVAL_WALLET, MAKER_WALLET]])
        report = discover(
            coins=["BTC"],
            run_session=runner,
            read_candidates=runner.read_candidates,
            target=2,
            max_sessions=3,
            log=_silent,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "L2_DISCOVERY_001.json"
            path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            self.assertEqual(read_candidate_file(path), sorted([EVAL_WALLET, MAKER_WALLET]))

    def test_the_evidence_discloses_the_candidate_ranking_and_its_bias(self) -> None:
        runner = FakeSessionRunner([["0xa", "0xb"]])
        report = discover(
            coins=["BTC"],
            run_session=runner,
            read_candidates=runner.read_candidates,
            target=2,
            max_sessions=1,
            log=_silent,
        )
        self.assertIn("candidate_order", report)
        self.assertIn("selection_note", report)
        self.assertIn("trade_count", report["candidate_order"])
        self.assertEqual(report["candidate_order"], DEFAULT_CANDIDATE_ORDER)
        self.assertTrue(report["selection_note"])

    def test_duplicate_candidates_from_the_reader_are_deduplicated(self) -> None:
        report = discover(
            coins=["BTC"],
            run_session=lambda coins, index, max_iterations: {},
            read_candidates=lambda limit: ["0xa", "0xa", "0xb"],
            target=2,
            max_sessions=1,
            log=_silent,
        )
        self.assertEqual(report["candidate_count"], 2)
        self.assertEqual(report["candidates"], ["0xa", "0xb"])


if __name__ == "__main__":
    unittest.main()
