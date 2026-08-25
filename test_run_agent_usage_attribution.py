"""The live run_agent producer emits its proven Agent attribution."""

import ast
from pathlib import Path


tree = ast.parse(Path("app.py").read_text())
recording_calls = [
    node
    for node in ast.walk(tree)
    if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Name)
    and node.func.id == "record_llm_usage"
]

assert len(recording_calls) == 1
recording = recording_calls[0]
assert any(
    keyword.arg is None
    and isinstance(keyword.value, ast.Call)
    and isinstance(keyword.value.func, ast.Name)
    and keyword.value.func.id == "usage_attribution_from_context"
    and len(keyword.value.args) == 1
    and isinstance(keyword.value.args[0], ast.Name)
    and keyword.value.args[0].id == "execution_context"
    for keyword in recording.keywords
)

print("run_agent attribution contract: OK")
