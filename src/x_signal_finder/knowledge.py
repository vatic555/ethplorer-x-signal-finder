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
from urllib.parse import unquote, urlsplit, urlunsplit


REVIEW_STATUSES = frozenset({"pending", "reviewed", "deprecated"})
VOCABULARY_REVIEW_STATUSES = frozenset({"candidate", "reviewed", "deprecated"})
VOCABULARY_MATCH_TYPES = frozenset({"token", "phrase", "entity"})
VOCABULARY_CATEGORIES = frozenset(
    {
        "product",
        "network",
        "capability",
        "user_problem",
        "user_intent",
        "analytics_concept",
        "project_entity",
        "infrastructure",
        "bizdev_integration",
        "contextual",
        "exclusion_context",
    }
)
VOCABULARY_ROLES = frozenset(
    {"positive_trigger", "context_only", "negative_context"}
)
VOCABULARY_STRENGTHS = frozenset({"strong", "normal", "weak"})
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
MARKDOWN_LINK_PATTERN = re.compile(r"(?<!!)\[[^]]*]\(([^)]+)\)")
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^]]*]\(([^)]+)\)")
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
VOCABULARY_COLUMNS = (
    "trigger_id",
    "term",
    "match_type",
    "category",
    "role",
    "strength",
    "products",
    "networks",
    "asset_ids",
    "static_source_ids",
    "static_basis",
    "first_party_authored_count",
    "referenced_context_count",
    "exact_article_link_basis",
    "review_status",
    "notes",
)
REQUIRED_PATHS = (
    "README.md",
    "assets_catalog.csv",
    "source_documents.md",
    "review_summary.md",
    "prefilter/README.md",
    "prefilter/vocabulary.csv",
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
    route_count: int
    vocabulary_count: int
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
            "route_count": self.route_count,
            "vocabulary_count": self.vocabulary_count,
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
) -> tuple[str | None, str | None, str | None, str | None]:
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
    source_file_sha256 = metadata.get("source_file_sha256")
    if source_file_sha256 is not None and (
        not isinstance(source_file_sha256, str)
        or not SHA256_PATTERN.fullmatch(source_file_sha256)
    ):
        errors.append(f"{label}: source_file_sha256 must be 64 lowercase hex characters")
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
    canonical_url = None
    if relative.parts[:2] == ("sources", "posts") and isinstance(source_url, str):
        canonical_url = normalize_article_url(source_url)
        if source_url.strip() and canonical_url is None:
            errors.append(
                f"{label}: source_url must identify an Ethplorer /posts/ article"
            )
    return source_id, status, body_signature, canonical_url


def _split_ids(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(";") if item.strip())


def normalize_article_url(value: str) -> str | None:
    """Normalize a public Ethplorer article URL without network access."""
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    hostname = (parsed.hostname or "").rstrip(".").casefold()
    if parsed.scheme.casefold() not in {"http", "https"}:
        return None
    if hostname not in {"ethplorer.io", "www.ethplorer.io"}:
        return None
    path = re.sub(r"/+", "/", unquote(parsed.path)).rstrip("/")
    if not re.fullmatch(r"/posts/[A-Za-z0-9_-]+", path):
        return None
    return urlunsplit(("https", "ethplorer.io", path, "", ""))


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


