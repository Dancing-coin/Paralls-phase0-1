"""将本轮结构化失败定位写入 CI 摘要，不复制原始请求、配置或完整日志。"""
from __future__ import annotations

import argparse
import builtins
import html
import json
import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def _exception_name(value: str) -> str:
    name = value.partition(':')[0].rstrip()
    kind = getattr(builtins, name, None)
    return name if isinstance(kind, type) and issubclass(kind, BaseException) else ''


def _source_location(source: str, line: str) -> str | None:
    repository = Path(__file__).resolve().parents[2]
    source = source.replace('\\', '/').removeprefix(repository.as_posix() + '/')
    if (re.fullmatch(r'(?:backend/(?:app|tests)|scripts/verification)/[\w/.-]+\.py', source)
            and '..' not in Path(source).parts and (repository / source).is_file()):
        return source + ':' + line
    return None


def _process_diagnostic(path: Path) -> dict:
    if not path.is_file():
        return {}
    result, traceback = {}, False
    with path.open(encoding='utf-8', errors='replace') as stream:
        for line in stream:
            if line.rstrip() == 'Traceback (most recent call last):':
                result, traceback = {}, True
            if not traceback:
                continue
            frame = re.fullmatch(r'  File "([^"\r\n]+)", line (\d+), in [^\r\n]+\s*', line)
            if frame and (location := _source_location(frame[1], frame[2])):
                result['source_location'] = location
            if name := _exception_name(line):
                result['error'] = name + ': details_omitted'
    return result


def _diagnostic_text(value: str) -> str:
    if value in {"Source inputs changed during verification", "Godot executable not found. Set GODOT_EXE or pass --godot-exe."}:
        return value
    match = re.fullmatch(r"(?:[A-Za-z_]\w*(?:Error|Exception): )?[A-Za-z_][A-Za-z0-9_.:-]*", value)
    if match:
        return value[:512]
    exception = re.match(r"([A-Za-z_]\w*(?:Error|Exception)):", value)
    return (exception[1] + ": " if exception else "") + "details_omitted"


def _fields(item: dict) -> dict:
    result = {}
    for key in ("id", "profile", "status", "exit_code", "failure_kind", "error", "message", "cleanup_status"):
        if key not in item:
            continue
        value = item[key]
        if value is None or type(value) in (str, int, bool):
            result[key] = (_diagnostic_text(value) if key in {"error", "message"} else value[:512]) if isinstance(value, str) else value
        else:
            result["diagnostic_error"] = "report_invalid_shape"
    for key in ("errors", "cleanup_errors", "source_dirty_paths"):
        if key in item:
            values = item[key]
            if isinstance(values, list) and all(isinstance(value, str) for value in values):
                result[key] = [value[:512] if key == 'source_dirty_paths' else _diagnostic_text(value)
                               for value in values[:20]]
            else:
                result["diagnostic_error"] = "report_invalid_shape"
    if item.get("failed_checks"):
        checks = item["failed_checks"]
        if isinstance(checks, list) and all(isinstance(check, dict) for check in checks):
            result["failed_checks"] = [{key: value[:128] for key in ("id", "status")
                if isinstance(value := check.get(key), str)} for check in checks]
        else:
            result["diagnostic_error"] = "report_invalid_shape"
    return result


