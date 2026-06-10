#!/usr/bin/env python3
"""Daily AI news collection and Slack DM script."""

import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import anthropic
from slack_sdk import WebClient

SCRIPT_DIR = Path(__file__).parent
SENT_ARTICLES_FILE = SCRIPT_DIR / "sent_articles.json"
SLACK_DM_CHANNEL = "DM6UXN0CC"
JST = timezone(timedelta(hours=9))


def load_sent_urls() -> set:
    if SENT_ARTICLES_FILE.exists():
        data = json.loads(SENT_ARTICLES_FILE.read_text())
        return set(data.get("sent_urls", []))
    return set()


def save_sent_urls(urls: set) -> None:
    data = {"sent_urls": sorted(urls)}
    SENT_ARTICLES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def search_and_summarize_news(sent_urls: set, today: str) -> dict:
    """Use Claude with web search to find and summarize latest AI tool news."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    year = today[:4]

    prompt = f"""Today is {today}. Search for the latest news (past week) about these three topics and return a JSON summary.

Search queries:
1. "Claude Code Anthropic latest news {year}"
2. "OpenAI Codex latest news {year}"
3. "Google Gemini latest news {year}"

Already-sent URLs to EXCLUDE: {json.dumps(sorted(sent_urls))}

Return ONLY valid JSON — no markdown fences, no explanation, just the object:
{{
  "claude_code": [
    {{"title": "Article title", "url": "https://...", "summary": "日本語の要約（1〜2文）"}}
  ],
  "codex": [...],
  "gemini": [...]
}}

Up to 3 articles per topic. Use [] if no new articles found for a topic."""

    messages = [{"role": "user", "content": prompt}]

    # Agentic loop to handle tool_use stop_reason
    for _ in range(10):
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    match = re.search(r"\{[\s\S]*\}", block.text)
                    if match:
                        try:
                            return json.loads(match.group())
                        except json.JSONDecodeError:
                            pass
            return {"claude_code": [], "codex": [], "gemini": []}

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = [
                {"type": "tool_result", "tool_use_id": block.id, "content": ""}
                for block in response.content
                if block.type == "tool_use"
            ]
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
        else:
            break

    return {"claude_code": [], "codex": [], "gemini": []}


def build_slack_message(news: dict, today: str) -> tuple:
    sections = []
    new_urls = []

    for key, label in [("claude_code", "🤖 Claude Code"), ("codex", "💻 Codex"), ("gemini", "✨ Gemini")]:
        articles = news.get(key, [])[:3]
        if articles:
            lines = [f"*{label}*"]
            for art in articles:
                lines.append(f"• *{art['title']}* — {art['summary']}")
                lines.append(f"  URL: {art['url']}")
                new_urls.append(art["url"])
            sections.append("\n".join(lines))

    header = f"📰 *AI開発ツール 最新ニュース* - {today}"
    body = "\n\n".join(sections) if sections else "本日の新着ニュースはありませんでした。"
    return header + "\n\n" + body, new_urls


def main():
    today = datetime.now(JST).strftime("%Y-%m-%d")
    sent_urls = load_sent_urls()

    print(f"[{today}] Searching for news (excluding {len(sent_urls)} sent URLs)...")
    news = search_and_summarize_news(sent_urls, today)
    message, new_urls = build_slack_message(news, today)

    slack = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    slack.chat_postMessage(channel=SLACK_DM_CHANNEL, text=message)
    print(f"Sent Slack DM to {SLACK_DM_CHANNEL}")

    if new_urls:
        sent_urls.update(new_urls)
        save_sent_urls(sent_urls)
        print(f"Updated sent_articles.json with {len(new_urls)} new URLs")
    else:
        print("No new articles found; sent_articles.json unchanged")


if __name__ == "__main__":
    main()
