import requests
from bs4 import BeautifulSoup
import re
import csv
import os
from urllib.parse import urljoin, quote_plus
from collections import namedtuple
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from twilio.rest import Client

# =================================================================
# 1. CONFIGURATION (⚠️ UPDATE THESE VALUES ⚠️)
# =================================================================

# --- Scraper Config ---
PHONE_REGEX = r"(?:\+?\d{1,4}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)?\d{3,4}[\s\-]?\d{3,4}"
# 🟢 BUG FIXED: Corrected the invalid character range in the domain part.
EMAIL_REGEX = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
NAME_KEYWORDS = ["mr", "mrs", "dr", "engineer", "manager", "director", "owner", "ceo"]
Contact = namedtuple("Contact", ["type", "value", "url", "name"])

# --- Communication Config ---
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "your_email@gmail.com"      # ➡️ Your email address
EMAIL_PASSWORD = "your_email_password"      # ➡️ Your email password (Use an App Password for Gmail)

TWILIO_ACCOUNT_SID = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" # ➡️ Your Twilio Account SID
TWILIO_AUTH_TOKEN = "yyyyyyyyyyyyyyyyyyyyyyyyyyyyy"   # ➡️ Your Twilio Auth Token
TWILIO_FROM_NUMBER = "+15551234567"                   # ➡️ Your Twilio phone number

# =================================================================
# 2. GENERAL UTILITY & WEB SCRAPING FUNCTIONS
# =================================================================

def find_next_page(soup, current_url):
    """Detects pagination links based on common keywords."""
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
    """Attempts to find name/title near a scraped contact value."""
    parent = soup.find(string=re.compile(re.escape(text_to_find)))
    if parent:
        for tag in parent.parents:
            for t in tag.find_all(["h1","h2","h3","p","span","div"], limit=5, recursive=True):
                t_text = t.get_text(separator=' ', strip=True)
                if any(k in t_text.lower() for k in NAME_KEYWORDS):
                    return t_text
    return ""

def scrape_full(url):
    """Scrapes phones, emails, and attempts to find names from a single URL."""
    try:
        # Use a common User-Agent to avoid immediate blocking
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot load page: {url} - Error: {e}")
        return [], None

    soup = BeautifulSoup(r.text, "html.parser")
    phones = set()
    emails = set()
    
    # Extract contacts from tags and text using the fixed regex
    for a in soup.find_all("a", href=True):
        if a['href'].startswith("tel:"):
            phones.add(a['href'].replace("tel:", "").strip())
        if a['href'].startswith("mailto:"):
            emails.add(a['href'].replace("mailto:", "").strip())

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
    """Interactive loop for running the general URL scraper."""
    start_url = input("\nEnter first page URL for general web scraping: ")
    all_results = []
    seen_contacts = set()
    current_url = start_url
    page_count = 0
    
    print("\n🚀 Starting full URL scrape and crawl...")

    try:
        while current_url:
            page_count += 1
            print(f"--- 🌐 SCRAPING PAGE {page_count}: {current_url} ---")
            
            page_results, soup = scrape_full(current_url)
            
            if not soup: break

            new_contacts = []
            for contact in page_results:
                if (contact.type, contact.value) not in seen_contacts:
                    seen_contacts.add((contact.type, contact.value))
                    all_results.append(contact)
                    new_contacts.append(contact)

            if new_contacts:
                print(f"Found {len(new_contacts)} new contacts:")
                for c in new_contacts:
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
            save_csv(all_results, "scraped_contacts_url.csv")
        elif 'KeyboardInterrupt' not in sys.exc_info() and page_count > 0:
            print("\nNo new contacts found to save.")

