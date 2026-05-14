#!/usr/bin/env python3
"""毎朝9:00 JST に run_daily_news.sh を実行するスケジューラー"""
import schedule
import subprocess
import time
import logging
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
LOG_FILE = SCRIPT_DIR / "run.log"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)


def run_daily_news():
    logging.info("Starting daily news job...")
    result = subprocess.run(
        [str(SCRIPT_DIR / "run_daily_news.sh")],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        logging.info(result.stdout.strip())
    if result.stderr:
        logging.warning(result.stderr.strip())
    logging.info(f"Job finished (exit code: {result.returncode})")


# 毎朝9:00 JST（UTC+9）= UTC 00:00
schedule.every().day.at("00:00").do(run_daily_news)

logging.info("Scheduler started. Next run: " + str(schedule.next_run()))

while True:
    schedule.run_pending()
    time.sleep(30)
