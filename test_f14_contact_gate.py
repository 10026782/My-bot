import unittest
from unittest.mock import patch

import crm


class ContactGateTests(unittest.TestCase):
    def test_israeli_variants_normalize_to_canonical(self):
        expected = "+972548212778"
        for phone in (
            "0548212778",
            "054-821-2778",
            "+972548212778",
            "+972 54-821-2778",
            "972548212778",
            "00972548212778",
            "+972 54-211-6211",
        ):
            with self.subTest(phone=phone):
                normalized = crm._normalize_contact_phone(phone)
                self.assertTrue(normalized.startswith("+972"))
                if "211" in phone:
                    self.assertEqual(normalized, "+972542116211")
                else:
                    self.assertEqual(normalized, expected)

    def test_canonical_foreign_numbers_are_preserved(self):
        for phone in ("+71234567890", "+359888123456"):
            with self.subTest(phone=phone):
                self.assertEqual(crm._normalize_contact_phone(phone), phone)

    def test_israeli_lookup_equivalents_are_bounded_and_exact(self):
        self.assertEqual(
            crm._contact_phone_equivalents("+972548212778"),
            ("+972548212778", "972548212778", "00972548212778", "0548212778"),
        )
        self.assertEqual(crm._contact_phone_equivalents("+71234567890"),
                         ("+71234567890",))

    def test_invalid_phone_does_not_lookup_or_write(self):
        for phone in (None, "", "054-821-27"):
            with self.subTest(phone=phone), patch.object(crm, "_get") as get, \
                    patch.object(crm, "_post") as post:
                result = crm.find_or_create_contact(phone, "Dana")
            self.assertEqual(result.status, "invalid")
            get.assert_not_called()
            post.assert_not_called()

    @patch.object(crm, "_creds_ok", return_value=True)
    def test_zero_matches_creates_once_with_canonical_phone(self, _creds):
        with patch.object(crm, "_get", return_value=[]) as get, patch.object(
                crm, "_post", return_value={"id": "recNEW"}) as post:
            result = crm.find_or_create_contact(
                "054-821-2778", "Dana", email="dana@example.com")
        self.assertIsInstance(result, crm.ContactResult)
        self.assertEqual((result.status, result.record_id), ("created", "recNEW"))
        self.assertEqual(result.normalized_phone, "+972548212778")
        self.assertEqual(get.call_count, 4)
        self.assertEqual(
            [call.args[1] for call in get.call_args_list],
            [
                "{טלפון} = '+972548212778'",
                "{טלפון} = '972548212778'",
                "{טלפון} = '00972548212778'",
                "{טלפון} = '0548212778'",
            ],
        )
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.args[1][crm.ContactFields.PHONE],
                         "+972548212778")

    @patch.object(crm, "_creds_ok", return_value=True)
    def test_one_match_returns_existing_without_post(self, _creds):
        with patch.object(crm, "_get", side_effect=[
                [], [{"id": "recEXISTING"}], [], []]), \
                patch.object(crm, "_post") as post:
            result = crm.find_or_create_contact("+972548212778", "Dana")
        self.assertEqual((result.status, result.record_id), ("existing", "recEXISTING"))
        post.assert_not_called()

    @patch.object(crm, "_creds_ok", return_value=True)
    def test_multiple_matches_are_ambiguous_without_post(self, _creds):
        with patch.object(crm, "_get", side_effect=[
                [{"id": "rec1"}], [{"id": "rec2"}], [{"id": "rec1"}], []]), patch.object(
                crm, "_post") as post:
            result = crm.find_or_create_contact("+972548212778", "Dana")
        self.assertEqual(result.status, "ambiguous")
        self.assertEqual(result.matches, ({"record_id": "rec1"}, {"record_id": "rec2"}))
        post.assert_not_called()

    @patch.object(crm, "_creds_ok", return_value=True)
    def test_lookup_error_is_not_zero_matches(self, _creds):
        with patch.object(crm, "_get", side_effect=RuntimeError("read failed")), \
                patch.object(crm, "_post") as post:
            result = crm.find_or_create_contact("+972548212778", "Dana")
        self.assertEqual(result.status, "lookup_error")
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
