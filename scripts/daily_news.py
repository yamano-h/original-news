#!/usr/bin/env python3
"""
Daily AI news fetcher and Slack sender.
Searches for Claude Code / Codex / Gemini news and DMs Eugene on Slack.
Avoids re-sending already-sent articles by tracking sent_articles.json.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

SCRIPT_DIR = Path(__file__).parent.parent
SENT_FILE = SCRIPT_DIR / "sent_articles.json"
SLACK_CHANNEL = "DM6UXN0CC"
JST = timezone(timedelta(hours=9))
MAX_PER_TOPIC = 3

TOPICS = [
    ("🤖 Claude Code", "Claude Code Anthropic 2026"),
    ("💻 Codex",        "OpenAI Codex 2026"),
    ("✨ Gemini",       "Google Gemini 2026"),
]


def load_sent_urls() -> set:
    if not SENT_FILE.exists():
        return set()
    with open(SENT_FILE) as f:
        data = json.load(f)
    return set(data.get("sent_urls", []))


def save_sent_urls(urls: set) -> None:
    with open(SENT_FILE, "w") as f:
        json.dump({"sent_urls": sorted(urls)}, f, indent=2, ensure_ascii=False)
        f.write("\n")


def fetch_google_news(query: str) -> list[dict]:
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ja&gl=JP&ceid=JP:ja"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
    except Exception as e:
        print(f"[WARN] fetch failed for '{query}': {e}", file=sys.stderr)
        return []

    root = ET.fromstring(body)
    items = []
    for item in root.findall(".//item"):
        title_el = item.find("title")
        link_el  = item.find("link")
        desc_el  = item.find("description")
        if title_el is None or link_el is None:
            continue
        items.append({
            "title": (title_el.text or "").split(" - ")[0].strip(),
            "url":   (link_el.text or "").strip(),
            "desc":  (desc_el.text or "").strip() if desc_el is not None else "",
        })
    return items


def slack_send(token: str, channel: str, text: str) -> None:
    payload = json.dumps({"channel": channel, "text": text}).encode()
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=payload,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.load(resp)
    if not result.get("ok"):
        raise RuntimeError(f"Slack API error: {result.get('error')}")


def main() -> None:
    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    if not slack_token:
        print("[ERROR] SLACK_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    today = datetime.now(JST).strftime("%Y年%-m月%-d日")
    sent_urls = load_sent_urls()
    sections = []
    newly_sent: list[str] = []

    for label, query in TOPICS:
        articles = fetch_google_news(query)
        new_articles = [a for a in articles if a["url"] not in sent_urls][:MAX_PER_TOPIC]
        if not new_articles:
            sections.append(f"*{label}*\n本日の新着ニュースはありませんでした。")
            continue

        lines = [f"*{label}*"]
        for a in new_articles:
            lines.append(f"• *{a['title']}*\n  URL: {a['url']}")
            sent_urls.add(a["url"])
            newly_sent.append(a["url"])
        sections.append("\n".join(lines))

    message = f"📰 *AI開発ツール 最新ニュース* - {today}\n\n" + "\n\n".join(sections)
    slack_send(slack_token, SLACK_CHANNEL, message)
    print(f"[OK] Sent {len(newly_sent)} new article(s) to Slack.")

    if newly_sent:
        save_sent_urls(sent_urls)
        print(f"[OK] Updated {SENT_FILE}")


if __name__ == "__main__":
    main()
