# 毎朝ニュース送信タスク

あなたは毎朝、ClaudeCode・Codex・Geminiに関する最新ニュースを収集し、Slackに送信するタスクを担当しています。

## 手順

### 1. 送信済み記事の確認
`/home/user/original-news/sent_articles.json` を読み込み、過去に送信済みのURLリストを取得する。

### 2. 最新ニュースの検索
以下のキーワードで**それぞれ個別に**Web検索を実施する（本日の日付を含めること）：
- "Claude Code latest news 2026"
- "OpenAI Codex latest news 2026"
- "Google Gemini latest news 2026"

### 3. 重複排除
検索結果のうち、`sent_articles.json` に含まれていないURLの記事のみを対象とする。

### 4. Slackへ送信
ユーザーID `DM6UXN0CC`（eugene）にDMで以下の形式のメッセージを送信する：

```
📰 *AI開発ツール 最新ニュース* - [今日の日付]

*🤖 Claude Code*
• [記事タイトル]
  URL: [記事URL]
• ...

*💻 Codex*
• [記事タイトル]
  URL: [記事URL]
• ...

*✨ Gemini*
• [記事タイトル]
  URL: [記事URL]
• ...
```

新しい記事がない場合は「本日の新着ニュースはありませんでした」と送信する。

### 5. sent_articles.jsonの更新
送信した全記事のURLを `sent_articles.json` の `sent_urls` 配列に追加して保存する。
ファイルはJSON形式を維持すること。

## 注意事項
- 重複送信を避けるため、必ず sent_articles.json を確認・更新すること
- 記事は各カテゴリ最大3件程度に絞ること
- 概要は1〜2文で簡潔にまとめること
