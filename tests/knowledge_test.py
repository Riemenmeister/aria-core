import json
import os
import sys
import tempfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import aria_events
import aria_knowledge
from aria_events import EventType


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_wikipedia_summary_uses_rest_payload():
    aria_events.reset()
    received = []
    aria_events.subscribe(EventType.KNOWLEDGE_QUERIED, received.append)
    payload = {
        "title": "Aria",
        "description": "Test entry",
        "extract": "A short summary.",
        "content_urls": {"desktop": {"page": "https://example.test/wiki/Aria"}},
    }
    with mock.patch("urllib.request.urlopen", return_value=FakeResponse(payload)):
        summary = aria_knowledge.WikipediaClient(language="de").summary("Aria")

    assert summary["title"] == "Aria"
    assert summary["description"] == "Test entry"
    assert summary["extract"] == "A short summary."
    assert summary["url"] == "https://example.test/wiki/Aria"
    assert len(received) == 1
    assert received[0].event_type == EventType.KNOWLEDGE_QUERIED
    assert received[0].payload["source"] == "wikipedia"
    assert received[0].payload["action"] == "summary"
    assert received[0].payload["title"] == "Aria"


def test_wikipedia_search_publishes_event():
    aria_events.reset()
    received = []
    aria_events.subscribe(EventType.KNOWLEDGE_QUERIED, received.append)
    payload = {
        "pages": [
            {
                "title": "TCP",
                "description": "Protocol",
                "excerpt": "Transmission Control Protocol",
                "key": "TCP",
            }
        ]
    }
    with mock.patch("urllib.request.urlopen", return_value=FakeResponse(payload)):
        results = aria_knowledge.WikipediaClient(language="en").search("TCP", limit=1)

    assert len(results) == 1
    assert results[0]["title"] == "TCP"
    assert len(received) == 1
    assert received[0].payload["action"] == "search"
    assert received[0].payload["result_count"] == 1


def test_mentor_memory_round_trip():
    aria_events.reset()
    received = []
    aria_events.subscribe(EventType.MENTOR_OBSERVED, received.append)
    with tempfile.TemporaryDirectory() as temp_dir:
        memory_file = os.path.join(temp_dir, "mentor.jsonl")
        aria_knowledge.learn_from_mentor(
            "Gemini empfiehlt Quellen zu vergleichen.",
            source="gemini",
            memory_file=memory_file,
        )

        rows = aria_knowledge.read_mentor_memory(memory_file=memory_file)

    assert len(rows) == 1
    assert rows[0]["source"] == "gemini"
    assert rows[0]["note"] == "Gemini empfiehlt Quellen zu vergleichen."
    assert len(received) == 1
    assert received[0].event_type == EventType.MENTOR_OBSERVED
    assert received[0].payload["source"] == "gemini"


if __name__ == "__main__":
    test_wikipedia_summary_uses_rest_payload()
    test_wikipedia_search_publishes_event()
    test_mentor_memory_round_trip()
    print("knowledge tests: PASS")
