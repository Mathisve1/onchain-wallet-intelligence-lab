from __future__ import annotations

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from src.live_data import cli
from src.live_data.config import LiveDataConfig
from src.live_data.storage import LiveDataStore, StorageError

WALLET = "0x" + "ab" * 20


class ArgumentParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = cli.build_parser()

    def test_a_subcommand_is_required(self) -> None:
        with self.assertRaises(SystemExit):
            self.parser.parse_args([])

    def test_unknown_subcommands_are_refused(self) -> None:
        for argv in (["trade"], ["place-order"], ["init"]):
            with self.subTest(argv=argv):
                with self.assertRaises(SystemExit):
                    self.parser.parse_args(argv)

    def test_the_command_set_is_exactly_the_read_only_four(self) -> None:
        self.assertEqual(set(cli._COMMANDS), {"init-db", "backfill", "watch", "status"})

    def test_init_db_uses_the_configured_default_database(self) -> None:
        args = self.parser.parse_args(["init-db"])
        self.assertEqual(args.command, "init-db")
        self.assertEqual(args.db, LiveDataConfig().database_path)

    def test_the_database_path_is_overridable(self) -> None:
        args = self.parser.parse_args(["--db", "other.sqlite3", "status"])
        self.assertEqual(args.db, Path("other.sqlite3"))

    def test_backfill_requires_a_wallet_and_a_window(self) -> None:
        args = self.parser.parse_args(["backfill", "--wallet", "0x" + "AB" * 20, "--days", "30"])
        self.assertEqual(args.wallet, WALLET)  # canonicalized by the argument type
        self.assertEqual(args.days, 30)
        for argv in (
            ["backfill"],
            ["backfill", "--wallet", WALLET],
            ["backfill", "--days", "30"],
            ["backfill", "--wallet", "0xnothex", "--days", "30"],
            ["backfill", "--wallet", WALLET, "--days", "many"],
        ):
            with self.subTest(argv=argv):
                with self.assertRaises(SystemExit):
                    self.parser.parse_args(argv)

    def test_watch_accepts_multiple_wallets_and_coins(self) -> None:
        other = "0x" + "cd" * 20
        args = self.parser.parse_args(
            ["watch", "--wallets", WALLET, other, "--coins", "BTC", "ETH", "--max-iterations", "5"]
        )
        self.assertEqual(args.wallets, [WALLET, other])
        self.assertEqual(args.coins, ["BTC", "ETH"])
        self.assertEqual(args.max_iterations, 5)

    def test_watch_defaults_to_empty_selections_and_a_bounded_loop(self) -> None:
        args = self.parser.parse_args(["watch"])
        self.assertEqual((args.wallets, args.coins), ([], []))
        self.assertEqual(args.max_iterations, cli.DEFAULT_MAX_WATCH_ITERATIONS)

    def test_watch_rejects_a_malformed_wallet_or_coin(self) -> None:
        for argv in (["watch", "--wallets", "0xshort"], ["watch", "--coins", " BTC"]):
            with self.subTest(argv=argv):
                with self.assertRaises(SystemExit):
                    self.parser.parse_args(argv)

    def test_argument_type_helpers_raise_argparse_errors(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            cli._wallet("0xnope")
        with self.assertRaises(argparse.ArgumentTypeError):
            cli._coin("")


class CommandExecutionTests(unittest.TestCase):
    """Only the two commands that need no network are executed here."""

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.db_path = Path(self._tempdir.name) / "nested" / "live.sqlite3"

    def run_cli(self, argv: list[str]) -> tuple[int, str]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.main(argv)
        return code, stdout.getvalue()

    def test_init_db_creates_the_database_and_is_repeatable(self) -> None:
        code, output = self.run_cli(["--db", str(self.db_path), "init-db"])
        self.assertEqual(code, 0)
        self.assertTrue(self.db_path.exists())
        self.assertIn(str(self.db_path), output)
        self.assertEqual(self.run_cli(["--db", str(self.db_path), "init-db"])[0], 0)

    def test_status_reports_counts_and_runs_as_json(self) -> None:
        with LiveDataStore(self.db_path) as store:
            store.upsert_wallet(WALLET, observed_at_ms=1)
            store.start_run("run-1", mode="watch", started_at_ms=1)
        code, output = self.run_cli(["--db", str(self.db_path), "status"])
        report = json.loads(output)
        self.assertEqual(code, 0)
        self.assertEqual(report["counts"]["wallets"], 1)
        self.assertEqual(report["counts"]["fills"], 0)
        self.assertEqual(report["recent_runs"][0]["run_id"], "run-1")

    def test_status_on_an_uninitialized_database_fails_loudly(self) -> None:
        with self.assertRaises(StorageError):
            self.run_cli(["--db", str(self.db_path), "status"])

    def test_watch_without_a_selection_exits_nonzero_before_connecting(self) -> None:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = cli.main(["--db", str(self.db_path), "watch"])
        self.assertEqual(code, 2)
        self.assertIn("requires at least one", stderr.getvalue())
        self.assertFalse(self.db_path.exists())  # no side effect on a rejected command


class ImportSideEffectTests(unittest.TestCase):
    def test_building_the_parser_touches_no_database(self) -> None:
        before = set(Path.cwd().glob("*.sqlite3"))
        cli.build_parser()
        self.assertEqual(set(Path.cwd().glob("*.sqlite3")), before)

    def test_the_module_exposes_main_without_running_it(self) -> None:
        self.assertTrue(callable(cli.main))
        self.assertNotEqual(cli.__name__, "__main__")


if __name__ == "__main__":
    unittest.main()
