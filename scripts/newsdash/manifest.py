"""Build data/manifest.json — the frontend's single discovery point.

The manifest is always plaintext (it must be readable before login). In
private mode it carries only section ids/files plus the crypto block; counts
and display detail live inside the encrypted payloads."""

from __future__ import annotations

from . import APP_NAME, __version__
from .config import SiteConfig

MANIFEST_SCHEMA_VERSION = 1


def build_manifest(
    site: SiteConfig,
    sections: list[dict],
    *,
    generated_at: str,
    build_id: str,
    crypto_block: dict | None,
    status: str = "ok",
) -> dict:
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "app": APP_NAME,
        "app_version": __version__,
        "status": status,
        "generated_at": generated_at,
        "build_id": build_id,
        "site": {
            "title": site.title,
            "subtitle": site.subtitle,
            "languages": site.languages,
            "default_language": site.default_language,
            "theme": site.theme,
            "timezone": site.timezone,
            "visibility": site.visibility,
        },
        "sections": sections,
        "source_status_file": None,  # set by the builder
    }
    if crypto_block is not None:
        manifest["crypto"] = crypto_block
    return manifest
