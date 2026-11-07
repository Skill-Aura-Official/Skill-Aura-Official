import json
import unittest

from history import unexpected_failure_category


class PublicDiagnosticsTests(unittest.TestCase):
    def test_only_constant_labels_are_returned(self):
        cases = [
            (json.JSONDecodeError("private payload", "unpublished", 0), "invalid-json"),
            (TimeoutError("private endpoint"), "timeout"),
            (KeyError("private identifier"), "missing-data-field"),
            (ValueError("private credential"), "invalid-data-value"),
            (RuntimeError("private repository"), "unexpected"),
        ]
        for error, expected in cases:
            with self.subTest(kind=type(error).__name__):
                self.assertEqual(unexpected_failure_category(error), expected)
