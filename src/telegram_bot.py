import time
from typing import Optional
import requests
from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_EXTRA_CHAT_IDS
import logging

def send_message(text: str, chat_id: Optional[str] = None) -> None:
    base_chat = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not base_chat:
        return
    targets = []
    for x in [base_chat] + [t.strip() for t in TELEGRAM_EXTRA_CHAT_IDS.split(",") if t.strip()]:
        if x and x not in targets:
            targets.append(x)
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    max_retries = 3
    retry_delay = 5  # ثوانٍ

    for chat in targets:
        success = False
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json={"chat_id": chat, "text": text}, timeout=15)
                if response.status_code == 200:
                    success = True
                    break
                else:
                    logging.error(f"فشل إرسال تلغرام (محاولة {attempt + 1}): {response.status_code} - {response.text}")
            except Exception as e:
                logging.error(f"فشل إرسال تلغرام (محاولة {attempt + 1}): {e}")
            
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
        
        if not success:
            logging.error(f"فشل إرسال الرسالة إلى {chat} بعد {max_retries} محاولات.")
