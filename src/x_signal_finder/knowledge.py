"""Offline validation for the Git-backed MVP knowledge base."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import tomllib
from typing import Any
from urllib.parse import unquote


REVIEW_STATUSES = frozenset({"pending", "reviewed", "deprecated"})
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[[^]]*]\(([^)]+)\)")
URI_SCHEME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
ETHPLORER_ARTICLE_SOURCE_TYPE = "ethplorer_article"
SOURCE_REQUIRED_FIELDS = (
    "source_id",
    "title",
    "source_type",
    "products",
    "networks",
    "review_status",
    "confirms",
    "limitations",
)
ASSET_COLUMNS = (
    "asset_id",
    "name",
    "asset_type",
    "product",
    "networks",
    "topics",
    "what_it_can_answer",
    "what_it_cannot_prove",
    "unique_value",
    "source_ids",
    "review_status",
    "last_reviewed",
)
REQUIRED_PATHS = (
    "README.md",
    "assets_catalog.csv",
    "source_documents.md",
    "terminology/shared-analytics.md",
    "terminology/x-signal.md",
    "sources/_source-template.md",
    "sources/posts",
    "sources/ethplorer",
    "sources/binplorer",
    "sources/analytics",
    "sources/other",
)


@dataclass(frozen=True)
class KnowledgeValidationResult:
    """Content-safe result of one local knowledge validation."""

    knowledge_root: Path
    source_count: int
    asset_count: int
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": "valid" if self.valid else "invalid",
            "knowledge_root": str(self.knowledge_root),
            "source_count": self.source_count,
            "asset_count": self.asset_count,
            "error_count": len(self.errors),
            "errors": list(self.errors),
            "network_requests": 0,
            "llm_calls": 0,
        }

    def to_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=True)


def default_knowledge_root() -> Path:
    """Return the repository knowledge directory for an editable checkout."""
    return Path(__file__).resolve().parents[2] / "knowledge"


def _split_front_matter(path: Path, errors: list[str]) -> tuple[dict[str, Any], str]:
    relative = path.as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        errors.append(f"{relative}: cannot read UTF-8 Markdown ({type(error).__name__})")
        return {}, ""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "+++":
        errors.append(f"{relative}: TOML front matter must start with +++")
        return {}, text
    try:
        closing = next(
            index for index, line in enumerate(lines[1:], start=1) if line.strip() == "+++"
        )
    except StopIteration:
        errors.append(f"{relative}: TOML front matter has no closing +++")
        return {}, ""
    try:
        metadata = tomllib.loads("\n".join(lines[1:closing]))
    except tomllib.TOMLDecodeError as error:
        errors.append(f"{relative}: invalid TOML front matter ({error})")
        return {}, "\n".join(lines[closing + 1 :]).strip()
    return metadata, "\n".join(lines[closing + 1 :]).strip()


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and bool(item.strip()) for item in value
    )


def _is_iso_date(value: object) -> bool:
    if isinstance(value, date):
        return True
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _validate_source(
    path: Path,
    root: Path,
    errors: list[str],
) -> tuple[str | None, str | None, str | None]:
    label = path.relative_to(root).as_posix()
    metadata, body = _split_front_matter(path, errors)
    for field in SOURCE_REQUIRED_FIELDS:
        if field not in metadata:
            errors.append(f"{label}: missing required metadata field {field}")

    source_id = metadata.get("source_id")
    if not isinstance(source_id, str) or not ID_PATTERN.fullmatch(source_id):
        errors.append(f"{label}: source_id must be a stable lowercase identifier")
        source_id = None
    for field in ("title", "source_type"):
        value = metadata.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label}: {field} must be a non-empty string")
    for field in ("products", "networks", "confirms", "limitations"):
        value = metadata.get(field)
        if not isinstance(value, list) or not all(
            isinstance(item, str) for item in value
        ):
            errors.append(f"{label}: {field} must be an array of strings")
    confirms = metadata.get("confirms")

    status = metadata.get("review_status")
    if status not in REVIEW_STATUSES:
        errors.append(
            f"{label}: review_status must be pending, reviewed, or deprecated"
        )
        status = None
    if status == "reviewed" and not _is_string_list(confirms):
        errors.append(
            f"{label}: reviewed source must confirm at least one explicit claim"
        )

    source_url = metadata.get("source_url")
    approved_provenance = metadata.get("approved_provenance")
    if not any(
        isinstance(value, str) and value.strip()
        for value in (source_url, approved_provenance)
    ):
        errors.append(f"{label}: source_url or approved_provenance is required")
    if (
        isinstance(source_url, str)
        and source_url.strip()
        and not source_url.startswith(("https://", "http://"))
    ):
        errors.append(f"{label}: source_url must be an HTTP or HTTPS URL")
    for field in ("published_date", "retrieved_date"):
        value = metadata.get(field)
        if value is not None and not _is_iso_date(value):
            errors.append(f"{label}: {field} must use YYYY-MM-DD when present")
    if not body:
        errors.append(f"{label}: source content is empty")
    body_signature = None
    if body:
        normalized_body = re.sub(r"\s+", " ", body).strip().casefold()
        body_signature = hashlib.sha256(normalized_body.encode("utf-8")).hexdigest()

    relative = path.relative_to(root)
    if relative.parts[:2] == ("sources", "posts"):
        if metadata.get("source_type") != ETHPLORER_ARTICLE_SOURCE_TYPE:
            errors.append(
                f"{label}: sources/posts requires source_type ethplorer_article"
            )
        headings = [
            match.group(1).strip()
            for match in re.finditer(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
        ]
        if len(headings) != 1:
            errors.append(f"{label}: Ethplorer article must contain exactly one H1")
        elif isinstance(metadata.get("title"), str) and (
            headings[0] != metadata["title"].strip()
        ):
            errors.append(f"{label}: metadata title must match the existing H1")
        if len(body) < 500:
            errors.append(
                f"{label}: Ethplorer article appears empty or unexpectedly truncated"
            )
        if body.count("```") % 2:
            errors.append(f"{label}: unclosed fenced Markdown block")
    return source_id, status, body_signature


def _split_ids(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(";") if item.strip())


def _validate_assets(
    path: Path,
    source_statuses: dict[str, str],
    errors: list[str],
) -> int:
    if not path.is_file():
        return 0
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != ASSET_COLUMNS:
                errors.append(
                    "assets_catalog.csv: columns must exactly match the documented contract"
                )
                return 0
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        errors.append(
            f"assets_catalog.csv: cannot read catalog ({type(error).__name__})"
        )
        return 0

    seen_ids: set[str] = set()
    required_values = (
        "asset_id",
        "name",
        "asset_type",
        "product",
        "what_it_can_answer",
        "what_it_cannot_prove",
        "unique_value",
        "source_ids",
        "review_status",
        "last_reviewed",
    )
    for row_number, row in enumerate(rows, start=2):
        label = f"assets_catalog.csv:{row_number}"
        for field in required_values:
            if not (row.get(field) or "").strip():
                errors.append(f"{label}: {field} is required")
        asset_id = (row.get("asset_id") or "").strip()
        if not ID_PATTERN.fullmatch(asset_id):
            errors.append(f"{label}: asset_id must be a stable lowercase identifier")
        elif asset_id in seen_ids:
            errors.append(f"{label}: duplicate asset_id {asset_id}")
        else:
            seen_ids.add(asset_id)

        status = (row.get("review_status") or "").strip()
        if status not in REVIEW_STATUSES:
            errors.append(
                f"{label}: review_status must be pending, reviewed, or deprecated"
            )
        last_reviewed = (row.get("last_reviewed") or "").strip()
        if last_reviewed and not _is_iso_date(last_reviewed):
            errors.append(f"{label}: last_reviewed must use YYYY-MM-DD")

        source_ids = _split_ids(row.get("source_ids") or "")
        missing = sorted(set(source_ids).difference(source_statuses))
        for source_id in missing:
            errors.append(f"{label}: unknown source_id {source_id}")
        if status == "reviewed" and source_ids and not any(
            source_statuses.get(source_id) == "reviewed" for source_id in source_ids
        ):
            errors.append(
                f"{label}: reviewed capability requires at least one reviewed source"
            )
    return len(rows)


def _local_link_target(raw_target: str) -> str | None:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]
    if (
        not target
        or target.startswith(("#", "/"))
        or URI_SCHEME_PATTERN.match(target)
    ):
        return None
    return unquote(target.split("#", 1)[0])


def _validate_local_links(root: Path, errors: list[str]) -> None:
    for path in sorted(root.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for match in MARKDOWN_LINK_PATTERN.finditer(text):
            target = _local_link_target(match.group(1))
            if target is None:
                continue
            destination = path.parent / target
            if not destination.exists():
                label = path.relative_to(root).as_posix()
                errors.append(f"{label}: broken local reference {target}")


def validate_knowledge(root: Path | None = None) -> KnowledgeValidationResult:
    """Validate knowledge files without network, database, or model access."""
    knowledge_root = (root or default_knowledge_root()).resolve()
    errors: list[str] = []
    for relative in REQUIRED_PATHS:
        if not (knowledge_root / relative).exists():
            errors.append(f"missing required knowledge path: {relative}")

    source_statuses: dict[str, str] = {}
    seen_source_ids: set[str] = set()
    body_signatures: dict[str, str] = {}
    sources_root = knowledge_root / "sources"
    source_paths = (
        sorted(
            path
            for path in sources_root.rglob("*.md")
            if not path.name.startswith("_") and path.name.lower() != "readme.md"
        )
        if sources_root.is_dir()
        else []
    )
    for path in source_paths:
        source_id, status, body_signature = _validate_source(
            path, knowledge_root, errors
        )
        label = path.relative_to(knowledge_root).as_posix()
        if body_signature is not None:
            duplicate_of = body_signatures.get(body_signature)
            if duplicate_of is not None:
                errors.append(f"{label}: duplicate source body matches {duplicate_of}")
            else:
                body_signatures[body_signature] = label
        if source_id is None:
            continue
        if source_id in seen_source_ids:
            errors.append(f"{label}: duplicate source_id {source_id}")
            continue
        seen_source_ids.add(source_id)
        if status is not None:
            source_statuses[source_id] = status

    asset_count = _validate_assets(
        knowledge_root / "assets_catalog.csv",
        source_statuses,
        errors,
    )
    if knowledge_root.is_dir():
        _validate_local_links(knowledge_root, errors)
    return KnowledgeValidationResult(
        knowledge_root=knowledge_root,
        source_count=len(source_paths),
        asset_count=asset_count,
        errors=tuple(sorted(set(errors))),
    )