def failure_summary(root: Path) -> list[dict]:
    if not root.is_dir():
        return [dict(error="evidence_root_missing")]
    rows = []
    for path in sorted(root.rglob("*.json")):
        if path.name not in {"manifest.json", "profile-result.json"} and not path.name.endswith("-report.json"):
            continue
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            rows.append(dict(file=path.relative_to(root).as_posix(), error="report_unreadable"))
            continue
        if not isinstance(report, dict):
            rows.append(dict(file=path.relative_to(root).as_posix(), error="report_invalid_shape"))
            continue
        groups = [report.get(key, []) for key in ("steps", "profiles", "results", "failed_checks")]
        if any(not isinstance(group, list) or any(not isinstance(item, dict) for item in group) for group in groups):
            rows.append(dict(file=path.relative_to(root).as_posix(), error="report_invalid_shape"))
            continue
        failures = [item for group in groups[:3] for item in group if item.get("status") not in ("passed", "proved", "running")]
        overall_failed = any(value is False for key, value in report.items() if key.startswith("overall_"))
        if (report.get("status") not in ("failed", "blocked", "running") and not overall_failed
                and report.get("cleanup_status") != "failed" and not failures
                and not report.get("error") and not report.get("errors")):
            continue
        row = dict(file=path.relative_to(root).as_posix(), **_fields(report),
            failures=[_fields(item) for item in failures])
        if path.name == 'profile-result.json' and report.get('status') == 'failed':
            # 报告生成前异常退出时，也只公开异常类型和实际仓库源码位置。
            if diagnostic := _process_diagnostic(path.with_name('command.log')):
                row['process_diagnostic'] = diagnostic
        rows.append(row)
    for path in sorted(root.rglob("focused.xml")):
        try:
            cases = ET.parse(path).findall(".//testcase")
        except (OSError, ET.ParseError):
            rows.append(dict(file=path.relative_to(root).as_posix(), error="junit_unreadable"))
            continue
        for case in cases:
            for tag in ("failure", "error", "skipped"):
                entry = case.find(tag)
                if entry is not None:
                    row = dict(file=path.relative_to(root).as_posix(),
                        test=case.get("classname", "") + "." + case.get("name", ""), status=tag)
                    if entry.get('message'):
                        # JUnit 正文不属于结构化错误码，只允许已知内置异常类型。
                        name = _exception_name(entry.get('message'))
                        row['error'] = (name + ': ' if name else '') + 'details_omitted'
                    # 仅抽取仓库 Python 位置，不公开断言局部值或请求正文。
                    for line in (entry.text or '').splitlines():
                        match = re.fullmatch(r'(.+\.py):(\d+):(?:\s+[A-Za-z_]\w*)?\s*', line)
                        if match and (location := _source_location(match[1], match[2])):
                            row['source_location'] = location
                    # 内嵌 python -c 失败仅保留行号，绝不输出函数名或子进程正文。
                    child_lines = re.findall(r'File "<string>", line (\d{1,6}), in ', entry.text or '')
                    if child_lines:
                        row['embedded_child_line'] = int(child_lines[-1])
                    rows.append(row)
    for path in sorted(root.rglob('focused.log')):
        progress = timeout = None
        with path.open(encoding='utf-8', errors='replace') as stream:
            for line in stream:
                match = re.fullmatch(r'[.FEfsxXrR]+\s+\[\s*(\d{1,3})%\]\s*', line)
                if match and int(match[1]) <= 100:
                    progress = int(match[1])
                match = re.fullmatch(r'\[harness\] timeout after (\d+(?:\.\d+)?) seconds\s*', line)
                if match:
                    timeout = float(match[1])
        if timeout is not None:
            rows.append(dict(file=path.relative_to(root).as_posix(), status='timeout',
                timeout_seconds=timeout, last_progress_percent=progress))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    rows = failure_summary(args.root)
    summary = json.dumps(rows, ensure_ascii=False, indent=2)
    # 运行摘要可能需登录；把同一份已过滤定位放入公开 annotation，原日志仍留在 artifact。
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        for row in rows[:20]:
            message = json.dumps(row, ensure_ascii=True)[:1500]
            message = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
            print('::warning title=Structured verification failure::' + message)
    # CI 摘要有大小上限；原始完整证据仍由既有 artifact 步骤上传。
    if len(summary) > 48000:
        summary = summary[:48000] + "\n[truncated; see uploaded evidence]"
    text = "### Structured verification failures\n\n<pre>" + html.escape(summary) + "</pre>\n"
    destination = os.environ.get("GITHUB_STEP_SUMMARY")
    if destination:
        with Path(destination).open("a", encoding="utf-8") as output:
            output.write(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
