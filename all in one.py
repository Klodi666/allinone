import requests
from bs4 import BeautifulSoup
import re
import csv
import os
from urllib.parse import urljoin
from collections import namedtuple
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client

# =================================================================
# 1. CONFIGURATION
# =================================================================

# --- Scraper Config ---
PHONE_REGEX = r"(?:\+?\d{1,4}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)?\d{3,4}[\s\-]?\d{3,4}"
EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-9.-]+\.[a-zA-Z]{2,}"
NAME_KEYWORDS = ["mr", "mrs", "dr", "engineer", "manager", "director", "owner", "ceo"]
Contact = namedtuple("Contact", ["type", "value", "url", "name"])

# --- Email Sender Config ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "your_email@gmail.com"  # Your email
EMAIL_PASSWORD = "your_email_password"  # App password recommended for Gmail

# --- SMS Sender Config ---
TWILIO_ACCOUNT_SID = "AC48105203c512f43463db547c671d84c9"
TWILIO_AUTH_TOKEN = "abcdef1234567890abcdef1234567890"  # Replace with your real token
TWILIO_FROM_NUMBER = "+15551234567"  # Your Twilio phone number

# =================================================================
# 2. UTILITY & SCRAPING FUNCTIONS
# =================================================================

def find_next_page(soup, current_url):
    keywords = ["next", ">", "older", "more", "suivant"]
    links = soup.find_all("a")
    for a in links:
        text = (a.get_text() or "").strip().lower()
        href = a.get("href")
        if not href:
            continue
        if any(k in text for k in keywords):
            return urljoin(current_url, href)
    return None

def extract_name_near_text(soup, text_to_find):
    """Try to find name/title near a contact by checking parent tags."""
    parent = soup.find(string=re.compile(re.escape(text_to_find)))
    if parent:
        for tag in parent.parents:
            for t in tag.find_all(["h1","h2","h3","p","span","div"], limit=5, recursive=True):
                t_text = t.get_text(separator=' ', strip=True)
                if any(k in t_text.lower() for k in NAME_KEYWORDS):
                    return t_text
    return ""

def scrape_full(url):
    """Scrapes phones, emails, and attempts to find names."""
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot load page: {url} - Error: {e}")
        return [], None

    soup = BeautifulSoup(r.text, "html.parser")
    phones = set()
    emails = set()
    
    # 1. Extract from <a href="...">
    for a in soup.find_all("a", href=True):
        if a['href'].startswith("tel:"):
            p = a['href'].replace("tel:", "").strip()
            phones.add(p)
        if a['href'].startswith("mailto:"):
            e = a['href'].replace("mailto:", "").strip()
            emails.add(e)

    # 2. Extract from text
    text_phones = re.findall(PHONE_REGEX, soup.get_text(), re.UNICODE)
    for p in text_phones:
        p_clean = re.sub(r'[\s\-]+$', '', p).strip()
        phones.add(p_clean)

    text_emails = re.findall(EMAIL_REGEX, soup.get_text(), re.UNICODE)
    for e in text_emails:
        emails.add(e.strip())

    # Build Contact objects with name data
    results = []
    for p in phones:
        name = extract_name_near_text(soup, p)
        results.append(Contact("PHONE", p, url, name))
    for e in emails:
        name = extract_name_near_text(soup, e)
        results.append(Contact("EMAIL", e, url, name))

    return results, soup

def scrape_runner_interactive():
    """Interactive loop for running the scraper."""
    start_url = input("\nEnter first page URL for scraping: ")
    all_results = []
    seen_contacts = set()
    current_url = start_url
    page_count = 0
    
    print("\n🚀 Starting full scrape and crawl...")

    try:
        while current_url:
            page_count += 1
            print(f"--- 🌐 SCRAPING PAGE {page_count}: {current_url} ---")
            
            page_results, soup = scrape_full(current_url)
            new_contacts = []
            
            if not soup:
                break

            for contact in page_results:
                if (contact.type, contact.value) not in seen_contacts:
                    seen_contacts.add((contact.type, contact.value))
                    all_results.append(contact)
                    new_contacts.append(contact)

            if new_contacts:
                print(f"Found {len(new_contacts)} new contacts:")
                for c in new_contacts:
                    # Simple organized print for interactive mode
                    print(f"  [{c.type:<5}] {c.value:<30} - Name/Title: {c.name or 'N/A'}")

            next_url = find_next_page(soup, current_url)
            if not next_url or next_url == current_url:
                print("\n⛔ No more pages found. Stopping.\n")
                break
            
            print("\n--- Moving to next page ---\n")
            current_url = next_url

    except KeyboardInterrupt:
        print("\n⛔ Scraping interrupted by user (Ctrl+C).")

    finally:
        if all_results:
            save_csv(all_results, "scraped_contacts.csv")
        else:
            print("\nNo contacts found to save.")

