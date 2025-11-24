import requests
from bs4 import BeautifulSoup
import re
import csv
import os
from urllib.parse import urljoin

# Regex for phone numbers
phone_regex = r"(?:\+?\d{1,4}[\s\-]?)?(?:\(?\d{2,4}\)?[\s\-]?)?\d{3,4}[\s\-]?\d{3,4}"

# Detect next page link based on common keywords
def find_next_page(soup, current_url):
    keywords = ["next", ">", "older", "more"]
    links = soup.find_all("a")
    for a in links:
        text = (a.get_text() or "").strip().lower()
        href = a.get("href")
        if not href:
            continue
        if any(k in text for k in keywords):
            return urljoin(current_url, href)
    return None

# Scrape phone numbers from a single page
def scrape_phones(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        phones = set()

        # 1️⃣ <a href="tel:...">
        for a in soup.find_all("a", href=True):
            if a['href'].startswith("tel:"):
                phones.add(a['href'].replace("tel:", "").strip())

        # 2️⃣ Text on page
        text_phones = re.findall(phone_regex, soup.get_text())
        for p in text_phones:
            phones.add(p.strip())

        return list(phones), soup

    except Exception as e:
        print(f"❌ Failed to scrape {url}: {e}")
        return [], None

# Save results to CSV on Desktop
def save_csv(results):
    desktop = os.path.join(os.path.expanduser("~"), "Desktop")
    save_path = os.path.join(desktop, "phones_scraped.csv")
    with open(save_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["URL", "Phone Number"])
        writer.writerows(results)
    print(f"\n✔ All results saved to: {save_path}")

# ---------------- MAIN ----------------
if __name__ == "__main__":
    file_path = input("Enter path to file containing URLs: ")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip()]
    except Exception as e:
        print(f"❌ Could not read file: {e}")
        exit()

    try:
        max_numbers = int(input("Enter the number of phone numbers to scrape: "))
    except:
        print("❌ Invalid number.")
        exit()

    all_results = []
    all_numbers = set()
    total_count = 0

    print("\n🚀 Starting scraping...\n")

    try:
        for url in urls:
            current_url = url
            while current_url and total_count < max_numbers:
                phones, soup = scrape_phones(current_url)
                for p in phones:
                    if p not in all_numbers:
                        all_numbers.add(p)
                        all_results.append([current_url, p])
                        total_count += 1
                        print(f"[{total_count}] {p} from {current_url}")
                        if total_count >= max_numbers:
                            break

                # Go to next page
                if soup:
                    next_url = find_next_page(soup, current_url)
                    if not next_url or next_url == current_url:
                        break
                    current_url = next_url
                else:
                    break
            if total_count >= max_numbers:
                break

    except KeyboardInterrupt:
        print("\n⛔ Scraping interrupted by user (Ctrl+C)")

    finally:
        save_csv(all_results)
