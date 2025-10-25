import os
import requests
import time

# --- Configuration ---
# এই ভেরিয়েবলগুলো GitHub Secrets এ সেট করতে হবে
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GITHUB_TOKEN = os.getenv("TOKE_GITHUB_BOT")
GITHUB_OWNER = "fahim12064"
GITHUB_REPO = "NU-Notice-Bot-Updated-"
WORKFLOW_FILE = "main.yml"
REF = "main"

# --- Global Variables ---
last_update_id = 0

def trigger_github_workflow():
    """GitHub Actions workflow ট্রিগার করার জন্য API রিকোয়েস্ট পাঠায়।"""
    print("Attempting to trigger GitHub workflow...")
    
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {GITHUB_TOKEN}"
    }
    data = {"ref": REF}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=15 )
        if response.status_code == 204:
            print("✅ GitHub workflow successfully triggered!")
            return True
        else:
            print(f"❌ Failed to trigger workflow. Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        print(f"⚠️ An error occurred while triggering the workflow: {e}")
        return False

def send_telegram_message(chat_id, text):
    """টেলিগ্রামে মেসেজ পাঠায়।"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload, timeout=10 )
        print(f"📨 Reply sent to chat_id: {chat_id}")
    except Exception as e:
        print(f"❌ Failed to send reply message: {e}")

def get_telegram_updates():
    """টেলিগ্রাম থেকে নতুন মেসেজ গ্রহণ করে।"""
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"offset": last_update_id + 1, "timeout": 30}
    
    try:
        response = requests.get(url, params=params, timeout=40 )
        if response.status_code == 200:
            updates = response.json().get("result", [])
            if updates:
                # সবচেয়ে বড় update_id সেভ করি যাতে একই মেসেজ আবার প্রসেস না হয়
                last_update_id = updates[-1]["update_id"]
                return updates
    except Exception as e:
        print(f"❌ Error getting Telegram updates: {e}")
    
    return []

def process_messages():
    """নতুন মেসেজ প্রসেস করে এবং 'scrape' কমান্ড খোঁজে।"""
    print("Checking for new messages...")
    updates = get_telegram_updates()
    
    for update in updates:
        if "message" in update and "text" in update["message"]:
            message = update["message"]
            chat_id = message["chat"]["id"]
            text = message["text"].strip().lower()
            first_name = message.get("from", {}).get("first_name", "বন্ধু")

            print(f"📩 Message received from {first_name} (Chat ID: {chat_id}): '{text}'")

            if text == "scrape":
                print(f"⚡ 'scrape' command received from {first_name}.")
                
                # ব্যবহারকারীকে জানানো হচ্ছে যে প্রসেস শুরু হয়েছে
                send_telegram_message(chat_id, "🔄 আপনার অনুরোধ পেয়েছি। GitHub workflow চালু করা হচ্ছে...")
                
                # GitHub workflow ট্রিগার করা
                if trigger_github_workflow():
                    send_telegram_message(chat_id, "✅ Workflow সফলভাবে চালু হয়েছে! নোটিশগুলো скоро আপডেট করা হবে।")
                else:
                    send_telegram_message(chat_id, "❌ দুঃখিত, workflow চালু করতে একটি সমস্যা হয়েছে।")

def main():
    """বটের মূল লুপ, যা সব সময় চলতে থাকবে।"""
    if not TELEGRAM_BOT_TOKEN or not GITHUB_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN or GITHUB_TOKEN is not set. Please check your repository secrets.")
        return
        
    print("🤖 Bot started... Waiting for 'scrape' command.")
    # শুধু একবার মেসেজ চেক করবে এবং শেষ হয়ে যাবে। GitHub Actions এটিকে আবার চালাবে।
    process_messages()
    print("Cycle finished. Waiting for the next run.")

if __name__ == "__main__":
    main()

