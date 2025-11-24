import requests
import re
import csv
import os
import signal
import json
import random
import time
from urllib.parse import urljoin, urlparse, quote_plus
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

# ----------------- Banner -----------------
def print_banner():
    """Prints a text-based banner for the tool."""
    banner = """
  _.-=-._._.-=-._._.-=-._._.-=-._._.-=-._._.-=-._._.-=-._
_|  _   _    ___   ___  _   _ ___  _   _  _   _  _   _  |_
| | |  | |  / __| | _ \\| | | | _ \\| |_| | \\ \\ / / | | | | |
| | |__| | | (__  |   /| |_| |  _/|  _  |  \\ V /  | |_| | |
| |______|  \\___| |_|\\_\\\\___/|_|  |_| |_|   |_|    \\___/  |
|_.-=-._._.-=-._._.-=-._._.-=-._._.-=-._._.-=-._._.-=-._|
    """
    print(banner)

# ----------------- User Agent Rotation -----------------
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64)",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)"
]

def get_headers():
    return {"User-Agent": random.choice(USER_AGENTS)}

# ----------------- Shared Regex -----------------
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_REGEX = r"\+?\d[\d\s\-]{7,}\d"

def extract_emails(text):
    return set(re.findall(EMAIL_REGEX, text))

def extract_contacts(text):
    emails = set(re.findall(EMAIL_REGEX, text))
    phones = set(re.findall(PHONE_REGEX, text))
    return emails, phones

# ----------------- Global Scraper State -----------------
emails_found = set()
visited_links = set()
email_count = 0
stop_scraping = False

def signal_handler(sig, frame):
    """Handle Ctrl+C to stop gracefully and save results."""
    global stop_scraping
    stop_scraping = True
    print("\n\n[!] Stopping... saving results before exit.")
    exit(0)

signal.signal(signal.SIGINT, signal_handler)

