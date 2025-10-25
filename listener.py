import os
import requests
import json
import time

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = "fahim12064"
GITHUB_REPO = "NU-Notice-Bot-Updated-"
WORKFLOW_FILE = "main.yml"
REF = "main"

PROCESSED_FILE = "processed_updates.json"  
last_update_id = 0


# ---------------------------------------
# 🔹 Utility: Load/Save processed IDs
# ---------------------------------------
def load_processed_ids():
    """আগে যেসব update_id process হয়েছে সেগুলো ফাইল থেকে লোড করে।"""
    if os.path.exists(PROCESSED_FILE):
        try:
            with open(PROCESSED_FILE, "r") as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_processed_ids(ids):
    """processed update_id ফাইল এ সংরক্ষণ করে।"""
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(ids), f)


# ---------------------------------------
# 🔹 Trigger GitHub workflow
# ---------------------------------------
def trigger_github_workflow():
    print("🚀 Attempting to trigger GitHub workflow...")
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    data = {"ref": REF}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        print(f"🔹 Response: {response.status_code} | {response.text}")
        return response.status_code == 204, response.status_code
    except Exception as e:
        print(f"❌ Error triggering workflow: {e}")
        return False, str(e)


# ---------------------------------------
# 🔹 Telegram communication
# ---------------------------------------
def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
        print(f"📨 Sent reply to {chat_id}")
    except Exception as e:
        print(f"❌ Send failed: {e}")


def get_telegram_updates():
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"offset": last_update_id + 1, "timeout": 30}
    try:
        response = requests.get(url, params=params, timeout=40)
        if response.status_code == 200:
            updates = response.json().get("result", [])
            if updates:
                last_update_id = updates[-1]["update_id"]
                return updates
    except Exception as e:
        print(f"❌ Error fetching updates: {e}")
    return []


# ---------------------------------------
# 🔹 Process incoming messages
# ---------------------------------------
def process_messages():
    updates = get_telegram_updates()
    processed_ids = load_processed_ids()
    new_processed = False

    for update in updates:
        update_id = update["update_id"]

        # আগেই processed হলে skip করো
        if update_id in processed_ids:
            continue

        # Process new message
        if "message" in update and "text" in update["message"]:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            text = msg["text"].strip().lower()
            first_name = msg.get("from", {}).get("first_name", "বন্ধু")

            print(f"📩 {first_name}: {text}")

            if text in ["scrape", "/scrape"]:
                send_telegram_message(chat_id, "🔄 Workflow চালু করা হচ্ছে...")
                success, code = trigger_github_workflow()
                if success:
                    send_telegram_message(chat_id, "✅ Workflow সফলভাবে চালু হয়েছে!")
                else:
                    send_telegram_message(chat_id, f"❌ Workflow চালু ব্যর্থ (Status: {code})")

            elif text in ["start", "/start"]:
                send_telegram_message(chat_id, "👋 হ্যালো! 'scrape' লিখে পাঠাও GitHub workflow চালানোর জন্য।")

            # Process complete → ফাইলে রাখো
            processed_ids.add(update_id)
            new_processed = True

    # যদি নতুন কিছু process হয়, তাহলে save করো
    if new_processed:
        save_processed_ids(processed_ids)
        print(f"💾 Processed updates saved ({len(processed_ids)} total).")


# ---------------------------------------
# 🔹 Main loop
# ---------------------------------------
def main():
    print("🤖 Bot started! Waiting for new messages...")
    process_messages()
    print("Cycle finished.")


if __name__ == "__main__":
    main()