def _read_asset_ids(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return {
                (row.get("asset_id") or "").strip()
                for row in csv.DictReader(handle)
                if (row.get("asset_id") or "").strip()
            }
    except (OSError, UnicodeError, csv.Error):
        return set()


def _nonnegative_integer(value: str) -> bool:
    try:
        return int(value) >= 0
    except ValueError:
        return False


def _validate_vocabulary(
    path: Path,
    source_statuses: dict[str, str],
    asset_ids: set[str],
    canonical_routes: dict[str, str],
    errors: list[str],
) -> int:
    if not path.is_file():
        return 0
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != VOCABULARY_COLUMNS:
                errors.append(
                    "prefilter/vocabulary.csv: columns must exactly match the documented contract"
                )
                return 0
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as error:
        errors.append(
            "prefilter/vocabulary.csv: cannot read vocabulary "
            f"({type(error).__name__})"
        )
        return 0

    seen_ids: set[str] = set()
    seen_terms: dict[str, str] = {}
    routed_source_ids = set(canonical_routes.values())
    for row_number, row in enumerate(rows, start=2):
        label = f"prefilter/vocabulary.csv:{row_number}"
        for field in (
            "trigger_id",
            "term",
            "match_type",
            "category",
            "role",
            "strength",
            "static_basis",
            "first_party_authored_count",
            "referenced_context_count",
            "review_status",
            "notes",
        ):
            if not (row.get(field) or "").strip():
                errors.append(f"{label}: {field} is required")

        trigger_id = (row.get("trigger_id") or "").strip()
        if not ID_PATTERN.fullmatch(trigger_id):
            errors.append(f"{label}: trigger_id must be a stable lowercase identifier")
        elif trigger_id in seen_ids:
            errors.append(f"{label}: duplicate trigger_id {trigger_id}")
        else:
            seen_ids.add(trigger_id)

        term = (row.get("term") or "").strip()
        normalized_term = re.sub(r"\s+", " ", term).casefold()
        if normalized_term:
            duplicate_of = seen_terms.get(normalized_term)
            if duplicate_of is not None:
                errors.append(
                    f"{label}: normalized duplicate term matches {duplicate_of}"
                )
            else:
                seen_terms[normalized_term] = trigger_id or label

        match_type = (row.get("match_type") or "").strip()
        category = (row.get("category") or "").strip()
        role = (row.get("role") or "").strip()
        strength = (row.get("strength") or "").strip()
        status = (row.get("review_status") or "").strip()
        static_basis = (row.get("static_basis") or "").strip()
        if match_type not in VOCABULARY_MATCH_TYPES:
            errors.append(f"{label}: invalid match_type {match_type}")
        if category not in VOCABULARY_CATEGORIES:
            errors.append(f"{label}: invalid category {category}")
        if role not in VOCABULARY_ROLES:
            errors.append(f"{label}: invalid role {role}")
        if strength not in VOCABULARY_STRENGTHS:
            errors.append(f"{label}: invalid strength {strength}")
        if status not in VOCABULARY_REVIEW_STATUSES:
            errors.append(f"{label}: invalid review_status {status}")
        if static_basis not in {"yes", "no"}:
            errors.append(f"{label}: static_basis must be yes or no")

        for field in ("first_party_authored_count", "referenced_context_count"):
            if not _nonnegative_integer((row.get(field) or "").strip()):
                errors.append(f"{label}: {field} must be a non-negative integer")

        row_asset_ids = _split_ids(row.get("asset_ids") or "")
        for asset_id in sorted(set(row_asset_ids).difference(asset_ids)):
            errors.append(f"{label}: unknown asset_id {asset_id}")
        row_source_ids = _split_ids(row.get("static_source_ids") or "")
        for source_id in sorted(set(row_source_ids).difference(source_statuses)):
            errors.append(f"{label}: unknown static_source_id {source_id}")
        if static_basis == "yes" and not row_source_ids:
            errors.append(f"{label}: static_basis yes requires static_source_ids")
        exact_source_ids = _split_ids(row.get("exact_article_link_basis") or "")
        for source_id in sorted(set(exact_source_ids).difference(routed_source_ids)):
            errors.append(
                f"{label}: exact article source has no canonical route {source_id}"
            )
        if not set(exact_source_ids).issubset(row_source_ids):
            errors.append(
                f"{label}: exact_article_link_basis must be included in static_source_ids"
            )

        if status == "reviewed" and (
            static_basis != "yes"
            or not row_source_ids
            or not any(
                source_statuses.get(source_id) == "reviewed"
                for source_id in row_source_ids
            )
        ):
            errors.append(f"{label}: reviewed trigger requires reviewed static evidence")
        if (
            status == "reviewed"
            and category == "capability"
            and (not row_asset_ids or not row_source_ids)
        ):
            errors.append(
                f"{label}: reviewed capability trigger requires asset and static evidence"
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
        for match in MARKDOWN_IMAGE_PATTERN.finditer(text):
            target = _local_link_target(match.group(1))
            if target is None or not target.startswith("assets/"):
                continue
            destination = path.parent / target
            if not destination.is_file() or destination.stat().st_size == 0:
                label = path.relative_to(root).as_posix()
                errors.append(f"{label}: broken local image asset {target}")


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
    canonical_routes: dict[str, str] = {}
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
        source_id, status, body_signature, canonical_url = _validate_source(
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
        if canonical_url is not None:
            existing = canonical_routes.get(canonical_url)
            if existing is not None and existing != source_id:
                errors.append(
                    f"{label}: duplicate canonical article URL maps to {existing}"
                )
            else:
                canonical_routes[canonical_url] = source_id

    asset_path = knowledge_root / "assets_catalog.csv"
    asset_count = _validate_assets(
        asset_path,
        source_statuses,
        errors,
    )
    vocabulary_count = _validate_vocabulary(
        knowledge_root / "prefilter/vocabulary.csv",
        source_statuses,
        _read_asset_ids(asset_path),
        canonical_routes,
        errors,
    )
    if knowledge_root.is_dir():
        _validate_local_links(knowledge_root, errors)
    return KnowledgeValidationResult(
        knowledge_root=knowledge_root,
        source_count=len(source_paths),
        asset_count=asset_count,
        route_count=len(canonical_routes),
        vocabulary_count=vocabulary_count,
        errors=tuple(sorted(set(errors))),
    )
