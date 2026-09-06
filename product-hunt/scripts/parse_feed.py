#!/usr/bin/env python3
"""Parse PH Atom feed file -> JSON lines. No votes/ranking; fresh featured posts only."""
import json
import re
import sys
import xml.etree.ElementTree as ET

ns = {"a": "http://www.w3.org/2005/Atom"}
root = ET.parse(sys.argv[1]).getroot()
for i, e in enumerate(root.findall("a:entry", ns), 1):
    tag = re.sub(r"<[^>]+>", "", e.find("a:content", ns).text).strip().splitlines()
    tag = tag[0].strip() if tag else ""
    print(json.dumps({
        "rank": i,
        "name": e.find("a:title", ns).text,
        "tagline": tag[:200],
        "votes": None, "comments": None,
        "url": e.find("a:link", ns).get("href"),
        "created": e.find("a:published", ns).text[:10],
        "source": "feed"}))
