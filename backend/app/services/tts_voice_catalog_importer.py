"""Controlled XLSX catalog import and advisory ranking for TTS presentation assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re
from typing import Iterable
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from pydantic import BaseModel, ConfigDict, Field

from app.services.tts_voice_profiles import TTSVoiceCatalog, VoiceCatalogEntry


_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_DOCUMENT_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_TAG_SPLIT = re.compile(r"[;,|/]+")
_HEADER_NORMALIZE = re.compile(r"[^a-z0-9]+")


class TTSVoiceCatalogImportError(ValueError):
    """Raised when an operator-provided voice catalog cannot be normalized safely."""


@dataclass(frozen=True)
class XlsxVoiceCatalogColumns:
    """Normalized header names expected from a controlled provider export."""

    voice_id: str = "voice_id"
    language_tags: str = "language_tags"
    trait_tags: str = "trait_tags"
    usage_tags: str = "usage_tags"
    age_impression: str = "age_impression"
    voice_gender_presentation: str = "voice_gender_presentation"
    review_ref: str = "review_ref"


class VoiceCatalogCandidateRequest(BaseModel):
    """Approved presentation criteria used only to shortlist catalog entries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    required_language_tags: tuple[str, ...] = ()
    preferred_trait_tags: tuple[str, ...] = ()
    preferred_usage_tags: tuple[str, ...] = ()
    age_impression: str | None = None
    voice_gender_presentation: str | None = None


@dataclass(frozen=True)
class VoiceCatalogCandidate:
    """A deterministic advisory result; it is not an approved runtime binding."""

    entry: VoiceCatalogEntry
    score: int
    matched_trait_tags: tuple[str, ...]
    matched_usage_tags: tuple[str, ...]
    age_impression_matched: bool
    voice_gender_presentation_matched: bool

    @property
    def voice_id(self) -> str:
        return self.entry.voice_id


def import_xlsx_voice_catalog(
    source_path: str | Path,
    *,
    provider: str,
    model: str,
    catalog_revision: str,
    columns: XlsxVoiceCatalogColumns = XlsxVoiceCatalogColumns(),
) -> TTSVoiceCatalog:
    """Normalize the first worksheet of a controlled XLSX export into v1 JSON data.

    Provider, model, and revision are explicit operator inputs so a spreadsheet
    cannot silently define cross-provider compatibility. The importer handles
    only standard XLSX cell values and does not follow URLs or preview fields.
    """

    if not provider or not model or not catalog_revision:
        raise TTSVoiceCatalogImportError("provider, model, and catalog_revision are required")
    path = Path(source_path)
    if path.suffix.casefold() != ".xlsx":
        raise TTSVoiceCatalogImportError("voice catalog import requires an .xlsx file")

    rows = _read_first_worksheet(path)
    if not rows:
        raise TTSVoiceCatalogImportError("voice catalog XLSX has no rows")
    headers = {_normalize_header(value): index for index, value in enumerate(rows[0]) if value.strip()}
    expected = {field: _normalize_header(getattr(columns, field)) for field in columns.__dataclass_fields__}
    voice_column = headers.get(expected["voice_id"])
    if voice_column is None:
        raise TTSVoiceCatalogImportError("voice catalog XLSX is missing the voice_id column")

    entries: list[VoiceCatalogEntry] = []
    seen_voice_ids: set[str] = set()
    for row_number, row in enumerate(rows[1:], start=2):
        voice_id = _value_at(row, voice_column).strip()
        if not voice_id:
            if any(value.strip() for value in row):
                raise TTSVoiceCatalogImportError(f"voice catalog row {row_number} is missing voice_id")
            continue
        if voice_id in seen_voice_ids:
            raise TTSVoiceCatalogImportError(f"voice catalog contains duplicate voice_id: {voice_id}")
        seen_voice_ids.add(voice_id)
        entries.append(
            VoiceCatalogEntry(
                voice_id=voice_id,
                language_tags=_split_tags(_value_at(row, headers.get(expected["language_tags"]))),
                trait_tags=_split_tags(_value_at(row, headers.get(expected["trait_tags"]))),
                usage_tags=_split_tags(_value_at(row, headers.get(expected["usage_tags"]))),
                age_impression=_optional_value(_value_at(row, headers.get(expected["age_impression"]))),
                voice_gender_presentation=_optional_value(
                    _value_at(row, headers.get(expected["voice_gender_presentation"]))
                ),
                review_ref=_optional_value(_value_at(row, headers.get(expected["review_ref"]))),
            )
        )
    if not entries:
        raise TTSVoiceCatalogImportError("voice catalog XLSX has no voice entries")
    return TTSVoiceCatalog(
        contract="tts_voice_catalog.v1",
        provider=provider,
        model=model,
        catalog_revision=catalog_revision,
        voices=entries,
    )


