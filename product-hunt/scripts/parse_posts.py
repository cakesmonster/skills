#!/usr/bin/env python3
"""Parse PH GraphQL posts response (stdin) -> JSON lines {rank,name,tagline,votes,...}."""
import json
import sys

d = json.load(sys.stdin)
if "errors" in d:
    print("ERROR:", json.dumps(d["errors"])[:300], file=sys.stderr)
    sys.exit(1)
edges = d["data"]["posts"]["edges"]
for i, e in enumerate(edges, 1):
    n = e["node"]
    print(json.dumps({
        "rank": i, "name": n["name"], "tagline": n.get("tagline", ""),
        "votes": n.get("votesCount"), "comments": n.get("commentsCount"),
        "url": n.get("url"), "created": (n.get("createdAt") or "")[:10],
        "topics": [t["node"]["name"] for t in n.get("topics", {}).get("edges", [])],
        "source": "api"}))
