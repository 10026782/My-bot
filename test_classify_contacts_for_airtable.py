import unittest

from scripts.classify_contacts_for_airtable import InputRecord, classify_group


class AmbiguousOdClassificationTests(unittest.TestCase):
    def classify(self, name: str):
        return classify_group([InputRecord(name, "050-123-4567", "test")], "test-batch")

    def test_trade_context_suppresses_ambiguous_od(self):
        result = self.classify("עוד מתקין דלתות")

        self.assertEqual(result.values["Role Category"], "operator")
        self.assertFalse(any(match.role == "expert" for match in result.matches))
        self.assertIn("Ignored ambiguous token 'עוד'", result.values["Classification Reason"])

    def test_standalone_od_is_medium_expert_and_requires_review(self):
        result = self.classify("עוד אהרוני")

        self.assertEqual(result.values["Role Category"], "expert")
        self.assertEqual(result.values["Classification Confidence"], "medium")
        self.assertEqual(result.values["Review Required"], "true")

    def test_od_with_legal_context_is_medium_and_requires_review(self):
        result = self.classify("עוד משרד חוזים")

        self.assertEqual(result.values["Role Category"], "expert")
        self.assertEqual(result.values["Classification Confidence"], "medium")
        self.assertEqual(result.values["Review Required"], "true")

    def test_exact_lawyer_tokens_remain_high_confidence(self):
        for name in ('עו"ד אהרוני', "עו״ד אהרוני", "עורך דין אהרוני", "עורכת דין כהן"):
            with self.subTest(name=name):
                result = self.classify(name)
                self.assertEqual(result.values["Role Category"], "expert")
                self.assertEqual(result.values["Classification Confidence"], "high")

    def test_trade_only_context_stays_out_of_expert(self):
        result = self.classify("עוד חשמל")

        self.assertEqual(result.values["Role Category"], "other")
        self.assertFalse(any(match.role == "expert" for match in result.matches))
        self.assertEqual(result.values["Review Required"], "true")


if __name__ == "__main__":
    unittest.main()
