from __future__ import annotations

import dataclasses
import unittest

from research.archive_inventory.r11a_implementation import limits, runtime


def targets(count: int = 3) -> tuple[runtime.RuntimeTarget, ...]:
    return tuple(
        runtime.RuntimeTarget(
            object_ordinal_zero_based=index,
            path_hour_utc=f"2025-07-28T{index:02d}:00:00Z",
            source_object_key=f"node_fills_by_block/hourly/20250728/{index}.lz4",
            expected_etag=f'"etag-{index}"',
            expected_content_length=10 + index,
            expected_compressed_object_sha256=f"{index + 1:064x}",
        )
        for index in range(count)
    )


class R11ARuntimeGuardTests(unittest.TestCase):
    def test_runtime_reserve_fails_before_hard_timeout(self) -> None:
        values = iter((0, 1_000_000_000, 1_700_000_000))
        small = dataclasses.replace(
            limits.DEFAULT_LIMITS,
            maximum_runtime_seconds=2,
            post_measurement_packaging_reservation_seconds=1,
        )
        guard = runtime.RuntimeGuard(small, monotonic_ns=lambda: next(values))
        self.assertEqual(guard.check("first"), 1000)
        with self.assertRaises(runtime.R11ARuntimeError):
            guard.check("second")

    def test_negative_monotonic_delta_fails_closed(self) -> None:
        values = iter((10, 9))
        guard = runtime.RuntimeGuard(monotonic_ns=lambda: next(values))
        with self.assertRaises(runtime.R11ARuntimeError):
            guard.elapsed_milliseconds()


class R11AExecutionEvidenceStateTests(unittest.TestCase):
    def state(self) -> runtime.ExecutionEvidenceState:
        small = dataclasses.replace(
            limits.DEFAULT_LIMITS,
            maximum_get_object_requests=3,
        )
        return runtime.ExecutionEvidenceState(targets(), small)

    def test_initial_state_has_exact_unattempted_rows(self) -> None:
        state = self.state()
        rows = state.object_rows()
        self.assertEqual(len(rows), 3)
        self.assertTrue(
            all(
                row["processing_status"]
                == "UNATTEMPTED_AFTER_FAIL_CLOSED_STOP"
                and row["last_completed_stage"] == "UNATTEMPTED"
                and row["get_object_request_count"] == 0
                for row in rows
            )
        )

    def test_object_lifecycle_records_partial_and_complete_stages(self) -> None:
        state = self.state()
        state.mark_request_sent(0)
        state.mark_response_metadata(0, etag='"etag-0"', content_length=10)
        state.mark_body_progress(0, 4)
        partial = state.object_rows()[0]
        self.assertEqual(partial["processing_status"], "BODY_READ_FAILED_AFTER_RESPONSE_METADATA")
        self.assertEqual(partial["compressed_response_body_bytes_received"], 4)
        state.mark_body_progress(0, 10)
        state.mark_body_complete(0, sha256="1".zfill(64))
        first = {"decompressed_byte_count": 100, "pass_ordinal_one_based": 1}
        second = {"decompressed_byte_count": 100, "pass_ordinal_one_based": 2}
        state.mark_first_parse(0, first)
        state.mark_second_parse(0, second)
        complete = state.object_rows()[0]
        self.assertEqual(complete["processing_status"], "COMPLETE_TWO_LOCAL_PASSES")
        self.assertEqual(complete["last_completed_stage"], "SECOND_LOCAL_PARSE_COMPLETE")
        self.assertEqual(complete["get_object_request_count"], 1)
        self.assertEqual(complete["retry_count"], 0)

    def test_second_request_for_same_object_is_rejected(self) -> None:
        state = self.state()
        state.mark_request_sent(0)
        with self.assertRaises(runtime.R11ARuntimeError):
            state.mark_request_sent(0)

    def test_stop_ledger_has_exact_one_trigger_and_later_not_reached(self) -> None:
        state = self.state()
        state.trigger(
            "HTTP_OR_REQUESTER_PAYS_FAILURE",
            phase="AFTER_EACH_REQUEST_ATTEMPT",
            inputs={"first_failed_object_ordinal": 1},
        )
        rows = state.stop_rows()
        self.assertEqual(len(rows), len(runtime.STOP_CONDITIONS))
        triggered = [row for row in rows if row["evaluation_status"] == "TRIGGERED"]
        self.assertEqual(len(triggered), 1)
        self.assertEqual(triggered[0]["stop_condition"], "HTTP_OR_REQUESTER_PAYS_FAILURE")
        trigger_index = runtime.STOP_CONDITIONS.index("HTTP_OR_REQUESTER_PAYS_FAILURE")
        self.assertTrue(
            all(
                row["evaluation_status"] == "NOT_REACHED_AFTER_EARLIER_STOP"
                for row in rows[trigger_index + 1 :]
            )
        )

    def test_unknown_stop_condition_and_noncanonical_target_order_fail(self) -> None:
        state = self.state()
        with self.assertRaises(runtime.R11ARuntimeError):
            state.trigger("UNKNOWN", phase="X", inputs={})
        small = dataclasses.replace(
            limits.DEFAULT_LIMITS,
            maximum_get_object_requests=3,
        )
        reordered = (targets()[1], targets()[0], targets()[2])
        with self.assertRaises(runtime.R11ARuntimeError):
            runtime.ExecutionEvidenceState(reordered, small)


if __name__ == "__main__":
    unittest.main()
