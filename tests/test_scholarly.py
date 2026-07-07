import json
from pathlib import Path

import responses

from newsdash.fetchers import arxiv, crossref, openalex, semanticscholar
from newsdash.models import item_id

FIX = Path(__file__).parent / "fixtures" / "scholarly"


@responses.activate
def test_arxiv_parse_and_keyword_filter(make_ctx, make_source):
    responses.get(arxiv.API, body=(FIX / "arxiv_atom.xml").read_text())
    source = make_source(id="arxiv_hc", type="arxiv", category="optional",
                         section="papers", query="cat:cs.HC",
                         keywords=["visualization"])
    items = arxiv.fetch(source, make_ctx())
    assert len(items) == 1  # the OS paper does not match the keywords
    paper = items[0]
    assert paper.kind == "paper"
    assert paper.extra["arxiv_id"] == "2507.01234"
    assert paper.id == item_id(arxiv_id="2507.01234")
    assert paper.venue == "arXiv cs.HC"
    assert paper.authors == ["Ada Lovelace", "Wei Chen"]


@responses.activate
def test_openalex_parse(make_ctx, make_source):
    responses.get(openalex.API, body=(FIX / "openalex_works.json").read_text())
    source = make_source(id="oa", type="openalex", category="optional",
                         section="papers", query="information visualization")
    items = openalex.fetch(source, make_ctx(env={"CONTACT_MAILTO": "x@y.edu"}))
    assert len(items) == 1  # dateless record skipped
    paper = items[0]
    assert paper.extra["doi"] == "10.1145/999"
    assert paper.id == item_id(doi="10.1145/999")
    assert paper.venue == "ACM CHI"
    assert paper.summary == "We revisit declarative visualization grammars."
    assert "mailto=x%40y.edu" in responses.calls[0].request.url


@responses.activate
def test_crossref_issn_mode(make_ctx, make_source):
    responses.get(crossref.API, body=(FIX / "crossref_works.json").read_text())
    source = make_source(id="cr", type="crossref", category="optional",
                         section="papers", issn=["1050-6519"])
    items = crossref.fetch(source, make_ctx())
    assert len(items) == 1  # titleless record skipped
    paper = items[0]
    assert paper.venue == "Journal of Business and Technical Communication"
    assert paper.authors == ["Mary Sue", "Li Wang"]
    assert paper.summary.startswith("We examine")
    assert "issn%3A1050-6519" in responses.calls[0].request.url


@responses.activate
def test_semanticscholar_parse(make_ctx, make_source):
    responses.get(semanticscholar.API, body=(FIX / "s2_search.json").read_text())
    source = make_source(id="s2", type="semanticscholar", category="optional",
                         section="papers", query="data visualization")
    items = semanticscholar.fetch(source, make_ctx())
    assert len(items) == 1
    paper = items[0]
    assert paper.extra["doi"] == "10.1109/vis.2026.42"
    assert paper.extra["arxiv_id"] == "2507.00042"
    assert paper.venue == "IEEE VIS"


@responses.activate
def test_openalex_503_without_key_is_best_effort(make_ctx, make_source):
    responses.get(openalex.API, status=503)
    source = make_source(id="oa", type="openalex", category="optional",
                         section="papers", query="x")
    assert openalex.fetch(source, make_ctx()) == []


@responses.activate
def test_openalex_503_with_key_raises(make_ctx, make_source):
    import pytest
    import requests

    responses.get(openalex.API, status=503)
    source = make_source(id="oa", type="openalex", category="optional",
                         section="papers", query="x")
    with pytest.raises(requests.HTTPError):
        openalex.fetch(source, make_ctx(env={"OPENALEX_API_KEY": "k"}))


@responses.activate
def test_semanticscholar_429_is_best_effort(make_ctx, make_source):
    responses.get(semanticscholar.API, status=429)
    source = make_source(id="s2", type="semanticscholar", category="optional",
                         section="papers", query="x")
    assert semanticscholar.fetch(source, make_ctx()) == []
