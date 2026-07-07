"""Config loading, validation, preset resolution, and environment overlay.

All config is JSON so the browser, the pipeline, issue-ops, and agents read
and write the same files. Validation is two-layered: JSON Schema for shape,
then semantic checks for cross-field rules a schema cannot express (e.g. an
effective source, after preset overrides, must still have a type and section).

Security invariants enforced here:
- private sources may not carry a ``url`` (capability URLs live in Secrets);
- ``enabled: "auto"`` resolves to on only when every env var named in
  ``secret_ref`` is present and non-empty (key-present => on);
- ``<ID>_ENABLED=0`` in the environment is a kill switch for any source.
"""

from __future__ import annotations

import json
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
SECRET_TYPES = {"ics", "canvas"}
SOURCE_TYPES = URL_TYPES | QUERY_TYPES | SECRET_TYPES | {"crossref"}

# Category a source falls into when the config does not say.
DEFAULT_CATEGORY_BY_TYPE = {
    "ics": "private",
    "canvas": "private",
    "arxiv": "optional",
    "openalex": "optional",
    "crossref": "optional",
    "semanticscholar": "optional",
}

# Sections the v0.1 frontend knows how to render, and what lives in them.
SECTION_KINDS = {
    "news": "news",
    "papers": "papers",
    "schedule": "schedule",
    "courses": "courses",
}


@dataclass
class Windows:
    news_hours: int = 24
    papers_days: int = 7
    schedule_past_days: int = 1
    schedule_horizon_days: int = 14
    courses_horizon_days: int = 30
    archive_days: int = 14


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
                "max_results", "weight", "enabled"):
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
                "max_results", "weight", "enabled"):
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
    if src.type == "opml":
        if not (src.url or src.path):
            raise ConfigError(f"source '{sid}': opml requires url or path")
    elif src.type in URL_TYPES and not src.url:
        raise ConfigError(f"source '{sid}': type {src.type} requires url")
    if src.type in QUERY_TYPES and not src.query:
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


def load_site(repo_root: Path) -> SiteConfig:
    schema_dir = repo_root / "config" / "schema"
    site_schema, _, _, registry = _schemas(schema_dir)
    doc = _load_json(repo_root / "config" / "site.json")
    _validate(doc, site_schema, registry, "config/site.json")
    win = Windows(**doc.get("windows", {}))
    return SiteConfig(
        title=doc["title"],
        subtitle=doc.get("subtitle", ""),
        visibility=doc["visibility"],
        languages=list(doc["languages"]),
        default_language=doc["default_language"],
        theme=doc["theme"],
        timezone=doc["timezone"],
        windows=win,
    )


def load_config(repo_root: Path, env: Mapping[str, str] | None = None) -> Config:
    env = env if env is not None else {}
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

    interests = doc.get("interests", {})
    return Config(
        site=site,
        sources=sources,
        tag_rules=tag_rules,
        interests_keywords=list(interests.get("keywords", [])),
        interests_boost=float(interests.get("boost", 0.15)),
    )
