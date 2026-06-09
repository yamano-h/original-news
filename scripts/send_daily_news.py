#!/usr/bin/env python3
"""Daily AI news collector and Slack DM sender."""

import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic
import requests

JST = timezone(timedelta(hours=9))
BASE_DIR = Path(__file__).parent.parent
SENT_ARTICLES_FILE = BASE_DIR / "sent_articles.json"
SLACK_DM_CHANNEL = "DM6UXN0CC"

TOPICS = [
    ("Claude Code", "🤖"),
    ("OpenAI Codex", "💻"),
    ("Google Gemini", "✨"),
]


def load_sent_urls() -> set:
    if SENT_ARTICLES_FILE.exists():
        data = json.loads(SENT_ARTICLES_FILE.read_text(encoding="utf-8"))
        return set(data.get("sent_urls", []))
    return set()


def save_sent_urls(urls: set) -> None:
    data = {"sent_urls": sorted(urls)}
    SENT_ARTICLES_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def parse_articles(text: str) -> list:
    """Extract JSON array of articles from Claude's response text."""
    text = text.strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return []


def search_news(client: anthropic.Anthropic, topic: str, today: str, sent_urls: set) -> list:
    """Search for news using Claude with web search tool."""
    excluded = json.dumps(list(sent_urls)[:30], ensure_ascii=False)
    prompt = f"""Today is {today}. Search the web for the latest news about "{topic}" published in the past 7 days.

Exclude these already-sent URLs:
{excluded}

Return ONLY a JSON array (no other text before or after):
[{{"title": "...", "url": "https://...", "summary": "1-2 sentence summary in Japanese"}}]

Find up to 3 new articles not in the excluded list. If none found, return: []"""

    messages = [{"role": "user", "content": prompt}]

    for _ in range(10):
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=2048,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text":
                    articles = parse_articles(block.text)
                    return [a for a in articles if a.get("url") and a["url"] not in sent_urls]
            return []

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = [
                {"type": "tool_result", "tool_use_id": b.id, "content": []}
                for b in response.content
                if b.type == "tool_use"
            ]
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
        else:
            break

    return []


def send_slack_dm(token: str, channel: str, text: str) -> bool:
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"channel": channel, "text": text, "mrkdwn": True},
        timeout=30,
    )
    result = resp.json()
    if not result.get("ok"):
        print(f"Slack error: {result.get('error')}", file=sys.stderr)
    return result.get("ok", False)


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    slack_token = os.environ.get("SLACK_BOT_TOKEN")

    if not api_key:
        sys.exit("Error: ANTHROPIC_API_KEY not set")
    if not slack_token:
        sys.exit("Error: SLACK_BOT_TOKEN not set")

    client = anthropic.Anthropic(api_key=api_key)
    today = datetime.now(JST).strftime("%Y-%m-%d")

    print(f"Collecting news for {today}...")
    sent_urls = load_sent_urls()
    print(f"Excluding {len(sent_urls)} previously sent URLs")

    new_urls = set()
    sections = []

    for topic, emoji in TOPICS:
        print(f"Searching: {topic}")
        articles = search_news(client, topic, today, sent_urls)[:3]
        if articles:
            lines = [f"*{emoji} {topic}*"]
            for a in articles:
                lines.append(f"• *{a.get('title', 'No title')}*")
                if a.get("summary"):
                    lines.append(f"  {a['summary']}")
                lines.append(f"  URL: {a['url']}")
                new_urls.add(a["url"])
            sections.append("\n".join(lines))
            print(f"  -> {len(articles)} new article(s)")
        else:
            print(f"  -> No new articles")

    if sections:
        message = f"📰 *AI開発ツール 最新ニュース* - {today}\n\n" + "\n\n".join(sections)
    else:
        message = f"📰 *AI開発ツール 最新ニュース* - {today}\n\n本日の新着ニュースはありませんでした。"

    print("Sending to Slack...")
    if send_slack_dm(slack_token, SLACK_DM_CHANNEL, message):
        print("Sent successfully")
        if new_urls:
            sent_urls.update(new_urls)
            save_sent_urls(sent_urls)
            print(f"Saved {len(new_urls)} new URL(s) to sent_articles.json")
    else:
        sys.exit("Failed to send Slack message")


if __name__ == "__main__":
    main()
