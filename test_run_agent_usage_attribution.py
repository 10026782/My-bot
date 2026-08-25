"""The live run_agent producer emits its proven Agent attribution."""

from pathlib import Path


source = Path("app.py").read_text()
recording = source[source.index('source     = "run_agent"'):source.index("            except Exception as e:", source.index('source     = "run_agent"'))]

assert 'capability_id  = "general.reasoning"' in recording
assert 'execution_class = "FULL_AGENT"' in recording
assert "operation_id" not in recording
assert "workflow_id" not in recording

print("run_agent attribution contract: OK")