def save_csv(results, filename):
    """Saves Contact namedtuples to a unified CSV file."""
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    save_path = os.path.join(desktop, filename)
    
    csv_rows = []
    for contact in results:
        if contact.type == "PHONE":
            csv_rows.append([contact.url, contact.value, "", contact.name])
        elif contact.type == "EMAIL":
            csv_rows.append([contact.url, "", contact.value, contact.name])

    with open(save_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Page URL", "Phone Number", "Email", "Name/Title"])
        writer.writerows(csv_rows)
    print(f"\n✔ Data saved to: {save_path}")

# =================================================================
# 3. COMMUNICATION FUNCTIONS
# =================================================================

def send_sms(to_number, message_text):
    """Sends a single SMS via Twilio."""
    if TWILIO_AUTH_TOKEN == "abcdef1234567890abcdef1234567890":
        print("❌ SMS Failed: Please update TWILIO_AUTH_TOKEN in the CONFIGURATION section.")
        return

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=message_text,
            from_=TWILIO_FROM_NUMBER,
            to=to_number
        )
        print(f"✔ SMS sent to {to_number} | SID: {message.sid}")
    except Exception as e:
        print(f"❌ Failed to send SMS to {to_number}: {e}")

def send_email(to_address, subject, body):
    """Sends a single email via SMTP."""
    if EMAIL_ADDRESS == "your_email@gmail.com":
        print("❌ Email Failed: Please update EMAIL_ADDRESS and EMAIL_PASSWORD in the CONFIGURATION section.")
        return

    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_address
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"✔ Email sent to {to_address}")
    except Exception as e:
        print(f"❌ Failed to send email to {to_address}: {e}")

# =================================================================
# 4. INTERACTIVE MODE RUNNERS
# =================================================================

def sms_sender_interactive():
    print("\n--- 📧 SMS Sender Mode ---")
    to_number = input("Enter phone number to send SMS (with country code, e.g., +355699149691): ")
    message_text = input("Enter SMS text: ")
    send_sms(to_number, message_text)

def email_sender_interactive():
    print("\n--- ✉️ Email Sender Mode ---")
    
    mode_choice = input("Send to (1) Single Recipient or (2) Multiple (from CSV)? Enter 1 or 2: ")

    if mode_choice == '1':
        to_address = input("Enter recipient email: ")
        subject = input("Enter email subject: ")
        body = input("Enter email body: ")
        send_email(to_address, subject, body)
        
    elif mode_choice == '2':
        csv_file = input("Enter path to CSV file containing emails (one per line): ")
        
        recipients = []
        try:
            with open(csv_file, "r", newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    if row:
                        recipients.append(row[0].strip())
        except Exception as e:
            print(f"❌ Could not read CSV file: {e}")
            return

        if not recipients:
             print("❌ No recipients found in the CSV file.")
             return

        subject = input("Enter email subject for bulk send: ")
        body = input("Enter email body for bulk send: ")

        print(f"\nStarting bulk email send to {len(recipients)} recipients...")
        for email in recipients:
            send_email(email, subject, body)
            
    else:
        print("❌ Invalid choice. Returning to main menu.")

# =================================================================
# 5. MAIN MENU
# =================================================================

def main():
    while True:
        print("\n" + "="*40)
        print("🚀 CONTACT TOOLBOX")
        print("="*40)
        print("Choose an option:")
        print("1. 🕸️  Run Web Scraper (Extract Phone, Email, Name)")
        print("2. 💬  Run SMS Sender (Requires Twilio config)")
        print("3. 📧  Run Email Sender (Requires SMTP config)")
        print("4. 🚪  Exit")
        print("="*40)
        
        choice = input("Enter your choice (1-4): ").strip()

        if choice == '1':
            scrape_runner_interactive()
        elif choice == '2':
            sms_sender_interactive()
        elif choice == '3':
            email_sender_interactive()
        elif choice == '4':
            print("\nGoodbye! 👋")
            sys.exit()
        else:
            print("\n❌ Invalid choice. Please enter a number between 1 and 4.")

if __name__ == "__main__":
    main()