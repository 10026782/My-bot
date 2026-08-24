"""Focused PR-A2 guard tests."""

from tools.audit_model_call_boundary import CallFingerprint, classify, scan_text


def test_legacy_app_anthropic_call_is_baselined():
    findings = scan_text("app.py", "import anthropic\nclient = anthropic.Anthropic()\nclient.messages.create()\n")
    groups = classify(findings)
    assert len(groups["legacy"]) == 3
    assert not groups["new"]


def test_approved_adapter_is_not_scanned():
    assert not scan_text("llm_fallback.py", "import anthropic\nanthropic.Anthropic().messages.create()\n")


def test_new_direct_openai_call_is_blocking():
    finding = CallFingerprint("core/new_feature.py", "call", "chat.completions.create")
    groups = classify([finding])
    assert groups["new"] == [finding]


def test_imports_constructors_and_endpoints_are_detected():
    findings = scan_text(
        "core/new_feature.py",
        """
import openai
from anthropic import Anthropic
client = openai.OpenAI()
client.chat.completions.create()
""",
    )
    assert [item.as_text() for item in findings] == [
        "core/new_feature.py|call|chat.completions.create",
        "core/new_feature.py|call|openai.OpenAI",
        "core/new_feature.py|import|anthropic",
        "core/new_feature.py|import|openai",
    ]


if __name__ == "__main__":
    test_legacy_app_anthropic_call_is_baselined()
    test_approved_adapter_is_not_scanned()
    test_new_direct_openai_call_is_blocking()
    test_imports_constructors_and_endpoints_are_detected()
    print("test_audit_model_call_boundary: 4/4 passed")
