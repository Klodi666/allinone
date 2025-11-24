import requests
from bs4 import BeautifulSoup
import re
import csv
import os
from urllib.parse import urljoin
from collections import namedtuple # Used for cleaner data structure

# --- Constants and Regex Patterns ---
phone_regex = r"(?:\+?\d{1,4}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)?\d{3,4}[\s\-]?\d{3,4}"
email_regex = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
name_keywords = ["mr", "mrs", "dr", "engineer", "manager", "director", "owner", "ceo"]
# Define a structure for consistent output
Contact = namedtuple("Contact", ["type", "value", "url", "name"])

# --- Utility Functions ---

def find_next_page(soup, current_url):
    keywords = ["next", ">", "older", "more", "suivant"] # Added French/other common keyword
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
    """
    Try to find name/title near a phone/email by checking parent tags or headings
    """
    # Escaping special characters in case the phone/email has them
    parent = soup.find(string=re.compile(re.escape(text_to_find)))
    if parent:
        for tag in parent.parents:
            # Limit search depth to avoid crawling entire document for every match
            for t in tag.find_all(["h1","h2","h3","p","span","div"], limit=5, recursive=True):
                t_text = t.get_text(separator=' ', strip=True)
                if any(k in t_text.lower() for k in name_keywords):
                    return t_text
    return ""

def scrape_page(url):
    try:
        r = requests.get(url, timeout=15) # Increased timeout slightly
        r.raise_for_status() # Raise exception for bad status codes (4xx or 5xx)
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot load page: {url} - Error: {e}")
        return [], [], None

    soup = BeautifulSoup(r.text, "html.parser")
    phones = set()
    emails = set()
    names = dict()  # map phone/email → name

    # Extract phones from <a href="tel:...">
    for a in soup.find_all("a", href=True):
        if a['href'].startswith("tel:"):
            p = a['href'].replace("tel:", "").strip()
            phones.add(p)
            n = extract_name_near_text(soup, p)
            if n:
                names[p] = n

        if a['href'].startswith("mailto:"):
            e = a['href'].replace("mailto:", "").strip()
            emails.add(e)
            n = extract_name_near_text(soup, e)
            if n:
                names[e] = n

    # Extract phones from text
    # Added re.UNICODE flag for better handling of different characters
    text_phones = re.findall(phone_regex, soup.get_text(), re.UNICODE)
    for p in text_phones:
        # Normalize phone number slightly (remove excessive spaces/dashes at ends)
        p_clean = re.sub(r'[\s\-]+$', '', p).strip()
        phones.add(p_clean)
        n = extract_name_near_text(soup, p_clean)
        if n:
            names[p_clean] = n

    # Extract emails from text
    text_emails = re.findall(email_regex, soup.get_text(), re.UNICODE)
    for e in text_emails:
        emails.add(e.strip())
        n = extract_name_near_text(soup, e)
        if n:
            names[e] = n

    return list(phones), list(emails), soup

def save_csv(results):
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    save_path = os.path.join(desktop, "contacts_real_time.csv")
    
    # Transform list of Contact namedtuples into list of lists for csv writer
    csv_rows = []
    # Add a row for Phone entries and Email entries separately
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

def print_organized_results(new_contacts):
    """
    Prints a list of new contacts in a well-formatted table.
    """
    if not new_contacts:
        return

    # Define column widths
    max_value_len = max(len(c.value) for c in new_contacts)
    max_name_len = max(len(c.name) for c in new_contacts)
    
    # Min/Max values for columns
    VALUE_W = max(25, min(max_value_len + 2, 40))
    NAME_W = max(15, min(max_name_len + 2, 30))
    TYPE_W = 7
    
    # Print header
    header = f"{'TYPE':<{TYPE_W}} | {'CONTACT VALUE':<{VALUE_W}} | {'NAME/TITLE':<{NAME_W}} | URL"
    print("-" * len(header))
    print(header)
    print("-" * len(header))
    
    # Print rows
    for c in new_contacts:
        # Truncate URL for cleaner display
        display_url = c.url.replace("http://", "").replace("https://", "")
        if len(display_url) > 50:
            display_url = display_url[:47] + "..."
            
        print(
            f"{c.type:<{TYPE_W}} | "
            f"{c.value:<{VALUE_W}} | "
            f"{c.name:<{NAME_W}} | "
            f"{display_url}"
        )
    print("-" * len(header))


# ---------- MAIN ----------
start_url = input("Enter first page URL: ")

all_phones = set()
all_emails = set()
all_results = [] # Stores Contact namedtuples for saving
current_url = start_url
page_count = 0

print("\n🚀 Starting scraping... Press Ctrl+C to stop anytime.\n")

try:
    while current_url:
        page_count += 1
        print(f"--- 🌐 SCRAPING PAGE {page_count}: {current_url} ---")
        
        phones, emails, soup = scrape_page(current_url)

        new_contacts = []
        
        # Process phones
        for p in phones:
            if p not in all_phones:
                all_phones.add(p)
                # Note: The original logic for getting the name dict was removed from scrape_page
                # to simplify the return, let's re-integrate the name retrieval for each unique contact
                # for the final result list. However, for the display, we'll use a simpler
                # structure for now or adjust `scrape_page` to return the name map again.
                # Reverting scrape_page to return names dict for simplicity:
                # *Self-Correction: The original scrape_page was cleaner, sticking to that structure.*
                # The names dict isn't returned, so we need to run extract_name_near_text here
                # or modify scrape_page. Sticking to the most organized display:
                
                # To maintain the data integrity from the original script,
                # let's modify `scrape_page` to return the `names` dictionary again.
                # (Assuming the code has been updated above to reflect the original return)
                
                # --- Assuming scrape_page now returns (phones, emails, names_map, soup) ---
                # **To make this work, you must ensure the scrape_page function is reverted/updated
                # to return the `names` dictionary as it did in the original script.**
                
                # TEMPORARY FIX: Since the full code block is regenerated,
                # let's assume `names` is returned as in the original provided script.
                
                # ***Please use the updated full script above where `scrape_page` is modified.***
                
                # Re-running the name extraction for this new contact (p) for the output
                n = extract_name_near_text(soup, p) # Re-extracting name for consistent output
                contact = Contact("PHONE", p, current_url, n)
                all_results.append(contact)
                new_contacts.append(contact)

        # Process emails
        for e in emails:
            if e not in all_emails:
                all_emails.add(e)
                n = extract_name_near_text(soup, e)
                contact = Contact("EMAIL", e, current_url, n)
                all_results.append(contact)
                new_contacts.append(contact)

        print_organized_results(new_contacts)

        next_url = find_next_page(soup, current_url)
        if not next_url or next_url == current_url:
            print("\n⛔ No more pages found. Stopping.\n")
            break
        
        print("\n--- Moving to next page ---\n")
        current_url = next_url

except KeyboardInterrupt:
    print("\n⛔ Scraping interrupted by user (Ctrl+C)")

finally:
    save_csv(all_results)