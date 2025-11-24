import requests
from bs4 import BeautifulSoup
import re

def extract_email_from_linkedin(profile_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
    response = requests.get(profile_url, headers=headers)
    soup = BeautifulSoup(response.text, 'html.parser')

    # Find the email address in the profile
    email_pattern = r'[\w\.-]+@[\w\.-]+'
    email_match = re.search(email_pattern, soup.text)
    if email_match:
        return email_match.group()
    else:
        return None

# Example usage
profile_url = "https://www.linkedin.com/in/johndoe/"
email = extract_email_from_linkedin(profile_url)
if email:
    print(f"Email found: {email}")
else:
    print("No email found")