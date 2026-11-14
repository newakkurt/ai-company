import gzip
import json
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from company import research_sources as rs

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)


def fake_fetch(url):
    if "stackexchange" in url:
        return {"items": [
            {"title": "How do I back up &amp; diff switch configs?", "score": 42, "answer_count": 5,
             "view_count": 9000, "link": "https://networkengineering.stackexchange.com/q/1",
             "creation_date": 1760000000},
            {"title": "Second", "score": 7, "answer_count": 1, "view_count": 10,
             "link": "https://networkengineering.stackexchange.com/q/2", "creation_date": 1750000000},
        ]}
    return {"hits": [{"objectID": "99", "title": "Show HN: config drift tool", "points": 120,
                      "num_comments": 33, "created_at_i": 1761000000}]}


class ResearchSourcesTests(unittest.TestCase):
    def setUp(self):
        rs._cache.clear()

    def test_collect_unescapes_dedupes_and_orders_by_score(self):
        items = rs.collect(now=NOW, fetch=fake_fetch)
        self.assertEqual(items[0]["score"], 120)
        self.assertEqual(items[0]["url"], "https://news.ycombinator.com/item?id=99")
        titles = [i["title"] for i in items]
        self.assertIn("How do I back up & diff switch configs?", titles)
        self.assertEqual(len({i["url"] for i in items}), len(items))

    def test_format_is_bounded_and_cites_urls(self):
        items = rs.collect(now=NOW, fetch=fake_fetch)
        block = rs.format_evidence(items, budget=420, retrieved="2026-11-14")
        self.assertLessEqual(len(block), 420)
        self.assertIn("Cite only these URLs", block)
        self.assertIn("https://", block)

    def test_failures_degrade_to_empty_without_raising(self):
        def boom(url):
            raise OSError("network down")
        self.assertEqual(rs.collect(now=NOW, fetch=boom), [])
        self.assertEqual(rs.demand_evidence_block(now=NOW, fetch=boom), ("", 0))

    def test_one_failing_source_does_not_hide_the_others(self):
        def partial(url):
            if "stackexchange" in url:
                raise OSError("quota")
            return fake_fetch(url)
        items = rs.collect(now=NOW, fetch=partial)
        self.assertTrue(items)
        self.assertTrue(all(i["source"] == "hackernews" for i in items))

    def test_results_are_cached(self):
        fetch = Mock(side_effect=fake_fetch)
        rs.collect(now=NOW, fetch=fetch)
        calls = fetch.call_count
        rs.collect(now=NOW, fetch=fetch)
        self.assertEqual(fetch.call_count, calls)

    def test_env_switch_disables_evidence(self):
        with patch.dict(os.environ, {"AI_COMPANY_WEB_EVIDENCE": "false"}):
            self.assertEqual(rs.demand_evidence_block(now=NOW, fetch=fake_fetch), ("", 0))

    def test_gzip_responses_are_decoded(self):
        payload = gzip.compress(json.dumps({"items": []}).encode())
        response = Mock()
        response.read.return_value = payload
        response.headers = {"Content-Encoding": "gzip"}
        response.__enter__ = lambda s: s
        response.__exit__ = lambda *a: False
        with patch("company.research_sources.urlopen", return_value=response):
            self.assertEqual(rs._get_json("https://example.test"), {"items": []})
