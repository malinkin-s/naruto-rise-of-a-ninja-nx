"""Unit tests for check_docs.py enforcing documentation and task constraints."""

from pathlib import Path
import tempfile
import unittest

from check_docs import (
    check_state_md,
    check_markdown_links,
    check_tasks,
    run_checks,
)


class CheckDocsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "docs/performance/runs").mkdir(parents=True)
        (self.root / "docs/archive/runs").mkdir(parents=True)
        (self.root / "docs/tasks").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_state_budget_exceeded(self):
        state_file = self.root / "STATE.md"
        lines = ["# Title", "Updated: 2026-11-09"] + [f"- Line {i}" for i in range(160)]
        state_file.write_text("\n".join(lines), encoding="utf-8")
        violations = check_state_md(self.root, state_file)
        self.assertTrue(any("budget exceeded" in v for v in violations))

    def test_state_fact_without_citation_fails(self):
        state_file = self.root / "STATE.md"
        content = """# State
Updated: 2026-11-09
- **Fact:** Some unsupported claim without any run or commit or file.
"""
        state_file.write_text(content, encoding="utf-8")
        violations = check_state_md(self.root, state_file)
        self.assertTrue(any("Fact line does not cite" in v for v in violations))

    def test_state_fact_with_valid_run_id_passes(self):
        (self.root / "docs/performance/runs/run-test-01.md").write_text("# Run", encoding="utf-8")
        state_file = self.root / "STATE.md"
        content = """# State
Updated: 2026-11-09
- **Fact:** measured 30 fps in `run-test-01`.
"""
        state_file.write_text(content, encoding="utf-8")
        violations = check_state_md(self.root, state_file)
        self.assertEqual(violations, [])

    def test_broken_relative_link_detected(self):
        doc = self.root / "docs/sample.md"
        doc.write_text("See [missing file](non_existent.md).", encoding="utf-8")
        violations = check_markdown_links(self.root)
        self.assertTrue(any("broken link -> non_existent.md" in v for v in violations))

    def test_task_missing_fields_fails(self):
        task_file = self.root / "docs/tasks/T099-test.md"
        task_file.write_text("- **Status:** draft\n- **Module:** cpu\n", encoding="utf-8")
        violations = check_tasks(self.root)
        self.assertTrue(any("missing required fields" in v for v in violations))

    def test_multiple_measuring_tasks_fails(self):
        fields = [
            "- **Status:** measuring",
            "- **Module:** cpu",
            "- **Hypothesis:** h",
            "- **Primary metric:** fps",
            "- **Scenario:** sc",
            "- **Control Run ID:** c",
            "- **Candidate Run ID:** cand",
            "- **Scope:** s",
            "- **Regression checks:** r",
            "- **Acceptance rule:** a",
        ]
        body = "\n".join(fields)
        (self.root / "docs/tasks/T001.md").write_text(body, encoding="utf-8")
        (self.root / "docs/tasks/T002.md").write_text(body, encoding="utf-8")
        violations = check_tasks(self.root)
        self.assertTrue(any("Multiple tasks currently in 'measuring' status" in v for v in violations))


if __name__ == "__main__":
    unittest.main()
