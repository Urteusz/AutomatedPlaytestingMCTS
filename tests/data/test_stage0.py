"""Frozen benchmark validation tests."""

import unittest

from tools.validate_stage0 import validate_benchmark


class Stage0BenchmarkTests(unittest.TestCase):
    def test_frozen_benchmark_is_valid(self):
        errors, _ = validate_benchmark()
        self.assertEqual([], errors, "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
