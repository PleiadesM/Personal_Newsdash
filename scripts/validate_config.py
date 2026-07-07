#!/usr/bin/env python3
"""Validate config/*.json and print a short summary.

Used by CI, the setup-from-issue workflow, and the Page Skill. Exits 1 with a
``::error::`` annotation on the first problem found.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from newsdash.config import ConfigError, load_config


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    try:
        cfg = load_config(repo_root, os.environ)
    except ConfigError as exc:
        print(f"::error::config invalid: {exc}")
        sys.exit(1)

    print(f"site: {cfg.site.title!r} · visibility={cfg.site.visibility} "
          f"· theme={cfg.site.theme} · tz={cfg.site.timezone}")
    for category in ("open", "optional", "private"):
        group = [s for s in cfg.sources if s.category == category]
        active = sum(1 for s in group if s.active)
        waiting = sum(1 for s in group if s.skip_reason == "not_configured")
        print(f"{category:>8}: {len(group)} sources "
              f"({active} active, {waiting} awaiting secrets)")
    print(f"sections: {', '.join(cfg.sections)}")
    print("config OK")


if __name__ == "__main__":
    main()
