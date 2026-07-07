"""Source-status accumulation with private-source redaction.

The public ``source-status.json`` only details open and optional sources.
Private sources appear there as an aggregate count; their per-calendar /
per-course detail rides inside the encrypted section payload metas, and
error strings for private sources are reduced to the exception class name
(requests errors can echo capability URLs)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import SourceConfig


@dataclass
class StatusEntry:
    id: str
    name: str
    category: str
    section: str
    type: str
    ok: bool
    count: int = 0
    error: str | None = None
    skip_reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "section": self.section,
            "type": self.type,
            "ok": self.ok,
            "count": self.count,
            "error": self.error,
            "skip_reason": self.skip_reason,
        }


@dataclass
class StatusAccumulator:
    entries: list[StatusEntry] = field(default_factory=list)

    def record(
        self,
        source: SourceConfig,
        *,
        ok: bool,
        count: int = 0,
        error: Exception | str | None = None,
        skip_reason: str | None = None,
    ) -> None:
        message = None
        if error is not None:
            if source.category == "private":
                # never echo detail that might contain a capability URL
                message = type(error).__name__ if isinstance(error, Exception) else "error"
            else:
                message = str(error)[:200]
        self.entries.append(
            StatusEntry(
                id=source.id,
                name=source.name,
                category=source.category,
                section=source.section,
                type=source.type,
                ok=ok,
                count=count,
                error=message,
                skip_reason=skip_reason,
            )
        )

    def for_section(self, section: str) -> list[dict]:
        return [e.to_dict() for e in self.entries if e.section == section]

    def section_status(self, section: str) -> str:
        entries = [e for e in self.entries if e.section == section]
        if not entries:
            return "not_configured"
        active = [e for e in entries if e.skip_reason is None]
        if not active:
            if any(e.skip_reason == "not_configured" for e in entries):
                return "not_configured"
            return "not_configured"
        if all(not e.ok for e in active):
            return "error"
        if any(not e.ok for e in active):
            return "degraded"
        return "ok"

    def public_dict(self, generated_at: str) -> dict:
        public = [e.to_dict() for e in self.entries if e.category != "private"]
        private = [e for e in self.entries if e.category == "private"]
        return {
            "generated_at": generated_at,
            "sources": public,
            "private_summary": {
                "total": len(private),
                "configured": sum(1 for e in private if e.skip_reason != "not_configured"),
            },
        }
