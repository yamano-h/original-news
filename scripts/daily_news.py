#!/usr/bin/env python3
"""毎朝のAIニュース収集・Slack送信スクリプト"""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import anthropic
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

REPO_ROOT = Path(__file__).parent.parent
SENT_FILE = REPO_ROOT / "sent_articles.json"
SLACK_CHANNEL = "DM6UXN0CC"  # eugene


def load_sent_urls() -> set[str]:
    try:
        data = json.loads(SENT_FILE.read_text())
        return set(data.get("sent_urls", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_sent_urls(sent_urls: set[str]) -> None:
    SENT_FILE.write_text(
        json.dumps({"sent_urls": sorted(sent_urls)}, indent=2, ensure_ascii=False)
        + "\n"
    )


def fetch_news(sent_urls: set[str]) -> tuple[str, list[str]]:
    """Claude API + web_search でニュースを収集し、Slackメッセージと新規URLを返す"""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    today = date.today().strftime("%Y年%m月%d日")

    excluded = json.dumps(sorted(sent_urls), ensure_ascii=False, indent=2)
    prompt = f"""今日は{today}です。

ClaudeCode、OpenAI Codex、Google Geminiに関する**本日の最新ニュース**をWebで検索してまとめてください。

【除外URL（送信済みのため含めないこと）】
{excluded}

【出力形式】
以下のSlackメッセージをそのまま出力してください（他の説明文は不要）。
各カテゴリ最大3件、概要は1〜2文で簡潔に。
新着がない場合は「本日の新着ニュースはありませんでした」と書いてください。

---
📰 *AI開発ツール 最新ニュース* — {today}

*🤖 Claude Code*
• [記事タイトル]: [1〜2文の概要]
  URL: [記事URL]

*💻 Codex*
• [記事タイトル]: [1〜2文の概要]
  URL: [記事URL]

*✨ Gemini*
• [記事タイトル]: [1〜2文の概要]
  URL: [記事URL]
---

メッセージの末尾（区切り線の後）に、含めたURLをJSON配列で1行出力してください：
URLS_JSON:["https://...", ...]
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 9,
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )

    full_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            full_text += block.text

    # URLS_JSON行を抽出
    new_urls: list[str] = []
    match = re.search(r"URLS_JSON:(\[.*?\])", full_text, re.DOTALL)
    if match:
        try:
            new_urls = json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
        message = full_text[: match.start()].strip()
    else:
        message = full_text.strip()

    # 除外URLを念のためフィルタ
    new_urls = [u for u in new_urls if u not in sent_urls]

    return message, new_urls


def send_slack(message: str) -> None:
    slack = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    try:
        slack.chat_postMessage(channel=SLACK_CHANNEL, text=message)
        print("Slack DM sent successfully.")
    except SlackApiError as e:
        print(f"Slack error: {e.response['error']}", file=sys.stderr)
        raise


def main() -> None:
    sent_urls = load_sent_urls()
    print(f"Loaded {len(sent_urls)} already-sent URLs.")

    message, new_urls = fetch_news(sent_urls)
    print(f"Fetched message ({len(message)} chars), {len(new_urls)} new URLs.")

    if not message:
        print("Empty message, skipping.", file=sys.stderr)
        sys.exit(1)

    send_slack(message)

    sent_urls.update(new_urls)
    save_sent_urls(sent_urls)
    print(f"Updated {SENT_FILE} with {len(new_urls)} new URLs.")


if __name__ == "__main__":
    main()
