#!/usr/bin/env python3
"""Daily AI news fetcher and Slack DM sender."""

import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import feedparser
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

SENT_ARTICLES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sent_articles.json")
SLACK_USER_ID = "DM6UXN0CC"
MAX_ARTICLES_PER_CATEGORY = 3
DAYS_LOOKBACK = 3

# Google News RSS — no API key required
SEARCH_FEEDS = {
    "Claude Code": [
        'https://news.google.com/rss/search?q="Claude+Code"+Anthropic&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q="Claude+Code"+AI+coding&hl=en-US&gl=US&ceid=US:en',
    ],
    "Codex": [
        'https://news.google.com/rss/search?q=OpenAI+Codex&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q="Codex+CLI"+OpenAI&hl=en-US&gl=US&ceid=US:en',
    ],
    "Gemini": [
        'https://news.google.com/rss/search?q=Google+Gemini+AI&hl=en-US&gl=US&ceid=US:en',
        'https://news.google.com/rss/search?q="Gemini+2"+Google&hl=en-US&gl=US&ceid=US:en',
    ],
}

JST = timezone(timedelta(hours=9))


def load_sent_urls():
    try:
        with open(SENT_ARTICLES_FILE) as f:
            return set(json.load(f).get("sent_urls", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_sent_urls(sent_urls):
    with open(SENT_ARTICLES_FILE, "w") as f:
        json.dump({"sent_urls": sorted(sent_urls)}, f, indent=2, ensure_ascii=False)


def clean_html(text):
    text = re.sub(r"<[^>]+>", "", text or "")
    return html.unescape(text).strip()


def fetch_articles(feed_urls, sent_urls, cutoff_date):
    articles = []
    seen_urls = set()

    for feed_url in feed_urls:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                url = (entry.get("link") or "").strip()
                title = clean_html(entry.get("title") or "")
                summary = clean_html(entry.get("summary") or entry.get("description") or "")

                if not url or not title:
                    continue
                if url in sent_urls or url in seen_urls:
                    continue

                published = entry.get("published_parsed")
                if published:
                    pub_date = datetime(*published[:6], tzinfo=timezone.utc)
                    if pub_date < cutoff_date:
                        continue

                # Truncate long summaries to ~100 chars
                if len(summary) > 100:
                    summary = summary[:97] + "..."

                seen_urls.add(url)
                articles.append({"title": title, "url": url, "summary": summary, "published": published})

            time.sleep(0.5)
        except Exception as e:
            print(f"Warning: failed to fetch {feed_url}: {e}", file=sys.stderr)

    articles.sort(key=lambda x: x.get("published") or (2000, 1, 1, 0, 0, 0), reverse=True)
    return articles[:MAX_ARTICLES_PER_CATEGORY]


def format_message(news_by_category, today):
    date_str = today.astimezone(JST).strftime("%Y年%m月%d日")
    lines = [f"📰 *AI開発ツール 最新ニュース* - {date_str}\n"]

    icons = {"Claude Code": "🤖", "Codex": "💻", "Gemini": "✨"}
    all_urls = []

    total = sum(len(v) for v in news_by_category.values())
    if total == 0:
        lines.append("本日の新着ニュースはありませんでした。")
        return "\n".join(lines), []

    for category, articles in news_by_category.items():
        if not articles:
            continue
        icon = icons.get(category, "📌")
        lines.append(f"*{icon} {category}*")
        for article in articles:
            lines.append(f"• *{article['title']}*")
            if article["summary"]:
                lines.append(f"  {article['summary']}")
            lines.append(f"  <{article['url']}|記事を読む>")
            all_urls.append(article["url"])
        lines.append("")

    return "\n".join(lines).rstrip(), all_urls


def main():
    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    if not slack_token:
        print("Error: SLACK_BOT_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    today = datetime.now(timezone.utc)
    cutoff_date = today - timedelta(days=DAYS_LOOKBACK)

    print(f"Fetching news since {cutoff_date.strftime('%Y-%m-%d')} ...")
    sent_urls = load_sent_urls()

    news_by_category = {}
    for category, feed_urls in SEARCH_FEEDS.items():
        print(f"  [{category}]")
        articles = fetch_articles(feed_urls, sent_urls, cutoff_date)
        news_by_category[category] = articles
        print(f"    {len(articles)} new article(s) found")

    message, new_urls = format_message(news_by_category, today)

    print(f"\nSending Slack DM to {SLACK_USER_ID} ...")
    client = WebClient(token=slack_token)
    try:
        response = client.chat_postMessage(channel=SLACK_USER_ID, text=message, mrkdwn=True)
        print(f"Sent. ts={response['ts']}")
    except SlackApiError as e:
        print(f"Slack error: {e.response['error']}", file=sys.stderr)
        sys.exit(1)

    sent_urls.update(new_urls)
    save_sent_urls(sent_urls)
    print(f"Updated sent_articles.json (+{len(new_urls)} URLs)")


if __name__ == "__main__":
    main()
