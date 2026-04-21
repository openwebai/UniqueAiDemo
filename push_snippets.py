"""
Push the demo scripts to docs.openweb.ai as snippets.

Usage:
    export NXDOCS_API_KEY=nxdocs_sk_...
    python push_snippets.py
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://docs.openweb.ai/api/docs"
CATEGORY = "unique-sdk-demo"

SNIPPETS = [
    {
        "file": "01_search_and_chat.py",
        "title": "Unique SDK — Search & Chat Completion",
        "description": "Standalone script: search the knowledge base and call the LLM proxy.",
    },
    {
        "file": "02_webhook_server.py",
        "title": "Unique SDK — Webhook Server",
        "description": "Flask server that handles Unique platform webhooks for external modules.",
    },
    {
        "file": "03_space_api.py",
        "title": "Unique SDK — Space API",
        "description": "Interact with a pre-configured space: chats, messages, document upload.",
    },
]


def push(api_key: str, title: str, content: str, description: str) -> dict:
    body = json.dumps(
        {
            "title": title,
            "content": content,
            "language": "python",
            "category": CATEGORY,
            "description": description,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def main() -> int:
    api_key = os.environ.get("NXDOCS_API_KEY")
    if not api_key:
        print("Error: set NXDOCS_API_KEY", file=sys.stderr)
        return 1

    repo_root = Path(__file__).parent
    failures = 0

    for snippet in SNIPPETS:
        path = repo_root / snippet["file"]
        content = path.read_text()
        try:
            result = push(api_key, snippet["title"], content, snippet["description"])
        except urllib.error.HTTPError as e:
            print(f"FAIL {snippet['file']}: HTTP {e.code} {e.read().decode(errors='replace')}")
            failures += 1
            continue
        url = result.get("url") or result.get("data", {}).get("url") or result
        print(f"OK   {snippet['file']} -> {url}")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
