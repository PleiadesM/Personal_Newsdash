"""Optional Apropos-of-Nothing AI discovery.

Build-time only, off unless ``LLM_API_KEY`` is configured. The LLM first
chooses a benign, off-profile search topic from the public news/papers
context, then the pipeline searches public news through GDELT's DOC API and
asks the LLM for a short bilingual summary of one result.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Mapping

import requests
from dateutil import parser as dateparser

from .http import get
from .models import clip, iso_utc, strip_html
from .summarize import _extract_json, _item_lines, _post_chat

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
MAX_CONTEXT_NEWS = 18
MAX_CONTEXT_PAPERS = 8
MAX_GDELT_RESULTS = 8
GDELT_SOFT_FAIL_STATUSES = {429}
QUERY_KEYS = ("topic", "search_terms", "why_irrelevant")
SUMMARY_LANGS = ("en", "zh")

QUERY_SYSTEM_PROMPT = (
    "You are the Apropos-of-Nothing editor for a personal dashboard. "
    "Your job is to break an echo chamber with one benign public-news topic "
    "that is maximally unrelated to the user's current feed. Avoid the user's "
    "dominant topics, sources, professions, fields, and obvious adjacent "
    "themes. Prefer concrete, slightly odd, low-stakes topics: local culture, "
    "crafts, food, sports niches, weather curiosities, archaeology, festivals, "
    "transport oddities, or nature. Avoid tragedy, gore, scandal, conspiracy, "
    "medical advice, and sexual content. Respond with a single json object "
    "shaped exactly like this example: "
    '{"topic": "competitive pumpkin growing", "search_terms": '
    '["pumpkin championship", "giant pumpkin"], "why_irrelevant": '
    '"A deliberately distant detour from the feed."}'
)

SUMMARY_SYSTEM_PROMPT = (
    "You write the Apropos-of-Nothing card for a personal dashboard. Pick one "
    "candidate that is concrete, sourceable, benign, and far from the user's "
    "feed. Write a tiny bilingual card. Respond with a single json object "
    "shaped exactly like this example: "
    '{"choice": 1, "summaries": {"en": {"summary": "One crisp English '
    'sentence about the chosen item.", "why_irrelevant": "One short English '
    'clause explaining why it is off-profile."}, "zh": {"summary": '
    '"One concise Simplified Chinese sentence.", "why_irrelevant": '
    '"One concise Simplified Chinese clause."}}}'
)


def _context_prompt(payloads: dict[str, dict]) -> str:
    news = sorted(
        payloads.get("news", {}).get("items", []),
        key=lambda it: it.get("score") or 0,
        reverse=True,
    )
    papers = sorted(
        payloads.get("papers", {}).get("items", []),
        key=lambda it: it.get("score") or 0,
        reverse=True,
    )
    return (
        "Current news/research context to avoid:\n\n"
        f"News:\n{_item_lines(news, MAX_CONTEXT_NEWS)}\n\n"
        f"Papers/research:\n{_item_lines(papers, MAX_CONTEXT_PAPERS)}"
    )


def _llm_json(label: str, base_url: str, api_key: str, model: str,
              messages: list[dict], session: requests.Session) -> dict | None:
    try:
        content = _post_chat(
            base_url, api_key, model, messages, session, json_mode=True)
        result = _extract_json(content)
        if not isinstance(result, dict):
            raise ValueError("json root was not an object")
        return result
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "?"
        detail = ""
        if exc.response is not None:
            detail = exc.response.text.strip().replace(api_key, "***")[:200]
        print(f"[apropos-of-nothing:{label}] error: HTTPError ({status}) {detail}")
        return None
    except Exception as exc:  # noqa: BLE001 - enrichment must not fail builds
        print(f"[apropos-of-nothing:{label}] error: {type(exc).__name__}: "
              f"{str(exc)[:200]}")
        return None


def _clean_term(value) -> str:
    text = strip_html(str(value or ""))
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = text.strip(" \"'`")
    text = re.sub(r"[\"'`(){}\[\]<>|:*?~^\\]+", " ", text)
    text = re.sub(r"\b(?:AND|OR|NOT)\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[^A-Za-z0-9 .,&/-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .,&/-")
    if len(text) > 48:
        text = text[:48].rsplit(" ", 1)[0] or text[:48]
    return text


def _terms_from(value) -> list[str]:
    raw = value
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    terms: list[str] = []
    seen: set[str] = set()
    for item in raw:
        term = _clean_term(item)
        key = term.casefold()
        if len(term) < 3 or key in seen:
            continue
        seen.add(key)
        terms.append(term)
        if len(terms) == 4:
            break
    return terms


def _quote_query_term(term: str) -> str:
    if " " in term:
        return f'"{term}"'
    return term


def _gdelt_query(terms: list[str]) -> str:
    quoted = [_quote_query_term(t) for t in terms]
    if len(quoted) == 1:
        return quoted[0]
    return "(" + " OR ".join(quoted) + ")"


def _parse_article_date(value) -> str | None:
    if not value:
        return None
    text = str(value)
    try:
        if re.fullmatch(r"\d{14}", text):
            dt = datetime.strptime(text, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        else:
            dt = dateparser.parse(text)
            if dt is None:
                return None
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return iso_utc(dt)
    except (ValueError, OverflowError):
        return None


def _article_source_name(article: dict) -> str:
    return (
        article.get("domain")
        or article.get("source")
        or article.get("sourceCountry")
        or article.get("sourcecountry")
        or "GDELT"
    )


def _normalize_articles(doc: dict) -> list[dict]:
    raw_articles = doc.get("articles") if isinstance(doc, dict) else []
    if not isinstance(raw_articles, list):
        return []
    articles: list[dict] = []
    seen: set[str] = set()
    for article in raw_articles:
        if not isinstance(article, dict):
            continue
        url = (article.get("url") or article.get("url_mobile") or "").strip()
        title = strip_html(article.get("title") or "").strip()
        if not title or not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        summary = clip(strip_html(
            article.get("snippet") or article.get("summary")
            or article.get("description") or ""
        ))
        articles.append({
            "title": title,
            "url": url,
            "source_name": strip_html(_article_source_name(article)).strip() or "GDELT",
            "published_at": _parse_article_date(
                article.get("seendate") or article.get("published_at")
                or article.get("date")
            ),
            "summary": summary,
        })
    return articles


def _search_gdelt(terms: list[str], session: requests.Session) -> tuple[str, list[dict]]:
    query = _gdelt_query(terms)
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": str(MAX_GDELT_RESULTS),
        "timespan": "1week",
        "sort": "datedesc",
    }
    try:
        doc = get(session, GDELT_DOC_URL, params=params).json()
        return query, _normalize_articles(doc)
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status in GDELT_SOFT_FAIL_STATUSES:
            print("[apropos-of-nothing:search] skipped: GDELT rate-limited "
                  f"({status}); will try again next build")
            return query, []
        print(f"[apropos-of-nothing:search] error: HTTPError: {str(exc)[:200]}")
        return query, []
    except Exception as exc:  # noqa: BLE001 - optional enrichment
        print(f"[apropos-of-nothing:search] error: {type(exc).__name__}: "
              f"{str(exc)[:200]}")
        return query, []


def _candidate_lines(articles: list[dict]) -> str:
    lines = []
    for idx, article in enumerate(articles, start=1):
        parts = [
            f"[{idx}] {article['title']}",
            article.get("source_name") or "",
            article.get("published_at") or "",
            article.get("summary") or "",
        ]
        lines.append(" - ".join(p for p in parts if p)[:500])
    return "\n".join(lines)


def _clean_summary_block(data: dict) -> dict | None:
    summaries = data.get("summaries")
    if not isinstance(summaries, dict):
        return None
    cleaned: dict[str, dict] = {}
    for lang in SUMMARY_LANGS:
        block = summaries.get(lang)
        if not isinstance(block, dict):
            continue
        summary = clip(strip_html(block.get("summary") or ""), 260)
        why = clip(strip_html(block.get("why_irrelevant") or ""), 180)
        if summary:
            cleaned[lang] = {"summary": summary, "why_irrelevant": why}
    return cleaned or None


def _choice_index(data: dict, article_count: int) -> int:
    try:
        choice = int(data.get("choice", 1))
    except (TypeError, ValueError):
        choice = 1
    return min(max(choice, 1), article_count) - 1


def find_apropos_of_nothing(payloads: dict[str, dict], env: Mapping[str, str],
                            session: requests.Session) -> dict | None:
    api_key = env.get("LLM_API_KEY", "").strip()
    if (
        not api_key
        or env.get("LLM_SUMMARY_ENABLED") == "0"
        or env.get("APROPOS_OF_NOTHING_ENABLED") == "0"
    ):
        return None

    news_items = payloads.get("news", {}).get("items", [])
    paper_items = payloads.get("papers", {}).get("items", [])
    if not news_items and not paper_items:
        return None

    base_url = (env.get("LLM_BASE_URL") or "https://api.openai.com/v1").strip()
    model = (env.get("LLM_MODEL") or "gpt-4o-mini").strip()

    idea = _llm_json(
        "query",
        base_url,
        api_key,
        model,
        [
            {"role": "system", "content": QUERY_SYSTEM_PROMPT},
            {"role": "user", "content": _context_prompt(payloads)},
        ],
        session,
    )
    if not idea or not all(k in idea for k in QUERY_KEYS):
        print("[apropos-of-nothing:query] error: response missing keys")
        return None

    terms = _terms_from(idea.get("search_terms"))
    if not terms:
        print("[apropos-of-nothing:query] error: no usable search terms")
        return None

    query, articles = _search_gdelt(terms, session)
    if not articles:
        return None

    summary_data = _llm_json(
        "summary",
        base_url,
        api_key,
        model,
        [
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Original off-profile idea: {strip_html(idea.get('topic') or '')}\n"
                f"Why it should be irrelevant: "
                f"{strip_html(idea.get('why_irrelevant') or '')}\n\n"
                f"Candidates:\n{_candidate_lines(articles)}"
            )},
        ],
        session,
    )
    if not summary_data:
        return None
    summaries = _clean_summary_block(summary_data)
    if not summaries:
        print("[apropos-of-nothing:summary] error: response missing summaries")
        return None

    article = articles[_choice_index(summary_data, len(articles))]
    return {
        "topic": clip(strip_html(idea.get("topic") or terms[0]), 90),
        "query": query,
        "summaries": summaries,
        "source": {
            "title": article["title"],
            "url": article["url"],
            "name": article.get("source_name") or "GDELT",
            "published_at": article.get("published_at"),
        },
    }
