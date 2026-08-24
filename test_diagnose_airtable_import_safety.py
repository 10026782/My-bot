#!/usr/bin/env python3
"""diagnose_airtable.py must be side-effect-free on import (Track D-Structure #7)."""

import sys
from unittest.mock import patch


def _blow_up(*args, **kwargs):
    raise AssertionError("requests.get called at import time")


def test_import_does_not_call_network_or_exit():
    sys.modules.pop("diagnose_airtable", None)
    with patch("requests.get", side_effect=_blow_up):
        import diagnose_airtable  # noqa: F401 - import is the assertion


def test_main_is_callable():
    sys.modules.pop("diagnose_airtable", None)
    with patch("requests.get", side_effect=_blow_up):
        import diagnose_airtable
    assert callable(diagnose_airtable.main)


if __name__ == "__main__":
    test_import_does_not_call_network_or_exit()
    test_main_is_callable()
    print("OK — diagnose_airtable import is side-effect-free")
