# T000 — <short title>

<!-- Copy to docs/tasks/T<NNN>-<slug>.md. All fields below are required by tools/agent/check_docs.py. -->

- **Status:** draft <!-- draft | ready | measuring | accepted | rejected | abandoned -->
- **Module:** <one module from docs/architecture/subsystem-map.md>
- **Hypothesis:** <one falsifiable statement: "changing X in file Y reduces metric Z because W">
- **Primary metric:** <metric and predicted direction, e.g. guest FPS ↑, render busy ms/frame ↓>
- **Scenario:** <scenario ID / save / route / config ID>
- **Control Run ID:** <existing run in docs/performance/runs/, or "none (first baseline)">
- **Candidate Run ID:** <unique new Run ID, or "pending">
- **Scope:** <exact files allowed to change; sdk/ and vendored Renut in a separate commit>
- **Regression checks:** <functional and metric guardrails>
- **Acceptance rule:** <threshold relative to control and noise floor>

## Evidence

<Facts with Run IDs / files that motivated the task.>

## Result

<Filled when closing: candidate vs control table, verdict, link to the run report, STATE.md update.>
