#!/usr/bin/env python3
"""Daily AI news digest: ClaudeCode, Codex, Gemini -> Slack DM to Eugene"""
import anthropic
import json
import os
import re
import requests
from datetime import date
from pathlib import Path

HISTORY_FILE = Path(__file__).parent.parent / "sent_articles.json"
SLACK_CHANNEL = "DM6UXN0CC"  # Eugene's DM channel ID


def load_history() -> list:
    if HISTORY_FILE.exists():
        data = json.loads(HISTORY_FILE.read_text())
        return data.get("sent_urls", [])
    return []


def save_history(new_urls: list):
    existing = load_history()
    all_urls = list(dict.fromkeys(existing + new_urls))[-500:]
    HISTORY_FILE.write_text(json.dumps({"sent_urls": all_urls}, indent=2, ensure_ascii=False) + "\n")


def fetch_news(sent_urls: list) -> list:
    client = anthropic.Anthropic()
    today = date.today().isoformat()
    sent_sample = sent_urls[-30:]

    prompt = f"""今日は{today}です。以下の3つのトピックについて過去1週間の最新ニュースを検索してください：
1. Claude Code（AnthropicのAIコーディングツール）
2. OpenAI Codex（OpenAIのコーディングエージェント）
3. Google Gemini（GoogleのAIモデル）

各トピックにつき2〜3件の新しい記事を見つけてください。
以下のURLは既に送信済みなので除外してください: {json.dumps(sent_sample, ensure_ascii=False)}

以下のJSON形式のみで回答してください（説明文・マークダウン記法は不要）：
[
  {{"topic": "Claude Code", "title": "記事タイトル", "summary": "2〜3文の要約（日本語）", "url": "https://..."}},
  ...
]
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if hasattr(block, "type") and block.type == "text":
            match = re.search(r"\[.*\]", block.text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
    return []


def build_message(items: list) -> str:
    today_str = date.today().strftime("%Y年%m月%d日")
    lines = [f"*🤖 AI開発ツール 最新ニュースまとめ｜{today_str}*\n"]

    topic_emoji = {"Claude Code": "📌", "OpenAI Codex": "💻", "Google Gemini": "✨"}
    current_topic = None
    for item in items:
        topic = item.get("topic", "")
        if topic != current_topic:
            current_topic = topic
            emoji = topic_emoji.get(topic, "📌")
            lines.append(f"\n*{emoji} {topic}*")
        lines.append(f"• *{item['title']}*")
        lines.append(f"  {item['summary']}")
        lines.append(f"  <{item['url']}|記事を読む>")

    lines.append("\n---\n_このメッセージは自動送信です。毎朝8時（JST）に最新ニュースをお届けします。_")
    return "\n".join(lines)


def send_slack(message: str):
    token = os.environ["SLACK_BOT_TOKEN"]
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"channel": SLACK_CHANNEL, "text": message, "mrkdwn": True},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    if not result.get("ok"):
        raise RuntimeError(f"Slack API error: {result.get('error')}")
    print(f"Message sent: ts={result.get('ts')}")


def main():
    today = date.today()
    print(f"Starting daily news digest for {today}")

    history = load_history()
    print(f"Loaded {len(history)} previously sent URLs")

    items = fetch_news(history)
    print(f"Found {len(items)} articles from search")

    if not items:
        today_str = today.strftime("%Y年%m月%d日")
        send_slack(f"*🤖 AI開発ツール 最新ニュース｜{today_str}*\n\n本日の新着ニュースはありませんでした。")
        print("No articles found, sent notice.")
        return

    new_items = [i for i in items if i.get("url") not in history]
    if not new_items:
        print("All found articles already sent. Skipping.")
        return

    send_slack(build_message(new_items))

    new_urls = [i["url"] for i in new_items]
    save_history(new_urls)
    print(f"Sent {len(new_items)} articles, history updated with {len(new_urls)} URLs")


if __name__ == "__main__":
    main()
