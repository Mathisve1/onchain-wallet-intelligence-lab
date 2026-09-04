from __future__ import annotations

import hashlib
import unittest
from decimal import Decimal

from src.copyability.classify import (
    DIRECTIONAL,
    INSUFFICIENT_FILLS,
    PROBABLE_MARKET_MAKER,
    ClassifierThresholds,
)
from src.copyability.cohort import (
    EVALUABLE,
    REASON_REBATE,
    REASON_SCOPE,
    InstrumentScope,
    characterise,
    cohort_hash,
    freeze_record,
    rebate_dependence,
    scope_share,
    select_cohort,
)
from src.copyability.inputs import SourceFill

D = Decimal
DAY = 86_400_000
START = 1_000
END = 1_000 + DAY
WINDOW = (START, END)

SCOPE = InstrumentScope(
    funding_coins=frozenset({"BTC", "ETH", "SOL", "DOOMED"}),
    candle_complete_coins=frozenset({"BTC", "ETH", "DOOMED"}),
    excluded_coins=frozenset({"DOOMED"}),
)


def fill(
    wallet: str,
    t: int,
    tid: int,
    side: str,
    *,
    coin: str = "BTC",
    size: str = "1",
    fee: str = "0.05",
    closed_pnl: str = "0",
    crossed: bool | None = True,
) -> SourceFill:
    return SourceFill(wallet, coin, t, side, D("100"), D(size), D(fee), D(closed_pnl), tid, crossed=crossed)


def directional_fills(wallet: str, *, coin: str = "BTC", fee: str = "0.05", pnl: str = "1") -> list[SourceFill]:
    """Twenty taker round trips, each held half an hour: plainly directional."""
    rows: list[SourceFill] = []
    for i in range(20):
        base = 2_000 + i * 3_600_000
        rows.append(fill(wallet, base, 2 * i, "B", coin=coin, fee=fee))
        rows.append(fill(wallet, base + 1_800_000, 2 * i + 1, "A", coin=coin, fee=fee, closed_pnl=pnl))
    return rows


def maker_fills(wallet: str) -> list[SourceFill]:
    """Resting, two-sided, ten-second holds: a probable market maker."""
    rows: list[SourceFill] = []
    for i in range(20):
        base = 2_000 + i * 60_000
        rows.append(fill(wallet, base, 2 * i, "B", crossed=False))
        rows.append(fill(wallet, base + 10_000, 2 * i + 1, "A", crossed=False, closed_pnl="1"))
    return rows


class CharacteriseTests(unittest.TestCase):
    def test_a_taker_holding_for_half_an_hour_is_directional(self) -> None:
        profile = characterise("w1", directional_fills("w1"), start_ms=START, end_ms=END)
        self.assertEqual(profile.classification, DIRECTIONAL)
        self.assertEqual(profile.fill_count, 40)
        self.assertEqual(profile.wallet, "w1")

    def test_a_resting_two_sided_wallet_is_a_probable_market_maker(self) -> None:
        profile = characterise("w2", maker_fills("w2"), start_ms=START, end_ms=END)
        self.assertEqual(profile.classification, PROBABLE_MARKET_MAKER)

    def test_a_thin_wallet_is_insufficient_not_directional(self) -> None:
        rows = [fill("w3", 2_000 + i, i, "B") for i in range(3)]
        self.assertEqual(characterise("w3", rows, start_ms=START, end_ms=END).classification, INSUFFICIENT_FILLS)

    def test_fills_outside_the_window_and_other_wallets_do_not_count(self) -> None:
        rows = directional_fills("w4") + [fill("w4", END + 5_000, 900, "B"), fill("other", 3_000, 901, "B")]
        self.assertEqual(characterise("w4", rows, start_ms=START, end_ms=END).fill_count, 40)

    def test_thresholds_are_passed_through(self) -> None:
        rows = [fill("w5", 2_000 + i * 1_000, i, "B") for i in range(3)]
        loose = characterise("w5", rows, start_ms=START, end_ms=END, thresholds=ClassifierThresholds(min_fills=1))
        self.assertEqual(loose.classification, DIRECTIONAL)


