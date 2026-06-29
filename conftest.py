# conftest.py — pytest configuration for the project root
#
# מגדיר markers שה-CI משתמש בהם ב:
#   python -m pytest -m "not integration and not airtable and not live"
#
# שימוש בטסט:
#   import pytest
#   @pytest.mark.airtable
#   def test_something_that_hits_airtable(): ...
#
#   @pytest.mark.integration
#   def test_end_to_end(): ...
#
#   @pytest.mark.live
#   def test_needs_telegram(): ...
#
# טסטים ללא marker רצים תמיד ב-CI.
# טסטים עם marker רצים רק כשמפעילים ידנית:
#   python -m pytest -m "airtable"
#   python -m pytest -m "live"

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "airtable: test requires live Airtable connection (skipped in CI unit run)",
    )
    config.addinivalue_line(
        "markers",
        "integration: end-to-end test requiring full environment (skipped in CI unit run)",
    )
    config.addinivalue_line(
        "markers",
        "live: test requires live external service — Telegram, WhatsApp, Google (skipped in CI unit run)",
    )
