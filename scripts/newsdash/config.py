"""Config loading, validation, preset resolution, and environment overlay.

All config is JSON so the browser, the pipeline, issue-ops, and agents read
and write the same files. Validation is two-layered: JSON Schema for shape,
then semantic checks for cross-field rules a schema cannot express (e.g. an
effective source, after preset overrides, must still have a type and section).

Security invariants enforced here:
- private sources may not carry a ``url`` (capability URLs live in Secrets);
- ``enabled: "auto"`` resolves to on only when every env var named in
  ``secret_ref`` is present and non-empty (key-present => on);
- for a private feed source, ``secret_ref[0]`` names the ONE GitHub Secret
  (convention: ``SRC_<ID>_URL``) whose value is the capability URL; it is
  read from the environment at load time into ``src.url`` in process memory
  only and is never written, logged, or echoed in any message;
- ``<ID>_ENABLED=0`` in the environment is a kill switch for any source.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import jsonschema
from jsonschema.exceptions import best_match
from referencing import Registry, Resource


class ConfigError(Exception):
    """Invalid configuration; message is safe to print in CI logs."""


URL_TYPES = {"rss", "opml", "feed-json", "static-page"}
QUERY_TYPES = {"arxiv", "openalex", "semanticscholar"}
SOURCE_TYPES = URL_TYPES | QUERY_TYPES | {"crossref"}
# Private feed types whose capability URL is supplied via secret_ref[0]
# (a GitHub Secret named SRC_<ID>_URL) rather than a config-carried url.
PRIVATE_URL_TYPES = {"rss", "feed-json", "static-page"}

# Env keys carrying per-source capability URLs, overlaid from the
# NEWSDASH_SOURCE_SECRETS blob (all secrets JSON) at load time.
_SRC_SECRET_KEY = re.compile(r"^SRC_[A-Z0-9_]+$")

# Category a source falls into when the config does not say.
DEFAULT_CATEGORY_BY_TYPE = {
    "arxiv": "optional",
    "openalex": "optional",
    "crossref": "optional",
    "semanticscholar": "optional",
}

# Sections the frontend knows how to render, and what lives in them.
# "following" is the scholars/labs tracking section: papers-kind so followed
# authors' works carry authors/venue, but it accepts any feed source too.
SECTION_KINDS = {
    "news": "news",
    "papers": "papers",
    "following": "papers",
    "private": "news",
}


@dataclass
class Windows:
    news_hours: int = 24
    papers_days: int = 7
    archive_days: int = 14


@dataclass
class Ranking:
    # Homepage variety knobs: whether to show the mixed "Highlights" block,
    # and how many items any single source may contribute to it.
    highlights: bool = True
    max_per_source: int = 2


@dataclass
class Threads:
    # "Threads · 线索": the optional LLM keyword-aggregation block. Bounds on
    # max_threads (2..6) are enforced by config/schema/site.schema.json.
    # include_private is an explicit consent gate: private-section titles and
    # summaries are only sent to the configured LLM endpoint when it is true.
    enabled: bool = True
    max_threads: int = 6
    include_private: bool = False


@dataclass
class SectionMeta:
    """Friendly, orderable metadata for a nav tab (section).

    Attached to the manifest so the frontend can show a bilingual label
    instead of the raw section id, and (custom sections only) override how
    the section renders. Labels are public plaintext in the manifest.
    """
    id: str
    label: dict  # {"en": ..., "zh": ...}; at least one key present
    order: int | None = None
    kind: str | None = None


@dataclass
class SiteConfig:
    title: str
    subtitle: str
    visibility: str
    languages: list[str]
    default_language: str
    theme: str
    timezone: str
    windows: Windows
    ranking: Ranking
    sections: list[SectionMeta] = field(default_factory=list)
    threads: Threads = field(default_factory=Threads)


@dataclass
class TagRule:
    tag: str
    any: list[str]
    # ids of the sources the rule applies to; None = every source in the section
    source_ids: list[str] | None = None


@dataclass
class SourceConfig:
    id: str
    category: str = ""
    type: str = ""
    section: str = ""
    name: str = ""
    url: str | None = None
    path: str | None = None
    query: str | None = None
    # OpenAlex filter expression (e.g. "authorships.author.id:A…" to follow
    # a scholar, "authorships.institutions.lineage:I…" to follow a lab).
    filter: str | None = None
    # Source content language: "zh"/"en" forces items; None/"auto" detects.
    lang: str | None = None
    keywords: list[str] = field(default_factory=list)
    issn: list[str] = field(default_factory=list)
    max_results: int = 50
    weight: float = 0.8
    enabled: bool | str = True
    secret_ref: list[str] = field(default_factory=list)
    preset: str | None = None
    # Resolved against the environment at load time:
    active: bool = False
    skip_reason: str | None = None  # "disabled" | "not_configured"


@dataclass
class Config:
    site: SiteConfig
    sources: list[SourceConfig]
    tag_rules: dict[str, list[TagRule]]  # section id -> rules
    interests_keywords: list[str]
    interests_boost: float

    def sources_for_section(self, section: str) -> list[SourceConfig]:
        return [s for s in self.sources if s.section == section]

    @property
    def sections(self) -> list[str]:
        seen: list[str] = []
        for s in self.sources:
            if s.section not in seen:
                seen.append(s.section)
        return seen


def _load_json(path: Path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise ConfigError(f"missing config file: {path}")
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path}: invalid JSON ({exc})")


def _validate(doc, schema, registry, label: str) -> None:
    validator = jsonschema.Draft202012Validator(schema, registry=registry)
    err = best_match(validator.iter_errors(doc))
    if err is not None:
        raise ConfigError(f"{label}: {err.json_path}: {err.message}")


def _schemas(schema_dir: Path):
    site = _load_json(schema_dir / "site.schema.json")
    sources = _load_json(schema_dir / "sources.schema.json")
    preset = _load_json(schema_dir / "preset.schema.json")
    registry = Registry().with_resource(
        sources["$id"], Resource.from_contents(sources)
    )
    return site, sources, preset, registry


def _source_from_dict(raw: dict, preset: str | None = None) -> SourceConfig:
    src = SourceConfig(id=raw["id"], preset=preset)
    for key in ("category", "type", "section", "name", "url", "path", "query",
                "filter", "lang", "max_results", "weight", "enabled"):
        if key in raw:
            setattr(src, key, raw[key])
    if "keywords" in raw:
        src.keywords = list(raw["keywords"])
    if "issn" in raw:
        src.issn = list(raw["issn"])
    if "secret_ref" in raw:
        src.secret_ref = list(raw["secret_ref"])
    return src


def _apply_override(src: SourceConfig, raw: dict) -> None:
    """Field-by-field override of a preset source by a custom entry."""
    for key in ("category", "type", "section", "name", "url", "path", "query",
                "filter", "lang", "max_results", "weight", "enabled"):
        if key in raw:
            setattr(src, key, raw[key])
    if "keywords" in raw:
        src.keywords = list(raw["keywords"])
    if "issn" in raw:
        src.issn = list(raw["issn"])
    if "secret_ref" in raw:
        src.secret_ref = list(raw["secret_ref"])


def _semantic_check(src: SourceConfig) -> None:
    sid = src.id
    if src.enabled is False:
        return  # disabled entries may be partial (e.g. "turn this preset feed off")
    if src.type not in SOURCE_TYPES:
        raise ConfigError(f"source '{sid}': missing or unknown type {src.type!r}")
    if not src.category:
        src.category = DEFAULT_CATEGORY_BY_TYPE.get(src.type, "open")
    if not src.section:
        raise ConfigError(f"source '{sid}': missing section")
    if not src.name:
        src.name = sid
    if src.category == "private":
        if src.url or src.path:
            raise ConfigError(
                f"source '{sid}': private sources must not carry a url or path; "
                "put capability URLs in GitHub Secrets and use secret_ref"
            )
        if not src.secret_ref:
            raise ConfigError(f"source '{sid}': private sources need secret_ref")
    # Private sources carry no url/path (forbidden above); their capability
    # URL arrives via secret_ref[0] at load time, so exempt them here.
    if src.type == "opml":
        if src.category != "private" and not (src.url or src.path):
            raise ConfigError(f"source '{sid}': opml requires url or path")
    elif src.type in URL_TYPES and not src.url and src.category != "private":
        raise ConfigError(f"source '{sid}': type {src.type} requires url")
    if src.type == "openalex":
        if not (src.query or src.filter):
            raise ConfigError(f"source '{sid}': openalex requires query or filter")
    elif src.type in QUERY_TYPES and not src.query:
        raise ConfigError(f"source '{sid}': type {src.type} requires query")
    if src.type == "crossref" and not (src.query or src.issn):
        raise ConfigError(f"source '{sid}': crossref requires query or issn")


def _resolve_enabled(src: SourceConfig, env: Mapping[str, str]) -> None:
    kill = env.get(f"{src.id.upper()}_ENABLED")
    if kill is not None and kill.strip() == "0":
        src.active, src.skip_reason = False, "disabled"
        return
    if src.enabled is False:
        src.active, src.skip_reason = False, "disabled"
        return
    if src.secret_ref:
        missing = [k for k in src.secret_ref if not env.get(k, "").strip()]
        if missing:
            src.active, src.skip_reason = False, "not_configured"
            return
    src.active, src.skip_reason = True, None


def _resolve_private_url(src: SourceConfig, env: Mapping[str, str]) -> None:
    """Read a private feed's capability URL from ``secret_ref[0]`` into src.url.

    No-op unless the source is an active private feed type. The URL value is
    NEVER echoed in any message or log: an invalid/absent value only flips the
    source to inactive with skip_reason "not_configured". On success the URL
    lives solely in ``src.url`` in process memory for the fetcher to use.
    """
    if (src.category != "private" or src.type not in PRIVATE_URL_TYPES
            or not src.active):
        return
    value = env.get(src.secret_ref[0], "").strip()
    if not value.startswith(("http://", "https://")):
        src.active, src.skip_reason = False, "not_configured"
        return
    src.url = value


def overlay_source_secrets(env: Mapping[str, str]) -> Mapping[str, str]:
    """Fold per-source capability URLs from NEWSDASH_SOURCE_SECRETS into env.

    The workflow passes ``toJSON(secrets)`` as NEWSDASH_SOURCE_SECRETS so that
    per-source ``SRC_<ID>_URL`` secrets need not each be wired explicitly. Only
    keys matching ``^SRC_[A-Z0-9_]+$`` with string values are lifted, and only
    when not already present in env (a real env var always wins). The blob key
    itself is dropped from the returned copy. Parse failures are ignored. None
    of this is ever printed.
    """
    merged = {k: v for k, v in env.items() if k != "NEWSDASH_SOURCE_SECRETS"}
    blob = env.get("NEWSDASH_SOURCE_SECRETS")
    if blob:
        try:
            parsed = json.loads(blob)
        except (ValueError, TypeError):
            parsed = None
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                if (isinstance(k, str) and isinstance(v, str)
                        and _SRC_SECRET_KEY.match(k) and k not in merged):
                    merged[k] = v
    return merged


def load_site(repo_root: Path) -> SiteConfig:
    schema_dir = repo_root / "config" / "schema"
    site_schema, _, _, registry = _schemas(schema_dir)
    doc = _load_json(repo_root / "config" / "site.json")
    _validate(doc, site_schema, registry, "config/site.json")
    win = Windows(**doc.get("windows", {}))
    rank = Ranking(**doc.get("ranking", {}))
    if rank.max_per_source < 1:
        raise ConfigError("config/site.json: ranking.max_per_source must be >= 1")
    sections = _parse_sections(doc.get("sections", []))
    threads = Threads(**doc.get("threads", {}))
    return SiteConfig(
        title=doc["title"],
        subtitle=doc.get("subtitle", ""),
        visibility=doc["visibility"],
        languages=list(doc["languages"]),
        default_language=doc["default_language"],
        theme=doc["theme"],
        timezone=doc["timezone"],
        windows=win,
        ranking=rank,
        sections=sections,
        threads=threads,
    )


def _parse_sections(raw_sections: list[dict]) -> list[SectionMeta]:
    """Parse & semantically check optional section metadata (nav tabs).

    Schema has already checked shape (id pattern, label en/zh, kind enum).
    Here we enforce cross-field rules: ids are unique, a ``kind`` override is
    rejected for built-in sections (news/papers/following/private) so it can
    never redirect the private-section pipeline, and a label must carry at
    least one of en/zh.
    """
    sections: list[SectionMeta] = []
    seen: set[str] = set()
    for raw in raw_sections:
        sid = raw["id"]
        if sid in seen:
            raise ConfigError(
                f"config/site.json: duplicate section metadata id {sid!r}")
        seen.add(sid)
        label = dict(raw.get("label", {}))
        if not any(label.get(k) for k in ("en", "zh")):
            raise ConfigError(
                f"config/site.json: section {sid!r} label needs 'en' or 'zh'")
        kind = raw.get("kind")
        if kind is not None and sid in SECTION_KINDS:
            raise ConfigError(
                f"config/site.json: kind override not allowed for built-in "
                f"section {sid!r}")
        sections.append(SectionMeta(
            id=sid, label=label, order=raw.get("order"), kind=kind))
    return sections


def load_config(repo_root: Path, env: Mapping[str, str] | None = None) -> Config:
    env = env if env is not None else {}
    env = overlay_source_secrets(env)
    schema_dir = repo_root / "config" / "schema"
    _, sources_schema, preset_schema, registry = _schemas(schema_dir)

    site = load_site(repo_root)

    doc = _load_json(repo_root / "config" / "sources.json")
    _validate(doc, sources_schema, registry, "config/sources.json")

    merged: dict[str, SourceConfig] = {}
    tag_rules: dict[str, list[TagRule]] = {}

    for preset_id in doc.get("presets", []):
        pack_path = repo_root / "config" / "presets" / f"{preset_id}.json"
        pack = _load_json(pack_path)
        _validate(pack, preset_schema, registry, f"config/presets/{preset_id}.json")
        for raw in pack["sources"]:
            if raw["id"] in merged:
                raise ConfigError(
                    f"duplicate source id '{raw['id']}' "
                    f"(preset '{preset_id}' vs '{merged[raw['id']].preset}')"
                )
            src = _source_from_dict(raw, preset=preset_id)
            if not src.category:
                src.category = pack["category"]
            if not src.section:
                src.section = pack["section"]
            merged[src.id] = src
        # pack tag rules only tag items from that pack's own sources, so
        # e.g. ai-news "model-release" never fires on a BBC world story
        pack_source_ids = [raw["id"] for raw in pack["sources"]]
        section_rules = tag_rules.setdefault(pack["section"], [])
        for rule in pack.get("tag_rules", []):
            section_rules.append(TagRule(tag=rule["tag"], any=list(rule["any"]),
                                         source_ids=pack_source_ids))

    for raw in doc.get("sources", []):
        if raw["id"] in merged:
            _apply_override(merged[raw["id"]], raw)
        else:
            merged[raw["id"]] = _source_from_dict(raw)

    sources = list(merged.values())
    for src in sources:
        _semantic_check(src)
        _resolve_enabled(src, env)
        _resolve_private_url(src, env)

    # Top-level tag rules apply to every source of the targeted section(s) —
    # unlike pack rules, which stay scoped to their own pack's sources.
    # Appended after pack rules so the more specific tags win the MAX_TAGS race.
    feed_sections = [
        s for s in dict.fromkeys(src.section for src in sources)
        if SECTION_KINDS.get(s, "news") in ("news", "papers")
    ]
    for raw in doc.get("tag_rules", []):
        targets = [raw["section"]] if raw.get("section") else feed_sections
        for sec in targets:
            tag_rules.setdefault(sec, []).append(
                TagRule(tag=raw["tag"], any=list(raw["any"]), source_ids=None))

    interests = doc.get("interests", {})
    return Config(
        site=site,
        sources=sources,
        tag_rules=tag_rules,
        interests_keywords=list(interests.get("keywords", [])),
        interests_boost=float(interests.get("boost", 0.15)),
    )
