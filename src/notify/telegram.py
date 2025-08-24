import os, time, json, threading
import requests
from typing import Optional, List, Tuple

class RateLimiter:
    def __init__(self, min_interval_s: float = 1.0):
        self.min_interval_s = min_interval_s
        self.last_ts = 0.0
    def wait(self):
        now = time.time()
        delta = now - self.last_ts
        if delta < self.min_interval_s:
            time.sleep(self.min_interval_s - delta)
        self.last_ts = time.time()

class TelegramNotifier:
    def __init__(self, bot_token: Optional[str]=None, chat_id: Optional[str]=None):
        self.bot_token = bot_token or os.getenv("TG_BOT_TOKEN")
        self.chat_id   = chat_id or os.getenv("TG_CHAT_ID")
        if not self.bot_token or not self.chat_id:
            raise RuntimeError("Telegram bot token and chat id required (env TG_BOT_TOKEN, TG_CHAT_ID).")
        self.api_base  = f"https://api.telegram.org/bot{self.bot_token}"
        self.rl_global = RateLimiter(0.05) # safe global
        self.rl_chat   = RateLimiter(1.0)  # conservative per-chat limit
        self.last_update_id = 0
        
    def send_text(self, text: str, buttons: Optional[List[Tuple[str,str]]]=None):
        self.rl_chat.wait(); self.rl_global.wait()
        payload = {"chat_id": self.chat_id, "text": text}
        if buttons:
            payload["reply_markup"] = json.dumps({"inline_keyboard":[[{"text":b[0], "callback_data":b[1]} for b in buttons]]})
        try:
            requests.post(f"{self.api_base}/sendMessage", data=payload, timeout=8).raise_for_status()
        except Exception as e:
            print("Telegram send_text failed:", e)

    def send_photo(self, jpeg_bytes: bytes, caption: str=""):
        self.rl_chat.wait(); self.rl_global.wait()
        try:
            files = {"photo": ("skel.jpg", jpeg_bytes, "image/jpeg")}
            data  = {"chat_id": self.chat_id, "caption": caption}
            requests.post(f"{self.api_base}/sendPhoto", data=data, files=files, timeout=12).raise_for_status()
        except Exception as e:
            print("Telegram send_photo failed:", e)
            
    def check_callbacks(self):
        """Check for button presses and respond accordingly"""
        try:
            response = requests.get(f"{self.api_base}/getUpdates", 
                                  params={"offset": self.last_update_id + 1, "timeout": 1}, 
                                  timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data["ok"] and data["result"]:
                    for update in data["result"]:
                        self.last_update_id = update["update_id"]
                        if "callback_query" in update:
                            callback = update["callback_query"]
                            callback_data = callback["data"]
                            callback_id = callback["id"]
                            user_name = callback["from"].get("first_name", "User")
                            
                            # Acknowledge the callback
                            requests.post(f"{self.api_base}/answerCallbackQuery", 
                                        data={"callback_query_id": callback_id})
                            
                            # Respond based on callback data
                            if callback_data == "ACK_OK":
                                response_text = f"✅ Great! {user_name} confirmed they're okay. Alert cleared. 👍"
                            elif callback_data == "ACK_FALSE":
                                response_text = f"⚠️ {user_name} indicated this was a false alarm. System will learn from this. 🤖"
                            elif callback_data == "STOP_APP":
                                response_text = f"🛑 {user_name} stopped DuruOn. App will shutdown."
                                self.send_text(response_text)
                                return "STOP_APP"
                            else:
                                response_text = f"📝 {user_name} responded to the alert."
                                
                            self.send_text(response_text)
                            return callback_data
        except Exception as e:
            # Silently continue - don't spam logs with connection errors
            pass
        return None

class DummyNotifier:
    """Collects messages in-memory; used for tests and dry runs."""
    def __init__(self):
        self.messages = []
        self.photos = 0
    def send_text(self, text: str, buttons=None):
        self.messages.append(("text", text))
    def send_photo(self, data: bytes, caption: str=""):
        self.photos += 1
        self.messages.append(("photo", caption))
    def check_callbacks(self):
        return None