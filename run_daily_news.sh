#!/bin/bash
# 毎朝のAIニュース収集・Slack送信スクリプト
# cron: 23 0 * * * /home/user/original-news/run_daily_news.sh >> /home/user/original-news/run.log 2>&1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/run.log"
PROMPT_FILE="$SCRIPT_DIR/daily_news_prompt.md"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting daily news task..." >> "$LOG_FILE"

claude \
  --dangerously-skip-permissions \
  -p "$(cat "$PROMPT_FILE")" \
  --cwd "$SCRIPT_DIR" \
  >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Task finished with exit code: $EXIT_CODE" >> "$LOG_FILE"
