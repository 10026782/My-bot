# test_structured_command.py — N18 Phase 2: shared structured-command parsing
# primitive (core/structured_command.py), extracted from Lead's
# parse_structured_command(). Verifies the primitive's own contract in
# isolation — Lead-specific field mapping/validation is covered separately
# by test_lead_service_phase1.py (section 11).

from core.structured_command import build_structured_trigger_re, parse_positional_command

passed = failed = 0


def chk(desc: str, cond: bool) -> None:
    global passed, failed
    if cond:
        passed += 1
        print(f"✅ {desc}")
    else:
        failed += 1
        print(f"❌ {desc}")


trig = build_structured_trigger_re(r"ליד\s+חדש")

chk("unrelated text -> None", parse_positional_command("שלום עולם", trig) is None)
chk("bare trigger -> prompt", parse_positional_command("ליד חדש", trig) == {"prompt": True})
chk("bare trigger with trailing whitespace -> prompt",
    parse_positional_command("ליד חדש   ", trig) == {"prompt": True})
chk("trigger + free text, no delimiter -> None (not this format)",
    parse_positional_command("ליד חדש משה כהן", trig) is None)
chk("delimiter with nothing after it -> prompt",
    parse_positional_command("ליד חדש |", trig) == {"prompt": True})

chk("pipe delimiter splits and strips parts",
    parse_positional_command("ליד חדש | משה | 0501234567 | recruitment", trig) ==
    {"parts": ["משה", "0501234567", "recruitment"]})

chk("slash delimiter, no spaces",
    parse_positional_command("ליד חדש/משה/0501234567/recruitment/הערה", trig) ==
    {"parts": ["משה", "0501234567", "recruitment", "הערה"]})

chk("delimiter is detected per-call, not hardcoded to the first configured one",
    parse_positional_command("ליד חדש | א | ב", trig)["parts"] ==
    parse_positional_command("ליד חדש/א/ב", trig)["parts"])

chk("a different delimiter inside a value is left alone once the outer one is chosen",
    parse_positional_command("ליד חדש | משה/כהן | 0501234567", trig) ==
    {"parts": ["משה/כהן", "0501234567"]})

# Custom trigger/delimiter set — proves this isn't Lead-specific mechanics.
task_trig = build_structured_trigger_re(r"משימה\s+חדשה", delimiters=";")
chk("a different entity's trigger + delimiter works independently",
    parse_positional_command("משימה חדשה; לקנות חלב; מחר", task_trig) ==
    {"parts": ["לקנות חלב", "מחר"]})
chk("a different entity's trigger doesn't match Lead's own text",
    parse_positional_command("ליד חדש | משה | 0501234567", task_trig) is None)

print()
print("=" * 50)
print(f"test_structured_command.py: {passed} passed, {failed} failed")
if failed:
    raise SystemExit(1)