# ----------------- Scraper 1: General Website Scraper (email_scraper.py) -----------------
def fetch_emails_from_url(url, crawl=False, base_domain=None):
    """Fetch and extract emails from a given URL, optionally crawling links."""
    global email_count, emails_found
    try:
        response = requests.get(url, timeout=10, headers=get_headers())
        if response.status_code != 200:
            return set(), []
        
        emails = extract_emails(response.text)
        new_links = []
        
        for email in emails:
            if email not in emails_found:
                emails_found.add(email)
                email_count += 1
                print(f"[{email_count}] {email}")
        
        if crawl:
            soup = BeautifulSoup(response.text, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                link = urljoin(url, a_tag["href"])
                if base_domain in link and link not in visited_links:
                    new_links.append(link)
        
        return emails, new_links
    except:
        return set(), []

def scrape_urls(urls, max_emails=None, crawl=False):
    """Scrape multiple URLs for emails with threading, optional crawling."""
    global stop_scraping, visited_links
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for url in urls:
            if url not in visited_links:
                visited_links.add(url)
                futures[executor.submit(fetch_emails_from_url, url, crawl, urlparse(url).netloc)] = url
        
        while futures and not stop_scraping:
            new_links_to_crawl = []
            for future in as_completed(list(futures.keys())):
                if stop_scraping:
                    break
                if max_emails and email_count >= max_emails:
                    print(f"\n[+] Reached email limit ({max_emails}). Stopping.")
                    stop_scraping = True
                    break
                
                try:
                    _, new_links = future.result()
                    if crawl:
                        new_links_to_crawl.extend(new_links)
                except Exception as e:
                    print(f"Error processing future: {e}")
                
                del futures[future]
            
            if crawl and not stop_scraping:
                for link in new_links_to_crawl:
                    if link not in visited_links:
                        visited_links.add(link)
                        futures[executor.submit(fetch_emails_from_url, link, crawl, urlparse(link).netloc)] = link

def save_emails_to_csv(filename="emails.csv"):
    """Save collected emails to CSV."""
    if not emails_found:
        print("\n[!] No emails found.")
        return

    mode = "w"
    if os.path.exists(filename):
        choice = input(f"\n[?] {filename} exists. Append (a) or Overwrite (o)? [a/o]: ").strip().lower()
        if choice == "a":
            mode = "a"

    with open(filename, mode, newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if mode == "w":
            writer.writerow(["Email"])
        for email in emails_found:
            writer.writerow([email])

    abs_path = os.path.abspath(filename)
    print(f"\n[+] Emails saved to: {abs_path}")

def run_general_scraper():
    print("\n--- General Website Scraper ---")
    while True:
        print("1. Enter URLs manually")
        print("2. Load URLs from file (simple)")
        print("3. Load URLs from file and crawl site links")
        print("4. Back to main menu")
        choice = input("Select an option [1-4]: ").strip()
        
        urls = []
        crawl = False
        
        if choice == "1":
            urls = input("Enter URLs separated by space: ").split()
        elif choice == "2":
            file_path = input("Enter file path (default: urls.txt): ").strip() or "urls.txt"
            if not os.path.exists(file_path):
                print("[!] File not found.")
                continue
            with open(file_path, "r") as f:
                urls = [line.strip() for line in f if line.strip()]
        elif choice == "3":
            file_path = input("Enter file path (default: urls.txt): ").strip() or "urls.txt"
            if not os.path.exists(file_path):
                print("[!] File not found.")
                continue
            with open(file_path, "r") as f:
                urls = [line.strip() for line in f if line.strip()]
            crawl = True
        elif choice == "4":
            return
        else:
            print("[!] Invalid choice, try again.")
            continue
            
        limit = input("Enter max emails to collect (or press Enter for unlimited): ").strip()
        max_emails = int(limit) if limit.isdigit() else None
        
        global emails_found, visited_links, email_count, stop_scraping
        emails_found = set()
        visited_links = set()
        email_count = 0
        stop_scraping = False

        print("\n[+] Starting scrape... Press CTRL+C to stop anytime.\n")
        scrape_urls(urls, max_emails=max_emails, crawl=crawl)
        save_emails_to_csv()
        break

# ----------------- Scraper 2: Google Email Scraper (google_email_scraping.py) -----------------
def search_engine_urls(keyword, engine="google", num_results=50):
    query = f'intitle:"contact" AND "{keyword}"'
    query_encoded = quote_plus(query)
    urls = []
    
    if engine == "google":
        urls = [f"https://www.google.com/search?q={query_encoded}&start={start}" for start in range(0, num_results, 10)]
    elif engine == "bing":
        urls = [f"https://www.bing.com/search?q={query_encoded}&first={start}" for start in range(0, num_results, 10)]
    elif engine == "yahoo":
        urls = [f"https://search.yahoo.com/search?p={query_encoded}&b={start+1}" for start in range(0, num_results, 10)]
    elif engine == "duckduckgo":
        urls = [f"https://duckduckgo.com/html/?q={query_encoded}&s={start*50}" for start in range(0, num_results, 50)]
    return urls

def fetch_page_with_links(url):
    emails = set()
    links = []
    try:
        response = requests.get(url, headers=get_headers(), timeout=10)
        emails.update(extract_emails(response.text))
        soup = BeautifulSoup(response.text, "html.parser")
        links = [a.get('href') for a in soup.find_all('a', href=True) if a.get('href') and a.get('href').startswith('http')]
    except:
        pass
    return emails, links

def scrape_keyword(keyword, engines, num_results=50, max_threads=5, email_limit=500, progress_file="progress.json"):
    all_emails = set()
    visited_links = set()
    
    if os.path.exists(progress_file):
        with open(progress_file, "r") as f:
            progress_data = json.load(f)
    else:
        progress_data = {}
        
    try:
        for engine in engines:
            print(f"\n[+] Scraping {engine.title()} for keyword: {keyword}")
            search_urls = search_engine_urls(keyword, engine, num_results)
            total_urls = len(search_urls)
            start_index = progress_data.get(keyword, {}).get(engine, 0)
            
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                future_to_url = {executor.submit(fetch_page_with_links, url): url for url in search_urls[start_index:]}
                
                for i, future in enumerate(as_completed(future_to_url), start=start_index+1):
                    emails, links = future.result()
                    all_emails.update(emails)
                    for link in links:
                        if link not in visited_links:
                            visited_links.add(link)
                    
                    print(f"    {engine.title()} progress: {i}/{total_urls} pages | Emails found: {len(all_emails)}", end="\r")
                    
                    if keyword not in progress_data:
                        progress_data[keyword] = {}
                    progress_data[keyword][engine] = i
                    with open(progress_file, "w") as f:
                        json.dump(progress_data, f)
                    
                    if len(all_emails) >= email_limit:
                        print(f"\n[!] Email limit of {email_limit} reached for keyword: {keyword}")
                        return all_emails, False
                        
                    time.sleep(1)
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user. Progress saved.")
        with open(progress_file, "w") as f:
            json.dump(progress_data, f)
        return all_emails, False
        
    if os.path.exists(progress_file):
        os.remove(progress_file)
    return all_emails, True

def run_google_scraper():
    print("\n--- Google/Bing/Yahoo/DDG Email Scraper ---")
    choice = input("Input keywords manually (1) or from a file (2)? [1/2]: ").strip()

    if choice == "1":
        keywords = input("Enter keywords separated by comma: ").strip().split(",")
        keywords = [kw.strip() for kw in keywords if kw.strip()]
    elif choice == "2":
        file_path = input("Enter path to keywords file: ").strip()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                keywords = [line.strip() for line in f if line.strip()]
        except:
            print("[!] Could not read file.")
            return
    else:
        print("[!] Invalid choice. Exiting.")
        return

    num_results_input = input("Max search results per engine (default 50): ").strip()
    num_results = int(num_results_input) if num_results_input.isdigit() else 50
    threads_input = input("Max threads (default 5): ").strip()
    max_threads = int(threads_input) if threads_input.isdigit() else 5
    email_limit_input = input("Max emails per keyword (default 500): ").strip()
    email_limit = int(email_limit_input) if email_limit_input.isdigit() else 500
    
    engines = ["google", "bing", "yahoo", "duckduckgo"]
    all_emails = set()
    
    for keyword in keywords:
        emails, completed = scrape_keyword(keyword, engines, num_results=num_results, max_threads=max_threads, email_limit=email_limit)
        print(f"\n[+] Found {len(emails)} emails for keyword: {keyword}")
        all_emails.update(emails)
        
    if all_emails:
        output_file = "emails_from_keywords.csv"
        with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Email"])
            for email in sorted(all_emails):
                writer.writerow([email])
        print(f"\n[+] Total unique emails found: {len(all_emails)}")
        print(f"[+] Emails saved to {output_file}")
    else:
        print("[!] No emails found.")

# ----------------- Scraper 3: Facebook Scraper (facebook_scraper.py) -----------------
def extract_name(soup):
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    h1 = soup.find('h1')
    if h1 and h1.get_text():
        return h1.get_text().strip()
    h2 = soup.find('h2')
    if h2 and h2.get_text():
        return h2.get_text().strip()
    return "Unknown"

def fetch_facebook_page(url):
    emails = set()
    phones = set()
    name = "Unknown"
    try:
        response = requests.get(url, headers=get_headers(), timeout=10)
        emails, phones = extract_contacts(response.text)
        soup = BeautifulSoup(response.text, "html.parser")
        name = extract_name(soup)
    except:
        pass
    return name, emails, phones

def search_facebook_urls(keyword, engine="google", num_results=50):
    query = f'site:facebook.com "{keyword}"'
    query_encoded = quote_plus(query)
    urls = []
    if engine == "google":
        urls = [f"https://www.google.com/search?q={query_encoded}&start={start}" for start in range(0, num_results, 10)]
    elif engine == "bing":
        urls = [f"https://www.bing.com/search?q={query_encoded}&first={start}" for start in range(0, num_results, 10)]
    elif engine == "duckduckgo":
        urls = [f"https://duckduckgo.com/html/?q={query_encoded}&s={start*50}" for start in range(0, num_results, 50)]
    return urls

def scrape_facebook(keyword, engines, num_results=50, max_threads=5, contact_limit=100, progress_file="fb_progress.json"):
    all_contacts = []
    
    if os.path.exists(progress_file):
        with open(progress_file, "r") as f:
            progress_data = json.load(f)
    else:
        progress_data = {}

    try:
        for engine in engines:
            print(f"\n[+] Scraping {engine.title()} for keyword: {keyword}")
            search_urls = search_facebook_urls(keyword, engine, num_results)
            total_urls = len(search_urls)
            start_index = progress_data.get(keyword, {}).get(engine, 0)

            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                future_to_url = {executor.submit(fetch_facebook_page, url): url for url in search_urls[start_index:]}
                
                for i, future in enumerate(as_completed(future_to_url), start=start_index+1):
                    name, emails, phones = future.result()
                    if emails or phones:
                        all_contacts.append({
                            "Keyword": keyword,
                            "Name": name,
                            "Email": ", ".join(emails),
                            "Phone": ", ".join(phones)
                        })
                    
                    print(f"    {engine.title()} progress: {i}/{total_urls} pages | Contacts found: {len(all_contacts)}", end="\r")

                    if keyword not in progress_data:
                        progress_data[keyword] = {}
                    progress_data[keyword][engine] = i
                    with open(progress_file, "w") as f:
                        json.dump(progress_data, f)
                    
                    if len(all_contacts) >= contact_limit:
                        print(f"\n[!] Contact limit of {contact_limit} reached for keyword: {keyword}")
                        return all_contacts, False
                    
                    time.sleep(1)
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user. Progress saved.")
        with open(progress_file, "w") as f:
            json.dump(progress_data, f)
        return all_contacts, False

    if os.path.exists(progress_file):
        os.remove(progress_file)
    return all_contacts, True

def run_facebook_scraper():
    print("\n--- Facebook Public Contacts Scraper ---")
    choice = input("Input keywords manually (1) or from a file (2)? [1/2]: ").strip()
    
    if choice == "1":
        keywords = input("Enter keywords separated by comma: ").strip().split(",")
        keywords = [kw.strip() for kw in keywords if kw.strip()]
    elif choice == "2":
        file_path = input("Enter path to keywords file: ").strip()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                keywords = [line.strip() for line in f if line.strip()]
        except:
            print("[!] Could not read file.")
            return
    else:
        print("[!] Invalid choice. Exiting.")
        return
        
    num_results_input = input("Max search results per engine (default 50): ").strip()
    num_results = int(num_results_input) if num_results_input.isdigit() else 50
    threads_input = input("Max threads (default 5): ").strip()
    max_threads = int(threads_input) if threads_input.isdigit() else 5
    contact_limit_input = input("Max contacts per keyword (default 100): ").strip()
    contact_limit = int(contact_limit_input) if contact_limit_input.isdigit() else 100
    
    engines = ["google", "bing", "duckduckgo"]
    all_contacts = []
    
    for keyword in keywords:
        contacts, completed = scrape_facebook(keyword, engines, num_results=num_results, max_threads=max_threads, contact_limit=contact_limit)
        print(f"\n[+] Found {len(contacts)} contacts for keyword: {keyword}")
        all_contacts.extend(contacts)

    if all_contacts:
        output_file = "facebook_contacts_with_names.csv"
        with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["Keyword", "Name", "Email", "Phone"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for contact in all_contacts:
                writer.writerow(contact)
        print(f"\n[+] Total contacts found: {len(all_contacts)}")
        print(f"[+] Contacts saved to {output_file}")
    else:
        print("[!] No contacts found.")

# ----------------- Scraper 4: LinkedIn Scraper (linkedin_scraper.py) -----------------
def search_linkedin(query, engine="google", num_results=50):
    urls = []
    query_encoded = quote_plus(f"{query} site:linkedin.com/in")
    
    if engine == "google":
        for start in range(0, num_results, 10):
            url = f"https://www.google.com/search?q={query_encoded}&start={start}"
            try:
                response = requests.get(url, headers=get_headers(), timeout=10)
                soup = BeautifulSoup(response.text, "html.parser")
                for link in soup.select("a"):
                    href = link.get("href")
                    if href and href.startswith("/url?q="):
                        real_url = href.split("/url?q=")[1].split("&")[0]
                        if "linkedin.com/in" in real_url:
                            title_tag = link.get_text()
                            urls.append((title_tag.strip(), real_url))
                time.sleep(2)
            except:
                continue
    elif engine == "bing":
        for first in range(0, num_results, 10):
            url = f"https://www.bing.com/search?q={query_encoded}&first={first}"
            try:
                response = requests.get(url, headers=get_headers(), timeout=10)
                soup = BeautifulSoup(response.text, "html.parser")
                for a in soup.select("li.b_algo h2 a"):
                    href = a.get("href")
                    title = a.get_text()
                    if "linkedin.com/in" in href:
                        urls.append((title.strip(), href))
                time.sleep(2)
            except:
                continue
    elif engine == "yahoo":
        for start in range(0, num_results, 10):
            url = f"https://search.yahoo.com/search?p={query_encoded}&b={start+1}"
            try:
                response = requests.get(url, headers=get_headers(), timeout=10)
                soup = BeautifulSoup(response.text, "html.parser")
                for a in soup.select("a.ac-algo"):
                    href = a.get("href")
                    title = a.get_text()
                    if "linkedin.com/in" in href:
                        urls.append((title.strip(), href))
                time.sleep(2)
            except:
                continue
    return urls

def run_linkedin_scraper():
    print("\n--- LinkedIn Name & URL Extractor ---")
    file_path = input("Enter path to keywords file (default: keywords.txt): ").strip() or "keywords.txt"
    if not os.path.exists(file_path):
        print(f"[!] File not found: {file_path}")
        return
    
    with open(file_path, "r", encoding="utf-8") as f:
        keywords = [line.strip() for line in f if line.strip()]
        
    engines = ["google", "bing", "yahoo"]
    all_results = []
    
    for keyword in keywords:
        print(f"\n[+] Searching LinkedIn for keyword: {keyword}")
        for engine in engines:
            print(f"    Searching on {engine.title()}...")
            results = search_linkedin(keyword, engine)
            print(f"        Found {len(results)} profiles")
            all_results.extend(results)
    
    unique_results = {}
    for name, url in all_results:
        if url not in unique_results:
            unique_results[url] = name
            
    output_file = "linkedin_profiles.csv"
    if unique_results:
        with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["Name", "LinkedIn URL"])
            for url, name in unique_results.items():
                writer.writerow([name, url])
        abs_path = os.path.abspath(output_file)
        print(f"\n[+] Extraction complete. Saved to {abs_path}")
    else:
        print("\n[!] No profiles found.")

# ----------------- Scraper 5: Yellow Pages Scraper (yellow-page_scraper.py) -----------------
def fetch_yellow_pages(keyword, location="", page=1):
    businesses = []
    try:
        query = quote_plus(keyword)
        loc = quote_plus(location)
        url = f"https://www.yellowpages.com/search?search_terms={query}&geo_location_terms={loc}&page={page}"
        response = requests.get(url, headers=get_headers(), timeout=10)
        soup = BeautifulSoup(response.text, "html.parser")
        
        results = soup.find_all("div", class_="result")
        for r in results:
            name_tag = r.find("h2", class_="n")
            name = name_tag.get_text(strip=True) if name_tag else "Unknown"
            phone_tag = r.find("div", class_="phones")
            phone = phone_tag.get_text(strip=True) if phone_tag else "N/A"
            address_tag = r.find("div", class_="street-address")
            address = address_tag.get_text(strip=True) if address_tag else "N/A"
            website_tag = r.find("a", class_="track-visit-website")
            website = website_tag['href'] if website_tag else "N/A"
            emails = set()
            
            if website != "N/A":
                try:
                    resp = requests.get(website, headers=get_headers(), timeout=10)
                    emails.update(extract_emails(resp.text))
                except:
                    pass
            
            businesses.append({
                "Keyword": keyword,
                "Name": name,
                "Phone": phone,
                "Address": address,
                "Website": website,
                "Email": ", ".join(emails) if emails else "N/A"
            })
    except Exception as e:
        print(f"[!] Error fetching page: {e}")
    return businesses

def run_yellow_pages_scraper():
    print("\n--- Yellow Pages Business Scraper ---")
    choice = input("Input keywords manually (1) or from a file (2)? [1/2]: ").strip()

    if choice == "1":
        keywords = input("Enter keywords separated by comma: ").strip().split(",")
        keywords = [kw.strip() for kw in keywords if kw.strip()]
    elif choice == "2":
        file_path = input("Enter path to keywords file: ").strip()
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                keywords = [line.strip() for line in f if line.strip()]
        except:
            print("[!] Could not read file.")
            return
    else:
        print("[!] Invalid choice. Exiting.")
        return
        
    location = input("Enter location/city (optional): ").strip()
    pages_input = input("Number of pages per keyword (default 3): ").strip()
    pages = int(pages_input) if pages_input.isdigit() else 3
    threads_input = input("Max threads (default 5): ").strip()
    max_threads = int(threads_input) if threads_input.isdigit() else 5
    
    all_businesses = []
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = []
        for keyword in keywords:
            for page in range(1, pages+1):
                futures.append(executor.submit(fetch_yellow_pages, keyword, location, page))
                
        for i, future in enumerate(as_completed(futures), start=1):
            businesses = future.result()
            all_businesses.extend(businesses)
            print(f"Scraped {i}/{len(futures)} pages | Total businesses found: {len(all_businesses)}", end="\r")
            time.sleep(1)

    if all_businesses:
        output_file = "yellow_pages_with_emails.csv"
        with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = ["Keyword", "Name", "Phone", "Address", "Website", "Email"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for business in all_businesses:
                writer.writerow(business)
        print(f"\n[+] Total businesses found: {len(all_businesses)}")
        print(f"[+] Results saved to {output_file}")
    else:
        print("[!] No businesses found.")

# ----------------- Main Menu -----------------
def main():
    print_banner()
    while True:
        print("\n=== Multi-Scraper Tool ===")
        print("1. General Website/URL Email Scraper")
        print("2. Google/Bing/Yahoo/DDG Email Scraper (by keyword)")
        print("3. Facebook Public Contacts Scraper")
        print("4. LinkedIn Name & URL Extractor")
        print("5. Yellow Pages Business Scraper")
        print("6. Exit")
        
        choice = input("Select a scraper to run [1-6]: ").strip()
        
        if choice == "1":
            run_general_scraper()
        elif choice == "2":
            run_google_scraper()
        elif choice == "3":
            run_facebook_scraper()
        elif choice == "4":
            run_linkedin_scraper()
        elif choice == "5":
            run_yellow_pages_scraper()
        elif choice == "6":
            print("Exiting...")
            break
        else:
            print("[!] Invalid choice, try again.")

if __name__ == "__main__":
    main()