class RebateDependenceTests(unittest.TestCase):
    def test_negative_fees_over_gross_closed_profit(self) -> None:
        rows = [
            fill("w", 2_000, 1, "B", fee="-1"),
            fill("w", 3_000, 2, "A", fee="-1", closed_pnl="4"),
            fill("w", 4_000, 3, "A", fee="0.5", closed_pnl="4"),
        ]
        self.assertEqual(rebate_dependence(rows, start_ms=START, end_ms=END), D("0.25"))

    def test_paying_fees_only_is_zero_dependence(self) -> None:
        rows = [fill("w", 2_000, 1, "B"), fill("w", 3_000, 2, "A", closed_pnl="10")]
        self.assertEqual(rebate_dependence(rows, start_ms=START, end_ms=END), D(0))

    def test_losses_do_not_shrink_the_denominator(self) -> None:
        rows = [
            fill("w", 2_000, 1, "A", fee="-1", closed_pnl="2"),
            fill("w", 3_000, 2, "A", fee="0.1", closed_pnl="-100"),
        ]
        self.assertEqual(rebate_dependence(rows, start_ms=START, end_ms=END), D("0.5"))

    def test_no_closed_profit_is_no_measurement_not_zero(self) -> None:
        rows = [fill("w", 2_000, 1, "B", fee="-1"), fill("w", 3_000, 2, "A", fee="-1", closed_pnl="-3")]
        self.assertIsNone(rebate_dependence(rows, start_ms=START, end_ms=END))
        self.assertIsNone(rebate_dependence([], start_ms=START, end_ms=END))

    def test_fills_outside_the_window_are_ignored(self) -> None:
        rows = [
            fill("w", 2_000, 1, "A", fee="-1", closed_pnl="10"),
            fill("w", END + 1_000, 2, "A", fee="-99", closed_pnl="1"),
        ]
        self.assertEqual(rebate_dependence(rows, start_ms=START, end_ms=END), D("0.1"))


class InstrumentScopeTests(unittest.TestCase):
    def test_measured_perps_are_in_scope(self) -> None:
        self.assertTrue(SCOPE.in_scope("BTC"))
        self.assertTrue(SCOPE.in_scope("ETH"))

    def test_spot_and_builder_instruments_are_out(self) -> None:
        self.assertFalse(SCOPE.in_scope("@1"))
        self.assertFalse(SCOPE.in_scope("xyz:1234"))

    def test_an_explicitly_excluded_coin_is_out_even_when_measured(self) -> None:
        self.assertFalse(SCOPE.in_scope("DOOMED"))

    def test_a_coin_missing_from_either_measurement_is_out(self) -> None:
        self.assertFalse(SCOPE.in_scope("SOL"))  # funding but no complete candles
        self.assertFalse(SCOPE.in_scope("PEPE"))  # neither

    def test_the_scope_is_frozen(self) -> None:
        with self.assertRaises(Exception):
            SCOPE.funding_coins = frozenset()  # type: ignore[misc]


class ScopeShareTests(unittest.TestCase):
    def test_share_is_notional_weighted(self) -> None:
        rows = [
            fill("w", 2_000, 1, "B", coin="BTC", size="3"),
            fill("w", 3_000, 2, "B", coin="@1", size="1"),
        ]
        self.assertEqual(scope_share(rows, SCOPE, start_ms=START, end_ms=END), D("0.75"))

    def test_every_flavour_of_out_of_scope_counts_against_the_share(self) -> None:
        rows = [
            fill("w", 2_000, 1, "B", coin="BTC"),
            fill("w", 3_000, 2, "B", coin="@7"),
            fill("w", 4_000, 3, "B", coin="xyz:9"),
            fill("w", 5_000, 4, "B", coin="DOOMED"),
            fill("w", 6_000, 5, "B", coin="SOL"),
        ]
        self.assertEqual(scope_share(rows, SCOPE, start_ms=START, end_ms=END), D("0.2"))

    def test_no_notional_in_the_window_is_zero(self) -> None:
        self.assertEqual(scope_share([], SCOPE, start_ms=START, end_ms=END), D(0))
        outside = [fill("w", END + 1, 1, "B", coin="BTC")]
        self.assertEqual(scope_share(outside, SCOPE, start_ms=START, end_ms=END), D(0))

    def test_fills_outside_the_window_do_not_dilute_the_share(self) -> None:
        rows = [fill("w", 2_000, 1, "B", coin="BTC"), fill("w", END + 1, 2, "B", coin="@1", size="99")]
        self.assertEqual(scope_share(rows, SCOPE, start_ms=START, end_ms=END), D(1))


