"""Unit tests for the Hacker News engine in the TIMPS web search agent.

No network access: `requests.get` is monkeypatched with canned responses that
mirror the documented shapes of the two APIs in
https://github.com/HackerNews/API (Firebase lists/items) and Algolia HN Search.
"""

import importlib

import pytest

# `src.nextgen.__init__` re-exports the `web_search` function, so import the
# module explicitly to reach the engine adapters.
ws = importlib.import_module("src.nextgen.web_search")


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _patch_get(monkeypatch, handler):
    """Route requests.get(url, params=...) through a small fake."""
    calls = []

    def fake_get(url, params=None, **kwargs):
        calls.append({"url": url, "params": params or {}})
        return FakeResponse(handler(url, params or {}))

    monkeypatch.setattr("requests.get", fake_get)
    return calls


def test_algolia_keyword_search_maps_hits(monkeypatch):
    payload = {
        "hits": [
            {
                "objectID": "101",
                "title": "Show HN: A tiny agent runtime",
                "url": "https://example.com/agent",
                "author": "alice",
                "points": 321,
                "num_comments": 87,
                "created_at": "2026-11-10T12:00:00Z",
                "story_text": None,
            },
            {
                "objectID": "102",
                "title": None,
                "url": None,  # comment hit without a title is skipped
            },
        ]
    }
    calls = _patch_get(monkeypatch, lambda url, params: payload)

    results = ws._search_hackernews("agent runtime", 5, "any", "general", {})

    assert len(results) == 1
    hit = results[0]
    assert hit["source_engine"] == "hackernews"
    assert hit["title"] == "Show HN: A tiny agent runtime"
    assert hit["url"] == "https://example.com/agent"
    assert "321 points" in hit["snippet"]
    assert "87 comments" in hit["snippet"]
    assert calls[0]["url"] == ws.HN_ALGOLIA
    assert calls[0]["params"]["query"] == "agent runtime"
    assert calls[0]["params"]["tags"] == "story"


def test_algolia_recency_and_date_sort_use_search_by_date(monkeypatch):
    calls = _patch_get(monkeypatch, lambda url, params: {"hits": []})

    ws._search_hackernews(
        "kubernetes",
        3,
        "week",
        "news",
        {"hn_sort": "date", "hn_tags": "ask_hn"},
    )

    assert calls[0]["url"] == ws.HN_ALGOLIA_BY_DATE
    assert calls[0]["params"]["tags"] == "ask_hn"
    assert calls[0]["params"]["numericFilters"].startswith("created_at_i>")


def test_firebase_list_mode_fetches_items(monkeypatch):
    def handler(url, params):
        if url.endswith("/topstories.json"):
            return [1, 2, 3]
        if url.endswith("/item/1.json"):
            return {
                "id": 1,
                "type": "story",
                "title": "Rust rewrite of a database",
                "url": "https://example.com/rust-db",
                "score": 512,
                "by": "bob",
                "time": 1_760_000_000,
                "descendants": 210,
            }
        if url.endswith("/item/2.json"):
            return {"id": 2, "dead": True, "title": "dead story"}
        if url.endswith("/item/3.json"):
            return {
                "id": 3,
                "type": "story",
                "title": "Ask HN: What are you working on?",
                # no external url -> link to the HN item page
                "score": 42,
                "by": "carol",
                "time": 1_760_000_100,
                "descendants": 99,
            }
        raise AssertionError(f"unexpected url {url}")

    calls = _patch_get(monkeypatch, handler)

    results = ws._search_hackernews("hn:top", 5, "any", "general", {})

    assert [r["hn_id"] for r in results] == [1, 3]
    assert results[0]["url"] == "https://example.com/rust-db"
    assert results[1]["url"] == ws.HN_ITEM_URL.format(id=3)
    assert "Ask HN" in results[1]["title"]
    assert any(c["url"].endswith("/topstories.json") for c in calls)
    # dead item was filtered out
    assert all(r["title"] != "dead story" for r in results)


def test_unknown_hn_list_raises():
    with pytest.raises(ValueError, match="Unknown Hacker News list"):
        ws._search_hackernews("hn:nope", 5, "any", "general", {})


def test_web_search_auto_selects_hackernews_for_hn_prefix(monkeypatch, tmp_path):
    _patch_get(monkeypatch, lambda url, params: {"hits": []})
    monkeypatch.setattr(ws, "_GEN", tmp_path)

    payload = ws.web_search({
        "query": "hn:new",
        "max_results": 3,
        "synthesize": False,
        "fetch_content": False,
    })

    assert payload["engines_used"] == ["hackernews"]


def test_web_search_accepts_hackernews_as_comma_separated_string(monkeypatch, tmp_path):
    _patch_get(monkeypatch, lambda url, params: {"hits": []})
    monkeypatch.setattr(ws, "_GEN", tmp_path)

    payload = ws.web_search({
        "query": "llm",
        "engines": "hackernews",
        "max_results": 3,
        "synthesize": False,
        "fetch_content": False,
    })

    assert payload["engines_used"] == ["hackernews"]
    assert payload["engine_status"]["hackernews"].startswith("ok")
    assert (tmp_path / "web_search").exists()
