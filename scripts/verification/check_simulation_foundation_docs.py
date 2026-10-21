"""Opt-in static checks for the simulation fork's 00–26 design documents.

Only the explicit conventions described in that folder's README are checked.
This does not render Mermaid, fetch websites, or verify simulation behavior.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import unicodedata
from urllib.parse import unquote, urlsplit


DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "docs/fork项目/模拟预测底座/完整版"
NUMBERED = re.compile(r"^(\d{2})-.+\.md$")
LINK = re.compile(r"!?\[[^\]\n]*\]\((<[^>\n]+>|[^)\n]+)\)")
DEFINITION = re.compile(
    r"^(Record|RecordRef|PayloadRef|RelationInstance|Proposal|OwnerReceipt|"
    r"WorldRecordView|RelationProjection|QueryManifest|RecordEnvelope)\s*(?::|=\s*\{)",
    re.MULTILINE,
)
OWNERS = {
    "Record": "03", "RecordRef": "03", "PayloadRef": "03",
    "RelationInstance": "04", "Proposal": "05", "OwnerReceipt": "05",
    "WorldRecordView": "26", "RelationProjection": "26", "QueryManifest": "26",
}


def slug(text: str) -> str:
    text = text.strip().lower()
    text = "".join(c for c in text if c in " _-" or unicodedata.category(c)[0] in "LNM")
    return text.replace(" ", "-")


def parse_markdown(content: str):
    """Collect headings, plain text, and fenced blocks without rendering Markdown."""
    headings, blocks, plain = [], [], []
    fence, language, start, buffer = None, "", 0, []
    for line_number, line in enumerate(content.splitlines(), 1):
        if fence:
            if re.fullmatch(rf" {{0,3}}{re.escape(fence[0])}{{{len(fence)},}}\s*", line):
                blocks.append((language, "\n".join(buffer), start))
                fence, buffer = None, []
            else:
                buffer.append(line)
            continue
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if match:
            fence, language, start = match[1], match[2].strip(), line_number
            continue
        plain.append(line)
        heading = re.match(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            headings.append((line_number, heading[1]))
    return headings, blocks, "\n".join(plain), start if fence else None


def anchors(content: str) -> set[str]:
    result, counts = set(), {}
    for _, title in parse_markdown(content)[0]:
        base = slug(title)
        count = counts.get(base, 0)
        result.add(f"{base}-{count}" if count else base)
        counts[base] = count + 1
    result.update(re.findall(r'<a\s+(?:id|name)=[\"\']([^\"\']+)', content))
    return result


def has_three_diagrams(content: str) -> bool:
    headings, blocks, _, _ = parse_markdown(content)
    found = set()
    for language, body, line in blocks:
        if language != "mermaid":
            continue
        preceding = [title for position, title in headings if position < line]
        title = preceding[-1] if preceding else ""
        kind = body.strip().splitlines()[0] if body.strip() else ""
        if "架构" in title and re.match(r"(?:flowchart|graph)\s", kind):
            found.add("architecture")
        if "时序" in title and kind == "sequenceDiagram":
            found.add("sequence")
        if "数据流" in title and re.match(r"(?:flowchart|graph)\s", kind):
            found.add("dataflow")
    return len(found) == 3


def check_docs(root: Path, *, external_base: Path | None = None) -> list[str]:
    root = root.resolve()
    errors = []

    def error(path, category, detail):
        errors.append(f"{path.name}: [{category}] {detail}")

    if not root.is_dir():
        return [f"{root}: [number] documentation directory does not exist"]
    paths = sorted(root.glob("*.md"))
    contents = {p: p.read_text(encoding="utf-8-sig") for p in paths}
    by_number = {}
    for path in paths:
        match = NUMBERED.fullmatch(path.name)
        if match:
            by_number.setdefault(match[1], []).append(path)
    expected = {f"{i:02}" for i in range(27)}
    for number in sorted(expected | by_number.keys()):
        if number not in expected or len(by_number.get(number, [])) != 1:
            error(root, "number", f"number {number}: expected exactly one file")

    readme = root / "README.md"
    rows = re.findall(r"^\| (\d{2}) \| \[[^\]]+\]\(([^)]+)\)",
                      contents.get(readme, ""), re.MULTILINE)
    indexed = {}
    for number, target in rows:
        indexed.setdefault(number, []).append(target)
    for number in sorted(expected | indexed.keys()):
        matches = by_number.get(number, [])
        targets = indexed.get(number, [])
        if len(targets) != 1 or len(matches) != 1 or targets[0] != matches[0].name:
            error(readme, "index", f"number {number}: missing, duplicate, or incorrect row")

    definitions = {name: [] for name in OWNERS}
    for path, content in contents.items():
        headings, blocks, plain, unclosed = parse_markdown(content)
        if unclosed:
            error(path, "fence", f"unclosed code fence at line {unclosed}")
        for _, body, _ in blocks:
            for declaration in DEFINITION.finditer(body):
                name = declaration[1]
                if name == "RecordEnvelope":
                    error(path, "schema", "RecordEnvelope creates a second canonical envelope")
                    continue
                definitions[name].append(path)
                if path.name[:2] != OWNERS[name]:
                    error(path, "schema", f"{name} must be defined in {OWNERS[name]}")
                remainder = body[declaration.end():]
                payload = re.split(r"^\S", remainder, maxsplit=1, flags=re.MULTILINE)[0]
                fields = set(re.findall(r"^\s{2}([a-z_]+):", payload, re.MULTILINE))
                forbidden = set()
                if name == "Record":
                    forbidden = {"admission", "projection_version", "projection_cursor",
                                 "source_revision_vector", "graph_projection_revision"}
                elif name == "WorldRecordView":
                    forbidden = {"admission", "revision", "epistemic_status"}
                elif name == "RelationInstance":
                    forbidden = {"revision", "access_scope", "epistemic_status", "admission"}
                if fields & forbidden:
                    error(path, "schema", f"{name}: forbidden fields {sorted(fields & forbidden)}")

        for match in LINK.finditer(plain):
            target = match[1].strip("<>")
            if urlsplit(target).scheme or target.startswith("//"):
                continue
            file_part, _, fragment = target.partition("#")
            destination = (path.parent / unquote(file_part)).resolve() if file_part else path
            if external_base and not destination.is_relative_to(root):
                destination = (external_base / unquote(file_part)).resolve()
            if not destination.is_file():
                error(path, "link", f"missing local file: {target}")
            elif fragment and destination.suffix.lower() == ".md":
                text = contents.get(destination)
                if text is None:
                    text = destination.read_text(encoding="utf-8-sig")
                if unquote(fragment) not in anchors(text):
                    error(path, "anchor", f"missing heading: {target}")

        if path.name == "AGENTS.md":
            continue
        for axis in ("修订日期：", "合同版本：", "建设状态：", "验证证据："):
            if axis not in plain:
                error(path, "status", f"missing {axis}")
        if "non-authorizing" not in plain:
            error(path, "status", "missing non-authorizing declaration")
        for status in ("现有可复用", "计划建设", "后置能力"):
            if status not in content:
                error(path, "status", f"missing scope label {status}")
        if not has_three_diagrams(content):
            companion = re.search(r"三图配套：\[[^\]]+\]\(([^)#]+\.md)\)", plain)
            peer = (root / companion[1]).resolve() if companion else None
            if peer == path or peer not in contents or not has_three_diagrams(contents[peer]):
                error(path, "diagram", "need architecture, sequence and dataflow blocks or explicit companion")

    for name, owners in definitions.items():
        # RecordRef is currently an inline definition in 03, not a fenced schema.
        if name == "RecordRef":
            master = by_number.get("03", [])
            if not master or "RecordRef = {record_id, revision}" not in contents[master[0]]:
                error(root, "schema", "missing canonical inline RecordRef definition in 03")
            if len(owners) > 1:
                error(root, "schema", "duplicate explicit RecordRef definitions")
        elif len(owners) != 1:
            error(root, "schema", f"{name}: expected exactly one explicit definition")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                        help="documentation directory (default: simulation fork 完整版)")
    args = parser.parse_args()
    errors = check_docs(args.root)
    if errors:
        print("\n".join(errors))
        print(f"FAIL: {len(errors)} static documentation issue(s).")
        return 1
    print("PASS: 00–26 numbering/index, local links/anchors, fences, diagram structure, "
          "status axes and explicit schema ownership.")
    print("Not verified: Mermaid rendering, external sources, runtime, adapters, "
          "performance, security implementation or prediction validity.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