def rank_voice_catalog_candidates(
    catalog: TTSVoiceCatalog,
    request: VoiceCatalogCandidateRequest,
) -> list[VoiceCatalogCandidate]:
    """Return presentation-only short-list candidates in deterministic order."""

    required_languages = _normalized_set(request.required_language_tags)
    preferred_traits = _normalized_set(request.preferred_trait_tags)
    preferred_usage = _normalized_set(request.preferred_usage_tags)
    expected_age = _normalized_optional(request.age_impression)
    expected_gender = _normalized_optional(request.voice_gender_presentation)

    candidates: list[VoiceCatalogCandidate] = []
    for entry in catalog.voices:
        languages = _normalized_set(entry.language_tags)
        if not required_languages.issubset(languages):
            continue
        matched_traits = tuple(sorted(preferred_traits.intersection(_normalized_set(entry.trait_tags))))
        matched_usage = tuple(sorted(preferred_usage.intersection(_normalized_set(entry.usage_tags))))
        age_matched = expected_age is not None and _normalized_optional(entry.age_impression) == expected_age
        gender_matched = expected_gender is not None and _normalized_optional(entry.voice_gender_presentation) == expected_gender
        score = len(matched_traits) * 5 + len(matched_usage) * 3 + int(age_matched) * 2 + int(gender_matched) * 2
        candidates.append(
            VoiceCatalogCandidate(
                entry=entry,
                score=score,
                matched_trait_tags=matched_traits,
                matched_usage_tags=matched_usage,
                age_impression_matched=age_matched,
                voice_gender_presentation_matched=gender_matched,
            )
        )
    return sorted(candidates, key=lambda candidate: (-candidate.score, candidate.voice_id))


def _read_first_worksheet(path: Path) -> list[list[str]]:
    try:
        with ZipFile(path) as archive:
            shared_strings = _read_shared_strings(archive)
            worksheet_path = _first_worksheet_path(archive)
            root = ElementTree.fromstring(archive.read(worksheet_path))
    except (OSError, BadZipFile, KeyError, ElementTree.ParseError) as exc:
        raise TTSVoiceCatalogImportError("voice catalog XLSX is unreadable or invalid") from exc

    rows: list[list[str]] = []
    for row in root.findall(f".//{{{_MAIN_NS}}}sheetData/{{{_MAIN_NS}}}row"):
        values: dict[int, str] = {}
        for cell in row.findall(f"{{{_MAIN_NS}}}c"):
            reference = cell.get("r")
            if not reference:
                continue
            column_index = _column_index(reference)
            values[column_index] = _cell_value(cell, shared_strings)
        if values:
            rows.append([values.get(index, "") for index in range(max(values) + 1)])
    return rows


def _read_shared_strings(archive: ZipFile) -> list[str]:
    try:
        root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(node.itertext()) for node in root.findall(f"{{{_MAIN_NS}}}si")]


def _first_worksheet_path(archive: ZipFile) -> str:
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    first_sheet = workbook.find(f".//{{{_MAIN_NS}}}sheets/{{{_MAIN_NS}}}sheet")
    if first_sheet is None:
        raise TTSVoiceCatalogImportError("voice catalog XLSX has no worksheets")
    relation_id = first_sheet.get(f"{{{_DOCUMENT_REL_NS}}}id")
    relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for relation in relationships.findall(f"{{{_PACKAGE_REL_NS}}}Relationship"):
        if relation.get("Id") == relation_id:
            target = relation.get("Target")
            if target:
                return str(PurePosixPath("xl") / target.lstrip("/"))
    raise TTSVoiceCatalogImportError("voice catalog XLSX first worksheet relationship is invalid")


def _cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        inline = cell.find(f"{{{_MAIN_NS}}}is")
        return "" if inline is None else "".join(inline.itertext())
    value = cell.findtext(f"{{{_MAIN_NS}}}v", default="")
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (IndexError, ValueError) as exc:
            raise TTSVoiceCatalogImportError("voice catalog XLSX has an invalid shared-string reference") from exc
    return value


def _column_index(reference: str) -> int:
    match = re.match(r"([A-Z]+)", reference.upper())
    if match is None:
        raise TTSVoiceCatalogImportError("voice catalog XLSX has an invalid cell reference")
    index = 0
    for character in match.group(1):
        index = index * 26 + ord(character) - ord("A") + 1
    return index - 1


def _value_at(row: list[str], index: int | None) -> str:
    return "" if index is None or index >= len(row) else row[index]


def _split_tags(value: str) -> list[str]:
    return list(dict.fromkeys(tag.strip() for tag in _TAG_SPLIT.split(value) if tag.strip()))


def _optional_value(value: str) -> str | None:
    stripped = value.strip()
    return stripped or None


def _normalize_header(value: str) -> str:
    return _HEADER_NORMALIZE.sub("_", value.casefold()).strip("_")


def _normalized_set(values: Iterable[str]) -> set[str]:
    return {value.strip().casefold() for value in values if value.strip()}


def _normalized_optional(value: str | None) -> str | None:
    return value.strip().casefold() if value and value.strip() else None


__all__ = [
    "TTSVoiceCatalogImportError",
    "VoiceCatalogCandidate",
    "VoiceCatalogCandidateRequest",
    "XlsxVoiceCatalogColumns",
    "import_xlsx_voice_catalog",
    "rank_voice_catalog_candidates",
]
