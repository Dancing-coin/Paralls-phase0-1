"""Negative probes for the opt-in simulation design documentation checker."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "check_simulation_foundation_docs.py"
SPEC = importlib.util.spec_from_file_location("simulation_docs", SCRIPT)
assert SPEC and SPEC.loader
CHECKER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER)


class SimulationDocsTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="simulation-docs-probe-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name) / "完整版"
        # Linked companion documents remain at their original relative depth.
        self.source = CHECKER.DEFAULT_ROOT
        shutil.copytree(self.source, self.root)

    def path(self, number):
        return next(self.root.glob(f"{number:02}-*.md"))

    def errors(self):
        # External relative links are resolved against the original tree for
        # these isolated mutations; all local links use the mutated copy.
        return CHECKER.check_docs(self.root, external_base=self.source)

    def change(self, path, old, new):
        content = path.read_text(encoding="utf-8")
        self.assertIn(old, content)
        path.write_text(content.replace(old, new, 1), encoding="utf-8")

    def assert_problem(self, category):
        self.assertTrue(any(f"[{category}]" in e for e in self.errors()), self.errors())

    def test_repository_documents_pass(self):
        self.assertEqual([], self.errors())

    def test_missing_index_row_is_rejected(self):
        path = self.root / "README.md"
        rows = path.read_text(encoding="utf-8").splitlines(keepends=True)
        path.write_text("".join(r for r in rows if not r.startswith("| 24 |")), encoding="utf-8")
        self.assert_problem("index")

    def test_duplicate_number_is_rejected(self):
        shutil.copyfile(self.path(3), self.root / "03-duplicate.md")
        self.assert_problem("number")

    def test_broken_local_anchor_and_file_are_rejected(self):
        with self.path(3).open("a", encoding="utf-8") as stream:
            stream.write("\n[bad](04-实体关系图谱与动态边.md#absent-anchor)\n[bad](absent.md)\n")
        self.assert_problem("anchor")
        self.assert_problem("link")

    def test_missing_sequence_type_is_rejected(self):
        self.change(self.path(10), "sequenceDiagram", "flowchart LR")
        self.assert_problem("diagram")

    def test_companion_cannot_point_to_itself(self):
        self.change(self.path(25), "三图配套：[00](00-总纲与设计地图.md)",
                    "三图配套：[25](25-内存模拟方案在线图谱导航.md)")
        self.assert_problem("diagram")

    def test_missing_status_axis_is_rejected(self):
        self.change(self.path(3), "验证证据：", "证据字段已删除：")
        self.assert_problem("status")

    def test_second_record_definition_is_rejected(self):
        with self.path(10).open("a", encoding="utf-8") as stream:
            stream.write("\n```yaml\nRecord:\n  revision: Integer\n```\n")
        self.assert_problem("schema")

    def test_projection_field_in_canonical_record_is_rejected(self):
        self.change(self.path(3), "Record:\n", "Record:\n  projection_version: Integer\n")
        self.assert_problem("schema")

    def test_unclosed_fence_is_rejected(self):
        with self.path(3).open("a", encoding="utf-8") as stream:
            stream.write("\n```text\nunterminated\n")
        self.assert_problem("fence")


if __name__ == "__main__":
    unittest.main()
