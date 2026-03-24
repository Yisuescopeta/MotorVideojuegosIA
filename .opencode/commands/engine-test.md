---
description: Run the engine unittest flow
agent: build
---

Run the custom tool `engine_unittest`.

What this validates:
- Python unittest discover over `tests/`
- baseline non-visual regression coverage for the motor

Where artifacts are written:
- no new artifact bundle is required by default
- any repo-local outputs must stay under `artifacts/` or `.motor/`

Requirements:
- do not use raw bash when the custom tool is available
- summarize pass/fail, exit code, and the most relevant stdout/stderr
- if the tool fails, identify the first actionable failure
