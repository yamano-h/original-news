#!/usr/bin/env python3
"""Daily AI news collection and Slack DM notification."""

import json
import os
from datetime import date

import anthropic
from slack_sdk import WebClient

SENT_ARTICLES_FILE = os.path.join(os.path.dirname(__file__), "sent_articles.json")
SLACK_USER_ID = os.environ.get("SLACK_USER_ID", "DM6UXN0CC")
TODAY = date.today().strftime("%Y-%m-%d")
YEAR = date.today().year


def load_sent_urls():
    with open(SENT_ARTICLES_FILE) as f:
        return set(json.load(f)["sent_urls"])


def save_sent_urls(sent_urls):
    with open(SENT_ARTICLES_FILE, "w") as f:
        json.dump({"sent_urls": sorted(sent_urls)}, f, indent=2, ensure_ascii=False)
        f.write("\n")


def collect_and_format_news(sent_urls: set) -> tuple[str, list[str]]:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    sent_list = "\n".join(f"- {u}" for u in sorted(sent_urls))
    prompt = f"""今日（{TODAY}）のClaudeCode・Codex・Geminiの最新ニュースを収集し、Slack用メッセージを作成してください。

以下のURLはすでに送信済みです。これらは**必ず除外**してください:
{sent_list}

手順:
1. 以下の3つのキーワードでそれぞれWeb検索してください:
   - "Claude Code latest news {YEAR}"
   - "OpenAI Codex latest news {YEAR}"
   - "Google Gemini latest news {YEAR}"

2. 送信済みURLと重複しない新しい記事を各カテゴリ最大3件選んでください。

3. 以下の形式でSlackメッセージを作成してください（新しい記事がない場合は「本日の新着ニュースはありませんでした」と記載）:

📰 *AI開発ツール 最新ニュース* - {TODAY}

*🤖 Claude Code*
• *[記事タイトル]*
　[1〜2文の概要]
　URL: [URL]

*💻 Codex*
• *[記事タイトル]*
　[1〜2文の概要]
　URL: [URL]

*✨ Gemini*
• *[記事タイトル]*
　[1〜2文の概要]
　URL: [URL]

4. メッセージの最後に、送信する全記事URLをJSON配列形式で出力してください（必須）:
URLS_JSON: ["url1", "url2", ...]
"""

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    full_text = "".join(
        block.text for block in response.content if hasattr(block, "text")
    )

    if "URLS_JSON:" in full_text:
        parts = full_text.rsplit("URLS_JSON:", 1)
        message = parts[0].strip()
        try:
            new_urls = json.loads(parts[1].strip())
        except (json.JSONDecodeError, IndexError):
            new_urls = []
    else:
        message = full_text.strip()
        new_urls = []

    # Filter out any URLs Claude accidentally included from sent_urls
    new_urls = [u for u in new_urls if u not in sent_urls]
    return message, new_urls


def send_slack_dm(message: str) -> None:
    client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
    client.chat_postMessage(channel=SLACK_USER_ID, text=message)
    print("Slack DM sent.")


def main():
    sent_urls = load_sent_urls()
    print(f"Loaded {len(sent_urls)} sent URLs.")

    message, new_urls = collect_and_format_news(sent_urls)
    print(f"Found {len(new_urls)} new articles.")
    print("--- Message preview ---")
    print(message[:500])
    print("---")

    send_slack_dm(message)

    sent_urls.update(new_urls)
    save_sent_urls(sent_urls)
    print(f"saved {len(new_urls)} new URLs to {SENT_ARTICLES_FILE}")


if __name__ == "__main__":
    main()
