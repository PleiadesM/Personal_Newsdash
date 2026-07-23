# Threads · 线索 — design note

Why this block looks the way it does. Not a spec (see `DATA_CONTRACT.md` for
the payload, `CONFIG_REFERENCE.md` for the knobs) — a record of the two ideas
the design answers to, so future changes can be argued against them rather
than against taste.

## Relevance is an act, not a property

The project is named after the argument of Elisa Tamarkin's *Apropos of
Something: A History of Irrelevance and Relevance* (Chicago, 2022): relevance
is not something an item of news *has*; it is something a reader *does*. The
word descends from *relevate* — to lift something back into attention, as
Tamarkin puts it, "to raise it in another context on another occasion."
Nothing is relevant in general; things become relevant on an occasion, to
someone, in relation to their hour.

Threads takes that seriously in four ways:

1. **A thread is a raising-again, not a ranking.** The LLM's job is not to
   score items but to notice where several sources, on the same day, are
   circling the same thing — and to lift that convergence into view. The
   angles show how differently each source treats it; the reader, not the
   pipeline, decides what it means for them.
2. **The occasion is named.** Each card carries a one-line *why now* — because
   relevance exists only on occasions, the occasion is part of the content.
3. **The editorial hand is visible.** The block is dated, capped at six, and
   says what it is: today's footholds, chosen by a model, gone tomorrow.
   Ephemerality is not a limitation; a dashboard, like a morning paper, is an
   orientation ritual, and orientation is re-done daily.
4. **Threads touch.** News arrives as an ecology, not a list — one story
   reframes another. The small *touches:* links record that succession
   without building a graph out of it.

## Inscriptions that travel

The visual grammar follows Bruno Latour's "Visualisation and Cognition:
Drawing Things Together" (1986): what makes an inscription powerful is not
realism or decoration but that it is flat, stable, combinable, and lets you
*present absent things all at once* — and then go back to them. Hence:

1. **Flat, same-shaped cards.** Every thread is the same kind of object, so
   the day can be taken in at a glance and cards can be compared without
   re-learning a layout.
2. **The return ticket.** Latour's mobile inscriptions are two-way: the map
   must lead back to the coastline. Every angle row links back to the item it
   summarizes (in-app reader when full text exists, the source page
   otherwise). No claim in a thread is more than one click from its evidence.
3. **A cascade, not a dashboard-within-a-dashboard.** keyword → angle → item
   → full text. Each step adds detail; nothing at the top duplicates what a
   click reveals below.
4. **One honest encoding.** The only non-typographic mark is the convergence
   glyph — three strokes meeting, mixed, or fanning apart — because whether
   sources agree is the one thing the block knows that a list of links would
   hide. Everything else is typography; ornament would only add cognitive
   load without adding a way back to the sources.

## Consequences that look like quirks

- Angles are **not filtered by content language**. Elsewhere the site hides
  items whose language differs from the UI language; here, a Chinese source
  and an English source treating the same theme *is the finding*. Don't "fix"
  this.
- Threads **replace Highlights but never delete it**: when there is no LLM
  key, no threads file, or the payload fails, the algorithmic Highlights
  block renders instead. The feature degrades to arithmetic, never to a hole.
- Private-scope threads exist so that private sections (e.g. a career feed)
  get the same raising-again — but they are computed from private input only,
  written encrypted only, and rendered only after unlock. Public threads are
  never built from private items; the two scopes never share a call.
