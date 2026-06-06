#!/usr/bin/env python3
"""
毎朝のAIニュース収集・Slack送信スクリプト
ClaudeCode / OpenAI Codex / Google Gemini の最新ニュースをSlack DMに送信する
"""

import json
import os
import re
import sys
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

SENT_ARTICLES_PATH = Path(__file__).parent.parent / "sent_articles.json"
SLACK_CHANNEL_ID = "DM6UXN0CC"  # eugene のDM

SEARCH_QUERIES = [
    ("ClaudeCode", "Claude Code Anthropic"),
    ("Codex", "OpenAI Codex"),
    ("Gemini", "Google Gemini AI"),
]


def load_sent_urls() -> set:
    if SENT_ARTICLES_PATH.exists():
        data = json.loads(SENT_ARTICLES_PATH.read_text())
        return set(data.get("sent_urls", []))
    return set()


def save_sent_urls(urls: set):
    data = {"sent_urls": sorted(urls)}
    SENT_ARTICLES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def fetch_google_news(query: str) -> list[dict]:
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        items = []
        for item in root.findall(".//item")[:10]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "").strip()
            # Google News リンクを実URLに変換
            if "news.google.com" in link:
                # リダイレクト先URLを取得
                try:
                    req2 = urllib.request.Request(
                        link, headers={"User-Agent": "Mozilla/5.0"}
                    )
                    req2.method = "HEAD"
                    with urllib.request.urlopen(req2, timeout=5) as r:
                        final_url = r.url
                    link = final_url
                except Exception:
                    pass
            items.append({"title": title, "url": link, "pub_date": pub_date})
        return items
    except Exception as e:
        print(f"Warning: RSS fetch failed for '{query}': {e}", file=sys.stderr)
        return []


def summarize_with_claude(articles_by_category: dict) -> str:
    """Claude APIで記事を要約してSlack用メッセージを生成する"""
    import anthropic

    client = anthropic.Anthropic()
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y/%m/%d")

    articles_text = ""
    for category, articles in articles_by_category.items():
        articles_text += f"\n## {category}\n"
        for a in articles:
            articles_text += f"- タイトル: {a['title']}\n  URL: {a['url']}\n"

    if not articles_text.strip():
        return f"🤖 *AI開発ツール 最新ニュースまとめ* — {today}\n\n本日の新着ニュースはありませんでした。"

    prompt = f"""以下の記事一覧をもとに、Slack向けの日本語ニュースまとめメッセージを作成してください。

# 記事一覧
{articles_text}

# 出力形式
- 各カテゴリ最大3件
- 各記事は1〜2文の概要 + URLを含める
- Slackのマークダウン形式（*太字*、箇条書き•）を使用
- ヘッダー行: 🤖 *AI開発ツール 最新ニュースまとめ* — {today}
- カテゴリヘッダー: *🔷 Claude Code*、*🟢 OpenAI Codex*、*🔴 Google Gemini*

記事URLはそのまま含めてください（短縮しない）。"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def send_slack_message(text: str):
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise RuntimeError("SLACK_BOT_TOKEN が設定されていません")
    payload = json.dumps({"channel": SLACK_CHANNEL_ID, "text": text}).encode()
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        result = json.loads(resp.read())
    if not result.get("ok"):
        raise RuntimeError(f"Slack送信エラー: {result.get('error')}")
    print(f"Slack送信成功: {result.get('ts')}")


def main():
    sent_urls = load_sent_urls()
    new_articles: dict[str, list] = {}
    all_new_urls: set = set()

    for category, query in SEARCH_QUERIES:
        articles = fetch_google_news(query)
        fresh = [a for a in articles if a["url"] not in sent_urls][:3]
        if fresh:
            new_articles[category] = fresh
            all_new_urls.update(a["url"] for a in fresh)

    message = summarize_with_claude(new_articles)
    send_slack_message(message)

    if all_new_urls:
        save_sent_urls(sent_urls | all_new_urls)
        print(f"{len(all_new_urls)} 件の新規URLを sent_articles.json に追記しました")


if __name__ == "__main__":
    main()
