import os
import re
import json
import csv
import requests
import time
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin
from datetime import datetime

# --- Configuration ---
CSV_FILE_NAME = "scraped_notices.csv"
USER_IDS_FILE = "user_ids.json"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASE_URL = "https://www.nu.ac.bd/"


# ---------- GitHub Workflow Trigger ----------

def trigger_github_workflow():
    """Trigger GitHub workflow manually via API"""
    GITHUB_TOKEN = os.getenv("TOKE_GITHUB_BOT")
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN not set in secrets.")
        return

    GITHUB_OWNER = "fahim12064"  
    GITHUB_REPO = "NU-Notice-Bot-Updated-"
    WORKFLOW_FILE = "main.yml" 
    REF = "main"

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {GITHUB_TOKEN}"
    }
    data = {"ref": REF}

    try:
        r = requests.post(url, headers=headers, json=data, timeout=15)
        if r.status_code == 204:
            print("✅ GitHub workflow triggered successfully!")
        else:
            print(f"❌ Workflow trigger failed ({r.status_code}): {r.text}")
    except Exception as e:
        print(f"⚠️ Error triggering workflow: {e}")


# ---------- Utility Functions ----------

def load_user_ids():
    """Load user IDs from JSON file with proper string conversion"""
    if not os.path.exists(USER_IDS_FILE):
        return set()
    try:
        with open(USER_IDS_FILE, "r", encoding="utf-8") as f:
            ids = json.load(f)
            # Force convert all IDs to string to avoid quote issues
            return {str(i) for i in ids}
    except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
        print(f"Error loading user IDs: {e}")
        return set()

def save_user_ids(user_ids):
    """Save user IDs to JSON file with proper encoding"""
    with open(USER_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(user_ids), f, indent=2, ensure_ascii=False)

def load_last_update_data():
    """Load last update ID and user data from file with UTF-8 encoding"""
    last_update_file = "last_update_id.txt"
    if not os.path.exists(last_update_file):
        return 0, {}
    
    try:
        with open(last_update_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if not lines:
                return 0, {}
            
            last_update_id = int(lines[0].strip())
            user_data = {}
            
            for line in lines[1:]:
                if line.strip():
                    parts = line.strip().split(',', 1)
                    if len(parts) == 2:
                        chat_id, name = parts
                        user_data[chat_id] = name
            
            return last_update_id, user_data
    except Exception as e:
        print(f"Error reading last update data: {e}")
        return 0, {}

def save_last_update_data(last_update_id, user_data):
    """Save last update ID and user data to file with UTF-8 encoding"""
    last_update_file = "last_update_id.txt"
    try:
        with open(last_update_file, "w", encoding="utf-8") as f:
            f.write(str(last_update_id) + "\n")
            for chat_id, name in user_data.items():
                f.write(f"{chat_id},{name}\n")
    except Exception as e:
        print(f"Error saving last update data: {e}")

def handle_telegram_updates():
    """Handle new Telegram users and save their data"""
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ Telegram bot token not set")
        return

    user_ids = load_user_ids()
    last_update_id, user_data = load_last_update_data()

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=10"

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        updates = response.json().get("result", [])
    except Exception as e:
        print(f"❌ Telegram API error: {e}")
        return

    if not updates:
        print("👍 No new Telegram messages")
        return

    new_users_found = False
    max_update_id = last_update_id

    for update in updates:
        max_update_id = max(max_update_id, update["update_id"])
        msg = update.get("message", {})
        text = msg.get("text", "")
        chat = msg.get("chat", {})
        chat_id = str(chat.get("id"))
        first_name = msg.get("from", {}).get("first_name", "Friend")

        if not chat_id or not text:
            continue

        if text.strip().lower() == "/start":
            if chat_id not in user_ids:
                user_ids.add(chat_id)
                user_data[chat_id] = first_name
                new_users_found = True
                print(f"✅ New user registered: {chat_id} ({first_name})")

                # Send welcome message
                welcome_text = (
                    f"👋 Welcome, {first_name}!\n\n"
                    "You are now subscribed to receive notifications "
                    "for new notices from National University 📢✨\n\n"
                    "You will receive notifications when new notices are published."
                )

                try:
                    send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                    payload = {"chat_id": chat_id, "text": welcome_text}
                    requests.post(send_url, json=payload, timeout=10)
                except Exception as e:
                    print(f"❌ Failed to send welcome message to {chat_id}: {e}")
        elif text.strip().lower() == "scrape":
            first_name = msg.get("from", {}).get("first_name", "বন্ধু")
            print(f"⚡ Scrape command received from {first_name} ({chat_id})")

            # ✅ টেলিগ্রামে রিপ্লাই পাঠানো
            try:
                reply_text = "🔄 GitHub workflow চলছে, একটু অপেক্ষা করুন..."
                requests.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={"chat_id": chat_id, "text": reply_text},
                    timeout=10
                )
            except Exception as e:
                print(f"❌ রিপ্লাই পাঠাতে ব্যর্থ: {e}")

            # 👉 এখন GitHub workflow ট্রিগার করো
            trigger_github_workflow()

    # Save new users
    if new_users_found:
        save_user_ids(user_ids)
        print(f"💾 Saved {len(user_ids)} total users to user_ids.json")

    # Save last update ID and user data
    save_last_update_data(max_update_id, user_data)
    print("✅ Telegram updates and user data saved successfully")

