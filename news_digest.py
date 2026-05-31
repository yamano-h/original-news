#!/usr/bin/env python3
"""Daily AI news digest: ClaudeCode / Codex / Gemini → Slack DM"""

import json
import os
import datetime
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

SENT_ARTICLES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sent_articles.json")
SLACK_CHANNEL = "DM6UXN0CC"
MAX_PER_TOPIC = 3

TOPICS = {
    "🤖 Claude Code": "Claude Code Anthropic",
    "💻 Codex":        "OpenAI Codex",
    "✨ Gemini":        "Google Gemini AI",
}


def load_sent_urls():
    try:
        with open(SENT_ARTICLES_FILE) as f:
            return set(json.load(f).get("sent_urls", []))
    except FileNotFoundError:
        return set()


def save_sent_urls(new_urls):
    existing = load_sent_urls()
    merged = list(existing | set(new_urls))
    with open(SENT_ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump({"sent_urls": merged}, f, indent=2, ensure_ascii=False)


def fetch_google_news(query, sent_urls, max_items=MAX_PER_TOPIC):
    encoded = urllib.parse.quote(query)
    url = (
        f"https://news.google.com/rss/search"
        f"?q={encoded}&hl=en&gl=US&ceid=US:en&tbs=qdr:d2"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw = resp.read()

    root = ET.fromstring(raw)
    articles = []
    for item in root.iter("item"):
        link = (item.findtext("link") or "").strip()
        title_raw = item.findtext("title") or ""
        title = title_raw.split(" - ")[0].strip()
        desc_raw = item.findtext("description") or ""

        if not link or link in sent_urls:
            continue

        articles.append({"title": title, "url": link, "desc": desc_raw[:120]})
        if len(articles) >= max_items:
            break

    return articles


def build_message(results):
    today = datetime.date.today().strftime("%Y-%m-%d")
    lines = [f"*📰 AI開発ツール ニュースダイジェスト — {today}*\n"]

    has_news = any(articles for articles in results.values())
    if not has_news:
        lines.append("本日の新着ニュースはありませんでした。")
    else:
        for topic, articles in results.items():
            if not articles:
                continue
            lines.append(f"---\n*{topic}*")
            for a in articles:
                lines.append(f"• *{a['title']}*")
                lines.append(f"  {a['url']}")
            lines.append("")

    lines.append("_このメッセージは自動配信です。_")
    return "\n".join(lines)


def slack_post(token, channel, text):
    payload = json.dumps({"channel": channel, "text": text, "mrkdwn": True}).encode()
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = json.loads(resp.read())
    if not body.get("ok"):
        raise RuntimeError(f"Slack error: {body.get('error')}")
    return body


def main():
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        raise SystemExit("ERROR: SLACK_BOT_TOKEN env var is not set")

    sent_urls = load_sent_urls()

    results = {}
    new_urls = []
    for topic, query in TOPICS.items():
        try:
            articles = fetch_google_news(query, sent_urls)
        except Exception as exc:
            print(f"[WARN] fetch failed for '{topic}': {exc}")
            articles = []
        results[topic] = articles
        new_urls.extend(a["url"] for a in articles)

    message = build_message(results)
    print(message)

    slack_post(token, SLACK_CHANNEL, message)
    print("✓ Sent to Slack")

    save_sent_urls(new_urls)
    print(f"✓ Updated sent_articles.json (+{len(new_urls)} URLs)")


if __name__ == "__main__":
    main()
