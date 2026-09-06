#!/usr/bin/env python3
"""Build PH GraphQL posts query. Reads env: PH_AFTER, PH_NOW, PH_TOPIC. Prints JSON body."""
import json
import os

# common shortforms -> valid PH topic slugs (invalid slugs return 0 results silently!)
TOPIC_MAP = {
    "ai": "artificial-intelligence",
    "dev-tools": "developer-tools",
    "agents": "ai-agents",
    "productivity": "productivity",
    "design": "design-tools",
    "marketing": "marketing",
    "saas": "saas",
    "open-source": "open-source",
}

after = os.environ["PH_AFTER"]
now = os.environ["PH_NOW"]
topic = os.environ.get("PH_TOPIC", "")
topic = TOPIC_MAP.get(topic, topic)
args = []
if topic:
    args.append(f'topic: "{topic}"')
args += [f"order: VOTES", f"postedAfter: \"{after}\"", f"postedBefore: \"{now}\"", "first: 20"]
q = ("{ posts(" + ", ".join(args) + ") { edges { node { name tagline votesCount "
     "commentsCount createdAt url website topics(first: 3) { edges { node { name } } } } } } }")
print(json.dumps({"query": q}))