def load_scraped_links_from_csv():
    """Load scraped links from CSV file with improved CSV parsing"""
    if not os.path.exists(CSV_FILE_NAME):
        return set()
    
    links = set()
    try:
        with open(CSV_FILE_NAME, "r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            # Skip header
            next(reader, None)
            for row in reader:
                # Skip empty rows
                if not row or len(row) < 2:
                    continue
                
                # The URL should be the second column
                url = row[1].strip()
                
                # Only add if it's a valid URL
                if url.startswith("http"):
                    links.add(url)
                    
    except Exception as e:
        print(f"Error reading CSV file: {e}")
    
    print(f"📊 Loaded {len(links)} URLs from CSV")
    return links

def append_to_csv(notice_title, url, date):
    """Append new notice to CSV file with proper CSV formatting"""
    file_exists = os.path.exists(CSV_FILE_NAME)
    try:
        with open(CSV_FILE_NAME, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            if not file_exists:
                writer.writerow(["Notice Title", "URL", "Date"])
            writer.writerow([notice_title, url, date])
        print(f"✅ Successfully saved to CSV: {notice_title[:30]}...")
    except Exception as e:
        print(f"Error saving to CSV: {e}")

def send_telegram_notification(message):
    """Send notification to all registered users using plain text (no parsing)"""
    if not TELEGRAM_BOT_TOKEN:
        print("⚠️ Telegram token not configured. Skipping notification")
        return

    user_ids = load_user_ids()
    if not user_ids:
        print("🤷 No users registered to notify")
        return

    print(f"✉️ Sending notification to {len(user_ids)} users...")
    success = 0
    fail = 0

    for chat_id in user_ids:
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                data={
                    "chat_id": chat_id,
                    "text": message,
                    "disable_web_page_preview": True
                },
                timeout=15
            )
            response.raise_for_status()
            success += 1
            print(f"✅ Sent to {chat_id}")
            time.sleep(1)  # Rate limiting
        except Exception as e:
            fail += 1
            print(f"❌ Failed to send to {chat_id}: {e}")
    
    print(f"    ✅ Sent to {success} users, ❌ Failed for {fail}")

# ---------- Scraper Functions ----------

def scrape_nu_notices():
    """Scrape notices from National University website"""
    print("\n--- Step 1: Scraping NU Notices ---")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(BASE_URL, timeout=600000)

            # Wait for table to appear
            page.wait_for_selector("table tbody tr")
            time.sleep(2)

            # Locate all rows in the table
            rows = page.locator("table tbody tr")
            total = rows.count()
            
            # Limit to first 20 notices
            if total > 20:
                total = 20
            
            print(f"📊 Found {total} notices in the table")

            all_data = []

            for i in range(total):
                row = rows.nth(i)
                
                # Extract notice title and link
                title_element = row.locator("td:first-child a")
                title = title_element.inner_text().strip() if title_element.count() > 0 else ""
                href = title_element.get_attribute("href") if title_element.count() > 0 else ""
                
                # Extract publish date
                date_element = row.locator("td:last-child")
                publish_date = date_element.inner_text().strip() if date_element.count() > 0 else ""
                
                if href and title:
                    # Convert relative URL to absolute URL
                    full_url = urljoin(BASE_URL, href)
                    
                    all_data.append({
                        "title": title,
                        "url": full_url,
                        "date": publish_date
                    })
                    print(f"📰 Found notice: {title[:50]}...")

            browser.close()

        print(f"🎯 Total notices found: {len(all_data)}")
        return all_data
    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        return []

def parse_date(date_str):
    """Parse date string in format 'October 22, 2025' to datetime object"""
    try:
        return datetime.strptime(date_str, "%B %d, %Y")
    except ValueError:
        # Try alternative formats
        try:
            return datetime.strptime(date_str, "%b %d, %Y")
        except ValueError:
            print(f"❌ Could not parse date: {date_str}")
            return None

# ---------- Main Function ----------
if __name__ == "__main__":
    print("--- Starting NU Notice Scraper and Telegram Bot ---")
    
    # Step 1: Check for new Telegram users
    print("\n--- Checking for New Telegram Users ---")
    handle_telegram_updates()

    # Step 2: Start scraping
    all_notices = scrape_nu_notices()

    if not all_notices:
        print("\n📭 No notices found")
        # Send "No Notice" message
        today = datetime.now().strftime("%Y-%m-%d")
        message = f"📅 Date: {today}\n\n📭 No Notice"
        send_telegram_notification(message)
    else:
        scraped_links = load_scraped_links_from_csv()
        print(f"🔎 Already scraped: {len(scraped_links)} notices")
        
        # Get today's date
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Group notices by date
        notices_by_date = {}
        
        for notice in all_notices:
            # Parse the notice date
            notice_date = parse_date(notice["date"])
            notice_date_str = notice_date.strftime("%Y-%m-%d") if notice_date else ""
            
            # Add to the appropriate date group
            if notice_date_str:
                if notice_date_str not in notices_by_date:
                    notices_by_date[notice_date_str] = []
                notices_by_date[notice_date_str].append(notice)
        
        # Process today's notices
        if today in notices_by_date:
            today_notices = notices_by_date[today]
            
            # Filter out already scraped notices
            new_notices_to_send = [notice for notice in today_notices if notice["url"] not in scraped_links]
            
            if new_notices_to_send:
                # Create message with all new notices for today
                message = f"📅 Date: {today}\n\n🔔 New Notices Found\n\n"
                
                for i, notice in enumerate(new_notices_to_send, 1):
                    message += f"{i}. {notice['title']}\n   View Notice: {notice['url']}\n\n"
                
                print(f"\n--- Sending {len(new_notices_to_send)} New Notices for {today} ---")
                send_telegram_notification(message)
                
                # Save all new notices to CSV
                for notice in new_notices_to_send:
                    append_to_csv(notice["title"], notice["url"], notice["date"])
            else:
                print(f"\n✅ No new notices to send for {today}")
                # Send "No Notice" message
                message = f"📅 Date: {today}\n\n📭 No Notice"
                send_telegram_notification(message)
        else:
            print(f"\n✅ No notices found for {today}")
            # Send "No Notice" message
            message = f"📅 Date: {today}\n\n📭 No Notice"
            send_telegram_notification(message)
        
        # Save all notices to CSV (for future reference)
        for notice in all_notices:
            if notice["url"] not in scraped_links:
                append_to_csv(notice["title"], notice["url"], notice["date"])

    print("\n--- Mission Completed ---")
