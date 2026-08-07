from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wallet_intelligence.point_in_time import FeatureObservation, eligible_features


class PointInTimeTests(unittest.TestCase):
    def test_future_features_are_excluded(self) -> None:
        rows = [
            FeatureObservation("past", 10, 1),
            FeatureObservation("at_cutoff", 20, 2),
            FeatureObservation("future", 21, 3),
        ]
        self.assertEqual([row.name for row in eligible_features(rows, 20)], ["past", "at_cutoff"])


if __name__ == "__main__":
    unittest.main()
