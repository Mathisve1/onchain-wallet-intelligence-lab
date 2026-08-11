from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from research.archive_inventory.r11a_implementation import network


class FakeResponse:
    def __init__(self, *, status: int, headers: list[tuple[str, str]], body: bytes) -> None:
        self.status = status
        self._headers = headers
        self._body = body
        self._offset = 0
        self.read_calls = 0

    def getheaders(self) -> list[tuple[str, str]]:
        return list(self._headers)

    def read(self, amount: int) -> bytes:
        self.read_calls += 1
        if self._offset >= len(self._body):
            return b""
        value = self._body[self._offset : self._offset + amount]
        self._offset += len(value)
        return value


class FakeConnection:
    response: FakeResponse
    request_args: tuple[object, ...] | None = None

    def __init__(self, *_args, **_kwargs) -> None:
        self.closed = False

    def request(self, *args, **kwargs) -> None:
        type(self).request_args = (args, kwargs)

    def getresponse(self) -> FakeResponse:
        return type(self).response

    def close(self) -> None:
        self.closed = True


class R11ANetworkTests(unittest.TestCase):
    def download(self, response: FakeResponse, destination: Path):
        FakeConnection.response = response
        return network.https_get_to_file(
            host="example.test",
            request_path="/object",
            request_headers={"If-Match": '"etag"'},
            destination=destination,
            expected_etag='"etag"',
            expected_content_length=4,
            maximum_body_bytes=4,
            timeout_seconds=10,
            connection_factory=FakeConnection,
        )

    def test_metadata_is_verified_before_first_body_read(self) -> None:
        response = FakeResponse(
            status=200,
            headers=[
                ("ETag", '"wrong"'),
                ("Content-Length", "4"),
                ("x-amz-request-charged", "requester"),
            ],
            body=b"data",
        )
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "object"
            with self.assertRaises(network.R11ANetworkError):
                self.download(response, destination)
            self.assertEqual(response.read_calls, 0)
            self.assertFalse(destination.exists())

    def test_content_length_metadata_mismatch_is_prebody_failure(self) -> None:
        response = FakeResponse(
            status=200,
            headers=[
                ("ETag", '"etag"'),
                ("Content-Length", "5"),
                ("x-amz-request-charged", "requester"),
            ],
            body=b"data",
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(network.R11ANetworkError):
                self.download(response, Path(directory) / "object")
            self.assertEqual(response.read_calls, 0)

    def test_requester_pays_and_status_are_prebody_gates(self) -> None:
        for status, charged in ((403, "requester"), (200, None)):
            response = FakeResponse(
                status=status,
                headers=[
                    ("ETag", '"etag"'),
                    ("Content-Length", "4"),
                    *(([("x-amz-request-charged", charged)] if charged else [])),
                ],
                body=b"data",
            )
            with self.subTest(status=status, charged=charged), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(network.R11ANetworkError):
                    self.download(response, Path(directory) / "object")
                self.assertEqual(response.read_calls, 0)

    def test_success_streams_exact_body_and_hash(self) -> None:
        response = FakeResponse(
            status=200,
            headers=[
                ("ETag", '"etag"'),
                ("Content-Length", "4"),
                ("x-amz-request-charged", "requester"),
            ],
            body=b"data",
        )
        progress: list[int] = []
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "object"
            FakeConnection.response = response
            result = network.https_get_to_file(
                host="example.test",
                request_path="/object",
                request_headers={"If-Match": '"etag"'},
                destination=destination,
                expected_etag='"etag"',
                expected_content_length=4,
                maximum_body_bytes=4,
                timeout_seconds=10,
                on_progress=progress.append,
                connection_factory=FakeConnection,
            )
            self.assertTrue(result.complete)
            self.assertEqual(result.body_bytes_received, 4)
            self.assertEqual(result.body_sha256, hashlib.sha256(b"data").hexdigest())
            self.assertEqual(destination.read_bytes(), b"data")
            self.assertEqual(progress, [4])

    def test_short_or_oversize_body_fails_and_partial_file_is_removed(self) -> None:
        for body in (b"abc", b"abcde"):
            response = FakeResponse(
                status=200,
                headers=[
                    ("ETag", '"etag"'),
                    ("Content-Length", "4"),
                    ("x-amz-request-charged", "requester"),
                ],
                body=body,
            )
            with self.subTest(body=body), tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / "object"
                with self.assertRaises(network.R11ANetworkError):
                    self.download(response, destination)
                self.assertFalse(destination.exists())
                self.assertFalse(destination.with_name(destination.name + ".partial").exists())


if __name__ == "__main__":
    unittest.main()