class SelectCohortTests(unittest.TestCase):
    def candidates(self) -> dict[str, list[SourceFill]]:
        return {
            "0xdirectional": directional_fills("0xdirectional"),
            "0xalsofine": directional_fills("0xalsofine", coin="ETH"),
            "0xmaker": maker_fills("0xmaker"),
            "0xthin": [fill("0xthin", 2_000 + i, i, "B") for i in range(3)],
            "0xrebate": directional_fills("0xrebate", fee="-0.5"),
            "0xspot": directional_fills("0xspot", coin="@1"),
        }

    def test_stage_counts_and_reasons_for_a_mixed_set(self) -> None:
        selection = select_cohort(self.candidates(), scope=SCOPE, characterisation_window=WINDOW)
        self.assertEqual(selection.evaluable, ("0xalsofine", "0xdirectional"))
        self.assertEqual(
            selection.stage_counts,
            {
                "discovered": 6,
                "prefiltered_directional": 4,
                "probable_market_maker": 1,
                "rebate_excluded": 1,
                "scope_excluded": 1,
                "insufficient_fills": 1,
                "evaluable": 2,
            },
        )
        self.assertEqual(
            selection.per_wallet,
            {
                "0xalsofine": EVALUABLE,
                "0xdirectional": EVALUABLE,
                "0xmaker": PROBABLE_MARKET_MAKER,
                "0xrebate": REASON_REBATE,
                "0xspot": REASON_SCOPE,
                "0xthin": INSUFFICIENT_FILLS,
            },
        )
        self.assertEqual(selection.count, 2)

    def test_the_stage_counts_sum_to_discovered(self) -> None:
        counts = select_cohort(self.candidates(), scope=SCOPE, characterisation_window=WINDOW).stage_counts
        self.assertEqual(
            counts["discovered"],
            counts["evaluable"]
            + counts["rebate_excluded"]
            + counts["scope_excluded"]
            + counts["insufficient_fills"]
            + counts["probable_market_maker"],
        )

    def test_classification_is_decided_before_rebate_or_scope(self) -> None:
        # A market maker that is also rebate driven and off scope is counted once.
        rows = [f for f in maker_fills("0xmm")]
        selection = select_cohort({"0xmm": rows}, scope=SCOPE, characterisation_window=WINDOW)
        self.assertEqual(selection.per_wallet["0xmm"], PROBABLE_MARKET_MAKER)
        self.assertEqual(selection.stage_counts["rebate_excluded"], 0)
        self.assertEqual(selection.stage_counts["scope_excluded"], 0)
        self.assertEqual(selection.stage_counts["insufficient_fills"], 0)

    def test_thresholds_are_the_callers_to_move(self) -> None:
        rows = directional_fills("0xrebate", fee="-0.1")  # dependence 0.1
        strict = select_cohort(
            {"0xrebate": rows}, scope=SCOPE, characterisation_window=WINDOW, rebate_max=D("0.05")
        )
        self.assertEqual(strict.per_wallet["0xrebate"], REASON_REBATE)
        loose = select_cohort({"0xrebate": rows}, scope=SCOPE, characterisation_window=WINDOW)
        self.assertEqual(loose.per_wallet["0xrebate"], EVALUABLE)

    def test_a_wallet_with_no_closed_profit_is_not_excluded_for_rebates(self) -> None:
        rows = directional_fills("0xflat", fee="-1", pnl="0")
        selection = select_cohort({"0xflat": rows}, scope=SCOPE, characterisation_window=WINDOW)
        self.assertIsNone(rebate_dependence(rows, start_ms=START, end_ms=END))
        self.assertEqual(selection.per_wallet["0xflat"], EVALUABLE)

    def test_a_half_in_scope_wallet_sits_exactly_on_the_default_minimum(self) -> None:
        rows = directional_fills("0xhalf") + directional_fills("0xhalf", coin="@1")
        rows = [
            SourceFill(f.wallet, f.coin, f.time_ms, f.side, f.price, f.size, f.fee, f.closed_pnl, i, crossed=f.crossed)
            for i, f in enumerate(rows)
        ]
        self.assertEqual(scope_share(rows, SCOPE, start_ms=START, end_ms=END), D("0.5"))
        selection = select_cohort({"0xhalf": rows}, scope=SCOPE, characterisation_window=WINDOW)
        self.assertEqual(selection.per_wallet["0xhalf"], EVALUABLE)
        strict = select_cohort(
            {"0xhalf": rows}, scope=SCOPE, characterisation_window=WINDOW, scope_min=D("0.6")
        )
        self.assertEqual(strict.per_wallet["0xhalf"], REASON_SCOPE)

    def test_rebate_dependence_exactly_at_the_default_threshold_is_excluded(self) -> None:
        rows = directional_fills("0xexact", fee="-0.125")
        self.assertEqual(rebate_dependence(rows, start_ms=START, end_ms=END), D("0.25"))
        selection = select_cohort({"0xexact": rows}, scope=SCOPE, characterisation_window=WINDOW)
        self.assertEqual(selection.per_wallet["0xexact"], REASON_REBATE)

    def test_rebate_dependence_just_below_the_default_threshold_survives(self) -> None:
        rows = directional_fills("0xjustunder", fee="-0.124")
        self.assertEqual(rebate_dependence(rows, start_ms=START, end_ms=END), D("0.248"))
        selection = select_cohort({"0xjustunder": rows}, scope=SCOPE, characterisation_window=WINDOW)
        self.assertEqual(selection.per_wallet["0xjustunder"], EVALUABLE)

    def test_an_empty_candidate_set_selects_nothing(self) -> None:
        selection = select_cohort({}, scope=SCOPE, characterisation_window=WINDOW)
        self.assertEqual(selection.evaluable, ())
        self.assertEqual(selection.stage_counts["discovered"], 0)
        self.assertEqual(selection.per_wallet, {})


