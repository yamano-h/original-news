# 毎朝ニュース送信タスク

あなたは毎朝、ClaudeCode・Codex・Geminiに関する最新ニュースを収集し、Slackに送信するタスクを担当しています。

## 手順

### 1. 送信済み記事の確認
`/home/user/original-news/sent_articles.json` を読み込み、過去に送信済みのURLリストを取得する。

### 2. 最新ニュースの検索
以下のキーワードで**それぞれ個別に**Web検索を実施する（本日の日付を含めること）：
- "Claude Code latest news [今日の年]"
- "OpenAI Codex latest news [今日の年]"
- "Google Gemini latest news [今日の年]"

### 3. 重複排除
検索結果のうち、`sent_articles.json` に含まれていないURLの記事のみを対象とする。
新しい記事がない場合は処理を終了する（送信不要）。

### 4. Slack ツールの準備
ToolSearchを使って `mcp__Slack` または `slack` キーワードでSlackツールを検索してロードする。
利用可能なSlackツール（`mcp__Slack__chat_postMessage` 等）を探す。

### 5. Slackへ送信
ツールが見つかった場合、ユーザーID `DM6UXN0CC`（eugene）にDMで以下の形式のメッセージを送信する：

```
📰 *AI開発ツール 最新ニュース* - [今日の日付]

*🤖 Claude Code*
• [記事タイトル]
  概要: [1〜2文の概要]
  URL: [記事URL]

*💻 Codex*
• [記事タイトル]
  概要: [1〜2文の概要]
  URL: [記事URL]

*✨ Gemini*
• [記事タイトル]
  概要: [1〜2文の概要]
  URL: [記事URL]
```

Slackツールが利用できない場合はPushNotificationで結果をユーザーに通知する。

### 6. sent_articles.jsonの更新
送信に成功した全記事のURLを `sent_articles.json` の `sent_urls` 配列に追加して保存する。
ファイルはJSON形式を維持すること。

### 7. Gitコミット・プッシュ
以下のコマンドで変更をコミット・プッシュする：
```bash
cd /home/user/original-news
git add sent_articles.json
git commit -m "chore: update sent_articles.json [$(date +%Y-%m-%d)]"
git push -u origin claude/charming-noether-feumcj
```

## 注意事項
- 重複送信を避けるため、必ず sent_articles.json を確認・更新すること
- 送信に成功した記事のみ sent_articles.json に追加すること
- 記事は各カテゴリ最大3件程度に絞ること
- 概要は1〜2文で簡潔にまとめること
