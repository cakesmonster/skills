"""GitHub Trending scraper — single script, zero config. Outputs Markdown."""
import requests
from bs4 import BeautifulSoup

URL = "https://github.com/trending"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html",
}


def _parse_article(article):
    """Parse one <article> into a dict."""
    h2 = article.find("h2")
    if not h2:
        return None
    a_tag = h2.find("a")
    if not a_tag:
        return None
    href = (a_tag.get("href", "") or "").strip().lstrip("/")
    name = href  # e.g. "owner/repo"

    desc_p = article.find("p")
    desc = desc_p.get_text(strip=True) if desc_p else ""

    lang_span = article.find("span", itemprop="programmingLanguage")
    lang = lang_span.get_text(strip=True) if lang_span else ""

    # Total stars
    stars_el = article.find("a", href=lambda h: h and "/stargazers" in h)
    total_stars = ""
    if stars_el:
        total_stars = stars_el.get_text(strip=True).replace(",", "")

    # Stars today/this period
    today_el = article.find("span", class_="d-inline-block float-sm-right")
    stars_today = ""
    if today_el:
        text = today_el.get_text(strip=True)
        import re
        m = re.search(r"([\d,]+)\s+stars?", text)
        if m:
            stars_today = m.group(1).replace(",", "")

    # Forks
    fork_el = article.find("a", href=lambda h: h and "/forks" in h)
    forks = ""
    if fork_el:
        forks = fork_el.get_text(strip=True).replace(",", "")

    return {
        "name": name,
        "url": f"https://github.com/{name}",
        "description": desc,
        "language": lang,
        "stars": total_stars,
        "stars_today": stars_today,
        "forks": forks,
    }


def scrape(period="daily"):
    """Scrape trending page. period: daily | weekly | monthly."""
    resp = requests.get(f"{URL}?since={period}", headers=HEADERS, timeout=120)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    articles = soup.find_all("article", class_="Box-row")
    repos = []
    for art in articles:
        r = _parse_article(art)
        if r and r["name"]:
            repos.append(r)
    return repos


PERIOD_LABELS = {"daily": "今日", "weekly": "本周", "monthly": "本月"}


def fmt_markdown(period, repos, limit=10):
    label = PERIOD_LABELS.get(period, period)
    out = [f"## 🔥 GitHub Trending {label}  TOP {min(limit, len(repos))}\n"]
    emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, r in enumerate(repos[:limit]):
        e = emoji[i] if i < len(emoji) else f"{i+1}."
        lang = f" ({r['language']})" if r["language"] else ""
        stars_info = f"⭐{r['stars']}"
        if r["stars_today"]:
            stars_info = f"+{r['stars_today']} {stars_info}"
        out.append(f"{e} **[{r['name']}]({r['url']})**{lang} {stars_info}")
        if r["description"]:
            desc = r["description"]
            if len(desc) > 120:
                desc = desc[:117] + "..."
            out.append(f"   {desc}")
        out.append("")
    out.append(f"📡 数据: {URL}?since={period}")
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    period = sys.argv[1] if len(sys.argv) > 1 else "daily"
    repos = scrape(period)
    print(fmt_markdown(period, repos))