class CohortHashTests(unittest.TestCase):
    def test_the_digest_is_of_the_sorted_lowercase_lines(self) -> None:
        expected = hashlib.sha256(b"0xaa\n0xbb\n").hexdigest()
        self.assertEqual(cohort_hash(["0xbb", "0xaa"]), expected)

    def test_order_and_case_do_not_change_the_digest(self) -> None:
        self.assertEqual(cohort_hash(["0xAA", "0xBb"]), cohort_hash(["0xbb", "0xaa"]))

    def test_membership_does(self) -> None:
        self.assertNotEqual(cohort_hash(["0xaa"]), cohort_hash(["0xaa", "0xbb"]))

    def test_an_empty_cohort_hashes_the_empty_text(self) -> None:
        self.assertEqual(cohort_hash([]), hashlib.sha256(b"").hexdigest())


class FreezeRecordTests(unittest.TestCase):
    def wallets(self, n: int) -> list[str]:
        return [f"0x{i:040x}" for i in range(n)]

    def test_one_short_of_the_minimum_is_a_hard_stop_with_no_list(self) -> None:
        record = freeze_record(
            t0_ms=1_700_000_000_000,
            wallets=self.wallets(199),
            plan_commit="abc123",
            stage_counts={"discovered": 500, "evaluable": 199},
        )
        self.assertTrue(record["hard_stop"])
        self.assertEqual(record["evaluable_count"], 199)
        self.assertEqual(record["cohort"], [])
        self.assertEqual(record["cohort_sha256"], cohort_hash([]))
        self.assertEqual(record["attempted_count"], 199)
        self.assertEqual(record["attempted_sha256"], cohort_hash(self.wallets(199)))

    def test_under_a_hard_stop_the_digest_describes_the_empty_cohort(self) -> None:
        attempted = self.wallets(50)
        record = freeze_record(
            t0_ms=1_700_000_000_000, wallets=attempted, plan_commit="abc123", stage_counts={}
        )
        self.assertTrue(record["hard_stop"])
        self.assertEqual(record["cohort"], [])
        self.assertEqual(record["cohort_sha256"], cohort_hash([]))
        self.assertEqual(record["attempted_sha256"], cohort_hash(attempted))

    def test_the_minimum_itself_is_accepted_and_writes_the_list(self) -> None:
        wallets = self.wallets(200)
        record = freeze_record(
            t0_ms=1_700_000_000_000, wallets=wallets, plan_commit="abc123", stage_counts={"evaluable": 200}
        )
        self.assertFalse(record["hard_stop"])
        self.assertEqual(record["evaluable_count"], 200)
        self.assertEqual(record["cohort"], sorted(wallets))
        self.assertEqual(record["cohort_sha256"], cohort_hash(wallets))
        self.assertEqual(record["attempted_count"], 200)
        self.assertEqual(record["attempted_sha256"], cohort_hash(wallets))

    def test_the_minimum_is_the_callers_to_state(self) -> None:
        record = freeze_record(
            t0_ms=1_700_000_000_000, wallets=self.wallets(3), plan_commit="c", stage_counts={}, minimum=3
        )
        self.assertFalse(record["hard_stop"])
        self.assertEqual(len(record["cohort"]), 3)

    def test_the_record_carries_the_timestamp_the_commit_and_the_counts(self) -> None:
        counts = {"discovered": 10, "evaluable": 1}
        record = freeze_record(t0_ms=1_700_000_000_000, wallets=["0xAA"], plan_commit="deadbeef", stage_counts=counts)
        self.assertEqual(record["t0_ms"], 1_700_000_000_000)
        self.assertEqual(record["t0_utc"], "2023-11-14T22:13:20Z")
        self.assertEqual(record["plan_commit"], "deadbeef")
        self.assertEqual(record["stage_counts"], counts)
        self.assertIsNot(record["stage_counts"], counts)

    def test_sub_second_precision_survives_the_iso_stamp(self) -> None:
        record = freeze_record(t0_ms=1_700_000_000_123, wallets=[], plan_commit="c", stage_counts={})
        self.assertEqual(record["t0_utc"], "2023-11-14T22:13:20.123Z")

    def test_the_record_is_json_ready(self) -> None:
        import json

        record = freeze_record(
            t0_ms=1_700_000_000_000, wallets=self.wallets(200), plan_commit="c", stage_counts={"evaluable": 200}
        )
        self.assertEqual(json.loads(json.dumps(record))["evaluable_count"], 200)


if __name__ == "__main__":
    unittest.main()