def save_csv(results, filename):
    """Saves Contact data to a unified CSV file on the desktop."""
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    save_path = os.path.join(desktop, filename)
    
    csv_rows = []
    for contact in results:
        # Format based on the type of contact
        if contact.type == "PHONE":
            csv_rows.append([contact.url, contact.value, "", contact.name])
        elif contact.type == "EMAIL" or contact.type == "GOOGLE_EMAIL" or contact.type == "LINKEDIN_EMAIL":
            csv_rows.append([contact.url, "", contact.value, contact.name])

    with open(save_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Page URL/Source", "Phone Number", "Email", "Name/Title/Keyword"])
        writer.writerows(csv_rows)
    print(f"\n✔ Data saved to: {save_path}")

# =================================================================
# 3. GOOGLE SEARCH EMAIL SCRAPER
# =================================================================

def google_search_emails(keyword):
    """Scrapes emails directly from Google search result snippets."""
    search_query = f"{keyword} email contact"
    encoded_query = quote_plus(search_query)
    # Request up to 20 results per page
    url = f"https://www.google.com/search?q={encoded_query}&num=20"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    print(f"Searching Google for: '{search_query}'...")

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Google Search Failed: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    emails = set()
    
    # Extract emails from the entire search results page text
    matches = re.findall(EMAIL_REGEX, soup.get_text(), re.UNICODE)
    for email in matches:
        emails.add(email.strip())

    all_results = []
    for email in emails:
        # Name/Title is set to the search keyword for context in CSV
        all_results.append(Contact("GOOGLE_EMAIL", email, f"Google Search: {keyword}", keyword))
        
    return all_results

def google_scraper_interactive():
    print("\n--- 🔍 Google Search Email Scraper ---")
    keyword = input("Enter keyword (e.g., 'IBM sales team'): ")
    
    if not keyword:
        print("❌ Keyword cannot be empty.")
        return

    results = google_search_emails(keyword)
    
    if results:
        print(f"\n✔ Found {len(results)} unique emails:")
        for contact in results:
            print(f"  {contact.value}")
        save_csv(results, f"scraped_emails_google_{keyword.replace(' ', '_')}.csv")
    else:
        print("\n😔 No emails found for that keyword.")

# =================================================================
# 4. LINKEDIN PROFILE EXTRACTOR (NEW)
# =================================================================

def linkedin_scraper_interactive():
    print("\n--- 🔗 LinkedIn Profile Email Extractor ---")
    print("⚠️ WARNING: Direct scraping of LinkedIn pages is often blocked or requires a login.")
    print("This function attempts to find an email if the profile is fully public/unprotected.")
    
    profile_url = input("Enter the full LinkedIn Profile URL: ")
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(profile_url, headers=headers, timeout=15)
        
        # Check for non-public access (e.g., login redirect)
        if "login" in response.url.lower() or response.status_code != 200:
            print("❌ Access Denied/Blocked: LinkedIn redirected to a login page or blocked the request.")
            return

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Use the standard EMAIL_REGEX to find matches in the page source
        email_match = re.search(EMAIL_REGEX, soup.text, re.UNICODE)
        
        if email_match:
            email = email_match.group().strip()
            
            # Attempt to extract a name from the page title
            title_tag = soup.find('title')
            name = title_tag.text.split('|')[0].strip() if title_tag and '|' in title_tag.text else "N/A"
            
            print(f"\n✔ Email found: {email}")
            
            contact = Contact("LINKEDIN_EMAIL", email, profile_url, name)
            save_csv([contact], "scraped_linkedin_emails.csv")
        else:
            print("\n😔 No direct email found on the publicly accessible page content.")

    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to access URL: {e}")


# =================================================================
# 5. COMMUNICATION FUNCTIONS
# =================================================================

def send_sms(to_number, message_text):
    """Sends a single SMS via Twilio."""
    if TWILIO_AUTH_TOKEN == "yyyyyyyyyyyyyyyyyyyyyyyyyyyyy":
        print("❌ SMS Failed: Please update TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN in the CONFIGURATION section.")
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
# 6. INTERACTIVE MODE RUNNERS
# =================================================================

def sms_sender_interactive():
    print("\n--- 💬 SMS Sender Mode ---")
    to_number = input("Enter recipient phone number (with country code, e.g., +355699149691): ")
    message_text = input("Enter SMS text: ")
    send_sms(to_number, message_text)

def email_sender_interactive():
    print("\n--- 📧 Email Sender Mode ---")
    
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
# 7. MAIN MENU
# =================================================================

def main():
    # Dependency check for required libraries
    try:
        import requests, bs4, twilio
    except ImportError:
        print("\n🚨 CRITICAL: Missing required libraries!")
        print("Please run: pip install requests beautifulsoup4 twilio")
        sys.exit(1)
        
    while True:
        print("\n" + "="*50)
        print("🚀 CONTACT TOOLBOX V3 (COMPREHENSIVE)")
        print("="*50)
        print("Choose an option:")
        print("1. 🕸️  Run General URL Scraper (Website Crawl)")
        print("2. 🔍  Run Google Search Email Scraper (By Keyword)")
        print("3. 🔗  Run LinkedIn Profile Extractor (By URL)")
        print("-" * 50)
        print("4. 💬  Run SMS Sender (Requires Twilio)")
        print("5. 📧  Run Email Sender (Requires SMTP)")
        print("6. 🚪  Exit")
        print("="*50)
        
        choice = input("Enter your choice (1-6): ").strip()

        if choice == '1':
            scrape_runner_interactive()
        elif choice == '2':
            google_scraper_interactive()
        elif choice == '3':
            linkedin_scraper_interactive()
        elif choice == '4':
            sms_sender_interactive()
        elif choice == '5':
            email_sender_interactive()
        elif choice == '6':
            print("\nGoodbye! 👋")
            sys.exit()
        else:
            print("\n❌ Invalid choice. Please enter a number between 1 and 6.")

if __name__ == "__main__":
    main()