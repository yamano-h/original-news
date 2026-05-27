#!/usr/bin/env python3
"""Daily AI news collector: searches for ClaudeCode/Codex/Gemini news and sends to Slack."""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

SENT_ARTICLES_FILE = Path(__file__).parent.parent / "sent_articles.json"
SLACK_DM_CHANNEL = "DM6UXN0CC"

TOPICS = [
    ("Claude Code", "Claude Code Anthropic"),
    ("Codex", "OpenAI Codex"),
    ("Gemini", "Google Gemini AI"),
]


def load_sent_urls() -> set:
    if SENT_ARTICLES_FILE.exists():
        with open(SENT_ARTICLES_FILE) as f:
            return set(json.load(f).get("sent_urls", []))
    return set()


def save_sent_urls(urls: set) -> None:
    with open(SENT_ARTICLES_FILE, "w") as f:
        json.dump({"sent_urls": sorted(urls)}, f, indent=2, ensure_ascii=False)
        f.write("\n")


def search_news(client: anthropic.Anthropic, topic_name: str, search_query: str, sent_urls: set) -> list:
    today = datetime.now().strftime("%Y年%m月%d日")
    excluded = "\n".join(f"- {u}" for u in list(sent_urls)[:100])
    prompt = f"""今日は{today}です。
「{search_query}」に関する最新ニュースを過去数日以内の記事を中心に3件検索してください。

以下のURLはすでに送信済みなので必ず除外してください:
{excluded}

結果は以下のJSON配列のみで返してください（マークダウン不要）:
[
  {{
    "title": "記事タイトル（日本語）",
    "url": "https://...",
    "summary": "1〜2文の概要（日本語）"
  }}
]

新しい記事が見つからない場合は空配列 [] を返してください。"""

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    full_text = "\n".join(
        block.text for block in response.content if hasattr(block, "text")
    )

    match = re.search(r"\[.*?\]", full_text, re.DOTALL)
    if not match:
        return []

    try:
        articles = json.loads(match.group())
    except json.JSONDecodeError:
        return []

    return [a for a in articles if isinstance(a, dict) and a.get("url") not in sent_urls]


def build_message(results: list[tuple[str, list]]) -> str:
    today = datetime.now().strftime("%Y/%m/%d")
    lines = [f"*🤖 AI開発ツール 最新ニュース（{today}）*", ""]

    icons = {"Claude Code": "🔵", "Codex": "💻", "Gemini": "✨"}
    has_news = False

    for topic_name, articles in results:
        if not articles:
            continue
        has_news = True
        icon = icons.get(topic_name, "📌")
        lines.append(f"*【{topic_name}】*")
        for a in articles:
            lines.append(f"{icon} *{a['title']}*")
            lines.append(a["summary"])
            lines.append(f"🔗 {a['url']}")
            lines.append("")

    if not has_news:
        lines.append("本日の新着ニュースはありませんでした。")

    return "\n".join(lines)


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    slack_token = os.environ.get("SLACK_BOT_TOKEN")

    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY is not set", file=sys.stderr)
        sys.exit(1)
    if not slack_token:
        print("ERROR: SLACK_BOT_TOKEN is not set", file=sys.stderr)
        sys.exit(1)

    sent_urls = load_sent_urls()
    print(f"Loaded {len(sent_urls)} previously sent URLs")

    client = anthropic.Anthropic(api_key=api_key)
    results = []
    new_urls: set = set()

    for topic_name, search_query in TOPICS:
        print(f"Searching: {topic_name}...")
        articles = search_news(client, topic_name, search_query, sent_urls)
        print(f"  Found {len(articles)} new articles")
        results.append((topic_name, articles))
        for a in articles:
            if a.get("url"):
                new_urls.add(a["url"])

    message = build_message(results)
    print("\n--- Message preview ---")
    print(message)
    print("-----------------------\n")

    slack = WebClient(token=slack_token)
    try:
        slack.chat_postMessage(channel=SLACK_DM_CHANNEL, text=message)
        print("Slack DM sent successfully")
    except SlackApiError as e:
        print(f"ERROR: Slack API error: {e}", file=sys.stderr)
        sys.exit(1)

    if new_urls:
        updated = sent_urls | new_urls
        save_sent_urls(updated)
        print(f"Updated sent_articles.json (+{len(new_urls)} URLs, total={len(updated)})")
    else:
        print("No new URLs to record")


if __name__ == "__main__":
    main()
