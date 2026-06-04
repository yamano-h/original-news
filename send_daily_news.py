#!/usr/bin/env python3
"""毎朝のAIニュース収集・Slack送信スクリプト"""

import json
import os
import sys
import re
from datetime import date

import anthropic
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

SENT_ARTICLES_FILE = os.path.join(os.path.dirname(__file__), "sent_articles.json")
SLACK_CHANNEL = "DM6UXN0CC"  # eugene


def load_sent_urls() -> set[str]:
    if not os.path.exists(SENT_ARTICLES_FILE):
        return set()
    with open(SENT_ARTICLES_FILE) as f:
        return set(json.load(f)["sent_urls"])


def save_sent_urls(new_urls: list[str]) -> None:
    if os.path.exists(SENT_ARTICLES_FILE):
        with open(SENT_ARTICLES_FILE) as f:
            data = json.load(f)
    else:
        data = {"sent_urls": []}

    existing = set(data["sent_urls"])
    for url in new_urls:
        if url not in existing:
            data["sent_urls"].append(url)
            existing.add(url)

    with open(SENT_ARTICLES_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def fetch_news(sent_urls: set[str]) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    today = date.today().isoformat()

    prompt = f"""今日は{today}です。

以下の3トピックについて、それぞれWeb検索で最新ニュースを調べてください:
1. "Claude Code latest news {today[:4]}"
2. "OpenAI Codex latest news {today[:4]}"
3. "Google Gemini latest news {today[:4]}"

各カテゴリ最大3件の記事を選んでください。
ただし、以下のURLは送信済みなので除外してください:
{json.dumps(sorted(sent_urls), ensure_ascii=False, indent=2)}

**必ず以下のJSON形式のみで回答してください（前後に説明文・マークダウン不要）:**
{{
  "claude_code": [
    {{"title": "記事タイトル", "url": "https://...", "summary": "1〜2文の日本語概要"}}
  ],
  "codex": [
    {{"title": "記事タイトル", "url": "https://...", "summary": "1〜2文の日本語概要"}}
  ],
  "gemini": [
    {{"title": "記事タイトル", "url": "https://...", "summary": "1〜2文の日本語概要"}}
  ]
}}"""

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 9}],
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract last text block from response
    result_text = ""
    for block in response.content:
        if hasattr(block, "text") and block.text.strip():
            result_text = block.text.strip()

    # Strip markdown code fences if present
    result_text = re.sub(r"^```(?:json)?\s*", "", result_text)
    result_text = re.sub(r"\s*```$", "", result_text)

    try:
        return json.loads(result_text)
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}\nRaw response:\n{result_text}", file=sys.stderr)
        return {"claude_code": [], "codex": [], "gemini": []}


def format_slack_message(articles: dict, today: str) -> str:
    lines = [f"🤖 *AI開発ツール 最新ニュース* ({today})", ""]

    sections = [
        ("claude_code", "🔷 Claude Code (Anthropic)"),
        ("codex", "🟢 Codex (OpenAI)"),
        ("gemini", "🔴 Gemini (Google)"),
    ]

    for key, header in sections:
        items = articles.get(key, [])
        lines.append(f"*{header}*")
        if items:
            for item in items:
                lines.append(f"• *{item['title']}*")
                lines.append(f"  {item['summary']}")
                lines.append(f"  🔗 {item['url']}")
        else:
            lines.append("  新着ニュースなし")
        lines.append("")

    lines.append("_このメッセージは自動送信です。重複記事は除外しています。_")
    return "\n".join(lines)


def send_slack_message(message: str) -> None:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise ValueError("SLACK_BOT_TOKEN environment variable is not set")

    client = WebClient(token=token)
    try:
        client.chat_postMessage(channel=SLACK_CHANNEL, text=message, mrkdwn=True)
        print(f"Slack DM sent to {SLACK_CHANNEL}")
    except SlackApiError as e:
        print(f"Slack error: {e.response['error']}", file=sys.stderr)
        raise


def main():
    today = date.today().isoformat()
    print(f"[{today}] Fetching AI news...")

    sent_urls = load_sent_urls()
    print(f"Already sent {len(sent_urls)} articles.")

    articles = fetch_news(sent_urls)

    new_urls = []
    total_articles = 0
    for key in ("claude_code", "codex", "gemini"):
        for item in articles.get(key, []):
            total_articles += 1
            if item["url"] not in sent_urls:
                new_urls.append(item["url"])

    print(f"Found {total_articles} articles ({len(new_urls)} new).")

    if total_articles == 0:
        message = f"🤖 *AI開発ツール 最新ニュース* ({today})\n\n本日の新着ニュースはありませんでした。"
    else:
        message = format_slack_message(articles, today)

    send_slack_message(message)
    save_sent_urls(new_urls)
    print("Done.")


if __name__ == "__main__":
    main()
