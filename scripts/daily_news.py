#!/usr/bin/env python3
"""毎朝 ClaudeCode/Codex/Gemini の最新ニュースを収集し Eugene の Slack DM へ送信する。"""

import json
import os
import sys
from datetime import date, datetime

SENT_ARTICLES_FILE = os.path.join(os.path.dirname(__file__), "..", "sent_articles.json")
SLACK_CHANNEL = "DM6UXN0CC"  # Eugene の DM チャンネル ID

CATEGORIES = {
    "🤖 Claude Code": ["Claude Code site:anthropic.com OR site:github.com/anthropics", "Claude Code CLI news"],
    "💻 Codex": ["OpenAI Codex news", "OpenAI Codex agent"],
    "✨ Gemini": ["Google Gemini AI news", "Gemini 2.0 OR Gemini 2.5"],
}


def load_sent_urls() -> set:
    if not os.path.exists(SENT_ARTICLES_FILE):
        return set()
    with open(SENT_ARTICLES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("sent_urls", []))


def save_sent_urls(sent_urls: set) -> None:
    with open(SENT_ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump({"sent_urls": sorted(sent_urls)}, f, ensure_ascii=False, indent=2)


def search_news(queries: list[str], max_per_query: int = 5) -> list[dict]:
    from duckduckgo_search import DDGS

    results = []
    seen_urls = set()
    with DDGS() as ddgs:
        for query in queries:
            try:
                hits = ddgs.news(query, max_results=max_per_query, timelimit="w")
                for h in hits:
                    url = h.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        results.append(h)
            except Exception as e:
                print(f"[WARN] Search failed for '{query}': {e}", file=sys.stderr)
    return results


def build_slack_message(articles_by_category: dict, today_str: str) -> str:
    lines = [f"📰 *AI開発ツール 最新ニュース* - {today_str}", ""]

    has_any = any(arts for arts in articles_by_category.values())
    if not has_any:
        lines.append("本日の新着ニュースはありませんでした。")
        return "\n".join(lines)

    for category, articles in articles_by_category.items():
        if not articles:
            continue
        lines.append(f"*{category}*")
        for art in articles:
            title = art.get("title", "（タイトルなし）")
            url = art.get("url", "")
            body = art.get("body", "")
            summary = body[:120].rstrip() + ("…" if len(body) > 120 else "")
            lines.append(f"• {title}")
            if summary:
                lines.append(f"  {summary}")
            lines.append(f"  URL: {url}")
        lines.append("")

    return "\n".join(lines).rstrip()


def send_slack_message(token: str, channel: str, text: str) -> None:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError

    client = WebClient(token=token)
    try:
        client.chat_postMessage(channel=channel, text=text, mrkdwn=True)
        print("[OK] Slack message sent.")
    except SlackApiError as e:
        print(f"[ERROR] Slack API error: {e.response['error']}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    slack_token = os.environ.get("SLACK_BOT_TOKEN")
    if not slack_token:
        print("[ERROR] SLACK_BOT_TOKEN is not set.", file=sys.stderr)
        sys.exit(1)

    today_str = date.today().strftime("%Y年%m月%d日")
    print(f"[{datetime.now().isoformat()}] Starting daily news task for {today_str}")

    sent_urls = load_sent_urls()
    articles_by_category: dict = {}
    all_new_urls: list[str] = []

    for category, queries in CATEGORIES.items():
        results = search_news(queries)
        new_articles = [r for r in results if r.get("url", "") not in sent_urls][:3]
        articles_by_category[category] = new_articles
        all_new_urls.extend(r["url"] for r in new_articles if r.get("url"))
        print(f"  {category}: {len(new_articles)} 件の新着記事")

    message = build_slack_message(articles_by_category, today_str)
    print("\n--- Slack message preview ---")
    print(message)
    print("---")

    send_slack_message(slack_token, SLACK_CHANNEL, message)

    sent_urls.update(all_new_urls)
    save_sent_urls(sent_urls)
    print(f"[OK] sent_articles.json を更新しました（合計 {len(sent_urls)} 件）")


if __name__ == "__main__":
    main()
