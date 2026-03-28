import hashlib
import json
import os
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

URL = "https://consulate.ua/ukrainian-passport"
STATE_FILE = "state.json"

KEYWORDS = [
    "booking",
    "book",
    "appointment",
    "register",
    "registration",
    "remote consular services",
    "rcs",
    "seattle",
    "tacoma",
    "passport",
    "паспорт",
    "запис",
    "виїзний",
]

def send_telegram_message(token: str, chat_id: str, text: str):
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(
        api_url,
        data={"chat_id": chat_id, "text": text},
        timeout=30,
    )
    response.raise_for_status()

def send_to_all_chat_ids(token: str, chat_ids: list[str], text: str):
    for cid in chat_ids:
        send_telegram_message(token, cid, text)

def fetch_page_text(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ConsulateMonitor/1.0)"
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return text

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def find_keywords(text: str):
    lower = text.lower()
    return sorted([kw for kw in KEYWORDS if kw.lower() in lower])

def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_ids = [
        os.environ["TELEGRAM_CHAT_ID"],
        os.environ["TELEGRAM_CHAT_ID_MOM"],
    ]
    
    test_mode = os.environ.get("TEST_MODE", "false").lower() == "true"

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    page_text = fetch_page_text(URL)
    current_hash = sha256_text(page_text)
    current_keywords = find_keywords(page_text)

    previous = load_state()
    previous_hash = previous.get("hash")
    previous_keywords = previous.get("keywords", [])

    first_run = previous_hash is None
    page_changed = previous_hash is not None and previous_hash != current_hash
    new_keywords = sorted(list(set(current_keywords) - set(previous_keywords)))

    if first_run:
        save_state({
            "hash": current_hash,
            "keywords": current_keywords,
            "checked_at": now,
        })
        print("First run completed. Baseline saved.")
        return

    if test_mode:
        message = (
            "✅ Test message from GitHub Actions\n"
            f"Time: {now}\n"
            f"URL: {URL}"
        )
        send_to_all_chat_ids(token, chat_ids, message)
        print("Test Telegram message sent.")
        return
    
    if page_changed or new_keywords:
        message = (
            "⚠️ Consulate page changed\n"
            f"Time: {now}\n"
            f"URL: {URL}\n"
            f"New keywords: {', '.join(new_keywords) if new_keywords else 'none'}"
        )
        send_to_all_chat_ids(token, chat_ids, message)
        print("Change detected. Telegram message sent.")
    else:
        print("No change detected.")

    save_state({
        "hash": current_hash,
        "keywords": current_keywords,
        "checked_at": now,
    })

if __name__ == "__main__":
    main()
