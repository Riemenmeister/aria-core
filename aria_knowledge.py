import argparse
import json
import os
import re
import sys
import textwrap
import urllib.parse
import urllib.request
from datetime import datetime, timezone


DEFAULT_LANGUAGE = os.environ.get("ARIA_WIKI_LANG", "de")
DEFAULT_MEMORY_FILE = os.environ.get(
    "ARIA_MENTOR_MEMORY",
    os.path.join("memory", "gemini_mentor.jsonl"),
)
WIKIPEDIA_USER_AGENT = os.environ.get(
    "ARIA_WIKI_USER_AGENT",
    "AriaCore/0.1.0 (local knowledge assistant)",
)


class WikipediaClient:
    def __init__(self, language=DEFAULT_LANGUAGE, timeout=10):
        self.language = language.lower()
        self.timeout = timeout

    @property
    def api_base(self):
        return f"https://{self.language}.wikipedia.org/api/rest_v1"

    @property
    def search_base(self):
        return f"https://{self.language}.wikipedia.org/w/rest.php/v1"

    def summary(self, title):
        encoded_title = urllib.parse.quote(title.replace(" ", "_"), safe="")
        url = f"{self.api_base}/page/summary/{encoded_title}"
        data = self._get_json(url)
        return {
            "title": data.get("title", title),
            "description": data.get("description", ""),
            "extract": data.get("extract", ""),
            "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
        }

    def search(self, query, limit=5):
        params = urllib.parse.urlencode({"q": query, "limit": limit})
        url = f"{self.search_base}/search/page?{params}"
        data = self._get_json(url)
        pages = data.get("pages", [])
        return [
            {
                "title": page.get("title", ""),
                "description": page.get("description", ""),
                "excerpt": page.get("excerpt", ""),
                "url": f"https://{self.language}.wikipedia.org/wiki/"
                f"{urllib.parse.quote(page.get('key', page.get('title', '')).replace(' ', '_'))}",
            }
            for page in pages
        ]

    def _get_json(self, url):
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": WIKIPEDIA_USER_AGENT,
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read().decode("utf-8"))


def learn_from_mentor(note, source="gemini", memory_file=DEFAULT_MEMORY_FILE):
    os.makedirs(os.path.dirname(memory_file) or ".", exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "note": note.strip(),
    }
    with open(memory_file, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_mentor_memory(memory_file=DEFAULT_MEMORY_FILE, limit=10):
    if not os.path.exists(memory_file):
        return []
    with open(memory_file, "r", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    return rows[-limit:]


def print_summary(summary):
    print(summary["title"])
    if summary["description"]:
        print(summary["description"])
    if summary["extract"]:
        print()
        print(textwrap.fill(summary["extract"], width=88))
    if summary["url"]:
        print()
        print(summary["url"])


def print_search_results(results):
    for index, result in enumerate(results, start=1):
        print(f"{index}. {result['title']}")
        if result["description"]:
            print(f"   {result['description']}")
        if result["url"]:
            print(f"   {result['url']}")


def validate_language_code(value):
    normalized = value.strip().lower()
    if not re.fullmatch(r"[a-z]+(?:-[a-z]+)?", normalized):
        raise argparse.ArgumentTypeError(
            "Language code must be letters with optional single dash, e.g. de, en, simple, pt-br"
        )
    return normalized


def build_parser():
    parser = argparse.ArgumentParser(description="Aria knowledge bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    wiki = subparsers.add_parser("wiki", help="Fetch a Wikipedia page summary")
    wiki.add_argument("title", help="Wikipedia page title or topic")
    wiki.add_argument(
        "--lang",
        default=DEFAULT_LANGUAGE,
        type=validate_language_code,
        help="Wikipedia language code",
    )

    search = subparsers.add_parser("search", help="Search Wikipedia pages")
    search.add_argument("query", help="Search query")
    search.add_argument(
        "--lang",
        default=DEFAULT_LANGUAGE,
        type=validate_language_code,
        help="Wikipedia language code",
    )
    search.add_argument("--limit", type=int, default=5, help="Maximum result count")

    learn = subparsers.add_parser("learn", help="Store a mentor observation")
    learn.add_argument("note", nargs="?", help="Observation text; reads stdin when omitted")
    learn.add_argument("--source", default="gemini", help="Mentor/source name")
    learn.add_argument("--memory-file", default=DEFAULT_MEMORY_FILE, help="JSONL memory file")

    memory = subparsers.add_parser("memory", help="Show recent mentor observations")
    memory.add_argument("--memory-file", default=DEFAULT_MEMORY_FILE, help="JSONL memory file")
    memory.add_argument("--limit", type=int, default=10, help="Maximum entries to show")

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.command == "wiki":
        client = WikipediaClient(language=args.lang)
        print_summary(client.summary(args.title))
        return 0

    if args.command == "search":
        client = WikipediaClient(language=args.lang)
        print_search_results(client.search(args.query, limit=args.limit))
        return 0

    if args.command == "learn":
        note = args.note if args.note is not None else sys.stdin.read()
        if not note.strip():
            print("No mentor note provided.", file=sys.stderr)
            return 2
        entry = learn_from_mentor(note, source=args.source, memory_file=args.memory_file)
        print(f"Stored mentor observation from {entry['source']} at {entry['timestamp']}")
        return 0

    if args.command == "memory":
        for entry in read_mentor_memory(memory_file=args.memory_file, limit=args.limit):
            print(f"[{entry['timestamp']}] {entry['source']}: {entry['note']}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
