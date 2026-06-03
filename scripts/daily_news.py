#!/usr/bin/env python3
"""Daily AI news collector and Slack sender.

Searches for latest Claude Code / Codex / Gemini news via Claude's web search,
skips already-sent articles, and posts a summary DM to Slack.

Required env vars:
  ANTHROPIC_API_KEY  - Anthropic API key
  SLACK_BOT_TOKEN    - Slack Bot OAuth token (xoxb-...)
"""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import anthropic
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

REPO_DIR = Path(__file__).parent.parent
SENT_ARTICLES_FILE = REPO_DIR / "sent_articles.json"
SLACK_CHANNEL = "DM6UXN0CC"  # eugene's DM channel ID
TODAY = date.today().isoformat()

TOPICS = [
    ("🤖 Claude Code", "Claude Code by Anthropic agentic coding tool"),
    ("💻 Codex",       "OpenAI Codex coding assistant"),
    ("✨ Gemini",      "Google Gemini AI model"),
]


def load_sent_urls() -> set[str]:
    try:
        data = json.loads(SENT_ARTICLES_FILE.read_text(encoding="utf-8"))
        return set(data.get("sent_urls", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_sent_urls(new_urls: list[str]) -> None:
    existing = load_sent_urls()
    all_urls = sorted(existing | set(new_urls))
    SENT_ARTICLES_FILE.write_text(
        json.dumps({"sent_urls": all_urls}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def search_news(
    client: anthropic.Anthropic, topic: str, sent_urls: set[str]
) -> list[dict]:
    """Return up to 3 new articles about `topic`, excluding already-sent URLs."""
    sent_list = "\n".join(f"- {u}" for u in sorted(sent_urls)) or "(none)"

    prompt = f"""Today is {TODAY}. Use web search to find the latest news about "{topic}" published in the past 7 days.

Find up to 3 recent, noteworthy articles. Do NOT include any article whose URL appears in this already-sent list:
{sent_list}

Respond with ONLY a JSON array (no markdown fences). Each element must have:
  "title"   - article title in its original language
  "url"     - direct article URL (not a redirect)
  "summary" - 1-2 sentence summary in Japanese

Example:
[{{"title": "...", "url": "https://...", "summary": "..."}}]

If there are no new articles, respond with exactly: []"""

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2048,
        tools=[{"type": "web_search_20250305"}],
        messages=[{"role": "user", "content": prompt}],
    )

    for block in reversed(response.content):
        if block.type == "text":
            m = re.search(r"\[.*?\]", block.text, re.DOTALL)
            if m:
                try:
                    articles = json.loads(m.group())
                    return [a for a in articles if a.get("url") not in sent_urls]
                except (json.JSONDecodeError, AttributeError):
                    pass
    return []


def build_message(sections: list[tuple[str, list[dict]]]) -> str:
    lines = [f"📰 *AI開発ツール 最新ニュース* - {TODAY}", ""]
    for label, articles in sections:
        lines.append(f"*{label}*")
        if articles:
            for a in articles:
                lines.append(f"• {a['summary']}")
                lines.append(f"  URL: {a['url']}")
        else:
            lines.append("• 本日の新着記事はありませんでした")
        lines.append("")
    return "\n".join(lines).rstrip()


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    slack_token = os.environ.get("SLACK_BOT_TOKEN")

    if not api_key:
        sys.exit("ERROR: ANTHROPIC_API_KEY is not set")
    if not slack_token:
        sys.exit("ERROR: SLACK_BOT_TOKEN is not set")

    client = anthropic.Anthropic(api_key=api_key)
    sent_urls = load_sent_urls()
    print(f"Loaded {len(sent_urls)} already-sent URLs")

    sections: list[tuple[str, list[dict]]] = []
    all_new_urls: list[str] = []

    for label, topic in TOPICS:
        print(f"Searching: {topic} ...")
        articles = search_news(client, topic, sent_urls)
        print(f"  → {len(articles)} new article(s)")
        sections.append((label, articles))
        all_new_urls.extend(a["url"] for a in articles)

    message = build_message(sections)

    slack_client = WebClient(token=slack_token)
    try:
        result = slack_client.chat_postMessage(channel=SLACK_CHANNEL, text=message)
        print(f"Slack DM sent (ts={result['ts']})")
    except SlackApiError as e:
        sys.exit(f"Slack error: {e}")

    if all_new_urls:
        save_sent_urls(all_new_urls)
        print(f"Updated sent_articles.json (+{len(all_new_urls)} URLs)")
    else:
        print("No new articles found; sent_articles.json unchanged")


if __name__ == "__main__":
    main()
