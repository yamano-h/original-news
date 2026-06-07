#!/usr/bin/env python3
"""毎朝のAIニュース収集・Slack送信スクリプト"""

import json
import os
import re
import sys
from datetime import datetime
import anthropic
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

SENT_ARTICLES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sent_articles.json")
SLACK_USER_ID = "DM6UXN0CC"


def load_sent_urls():
    try:
        with open(SENT_ARTICLES_FILE) as f:
            return set(json.load(f).get("sent_urls", []))
    except FileNotFoundError:
        return set()


def save_sent_urls(urls):
    with open(SENT_ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump({"sent_urls": sorted(urls)}, f, indent=2, ensure_ascii=False)


def search_and_summarize(sent_urls):
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    today = datetime.now().strftime("%Y年%m月%d日")
    sent_list = "\n".join(sent_urls) if sent_urls else "(なし)"

    prompt = f"""今日は{today}です。

以下の3トピックについて最新ニュース記事をWeb検索してください。
各トピックで直近の記事を3件ずつ探してください：
1. Claude Code (Anthropic)
2. OpenAI Codex
3. Google Gemini

【重要】以下のURLはすでに送信済みなので除外してください：
{sent_list}

検索後、見つかった新規記事のみを以下のJSON形式で返してください（コードブロックやマークダウン不要、JSONのみ）:
{{
  "has_new_articles": true,
  "articles": {{
    "claude_code": [
      {{"title": "記事タイトル", "url": "記事の完全URL", "summary": "1〜2文の日本語概要"}}
    ],
    "codex": [
      {{"title": "記事タイトル", "url": "記事の完全URL", "summary": "1〜2文の日本語概要"}}
    ],
    "gemini": [
      {{"title": "記事タイトル", "url": "記事の完全URL", "summary": "1〜2文の日本語概要"}}
    ]
  }}
}}

新規記事が一件もない場合は has_new_articles を false にして articles を空にしてください。"""

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    for block in reversed(response.content):
        if hasattr(block, "text"):
            text = block.text.strip()
            # Strip markdown code fences if present
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                match = re.search(r"\{.*\}", text, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group())
                    except json.JSONDecodeError:
                        pass

    return {"has_new_articles": False, "articles": {}}


def build_slack_message(news, today):
    if not news.get("has_new_articles"):
        return f"📰 *AI開発ツール 最新ニュース* - {today}\n\n本日の新着ニュースはありませんでした。"

    articles = news.get("articles", {})
    lines = [f"📰 *AI開発ツール 最新ニュース* - {today}", "---"]

    sections = [
        ("claude_code", "*🤖 Claude Code*"),
        ("codex", "*💻 Codex (OpenAI)*"),
        ("gemini", "*✨ Gemini (Google)*"),
    ]
    for key, header in sections:
        items = articles.get(key, [])
        if not items:
            continue
        lines.append("")
        lines.append(header)
        for a in items:
            lines.append(f"\n• *{a['title']}*")
            lines.append(f"　{a['summary']}")
            lines.append(f"　{a['url']}")

    return "\n".join(lines)


def collect_new_urls(news, sent_urls):
    new_urls = []
    for items in news.get("articles", {}).values():
        for a in items:
            url = a.get("url", "")
            if url and url not in sent_urls:
                new_urls.append(url)
    return new_urls


def main():
    today = datetime.now().strftime("%Y年%m月%d日")
    sent_urls = load_sent_urls()
    print(f"送信済みURL数: {len(sent_urls)}", flush=True)

    print("ニュースを検索中...", flush=True)
    news = search_and_summarize(sent_urls)

    message = build_slack_message(news, today)

    slack = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    try:
        result = slack.chat_postMessage(channel=SLACK_USER_ID, text=message, mrkdwn=True)
        print(f"Slack送信成功: {result['ts']}", flush=True)
    except SlackApiError as e:
        print(f"Slack送信エラー: {e.response['error']}", file=sys.stderr)
        sys.exit(1)

    new_urls = collect_new_urls(news, sent_urls)
    sent_urls.update(new_urls)
    save_sent_urls(sent_urls)
    print(f"sent_articles.json を更新しました（新規: {len(new_urls)}件）", flush=True)


if __name__ == "__main__":
    main()
