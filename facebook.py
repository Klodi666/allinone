#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import argparse

def main(username, password):
    # Set up the Selenium WebDriver
    driver = webdriver.Firefox()

    # Log into Facebook
    driver.get("https://www.facebook.com/login.php")
    username_field = driver.find_element(By.NAME, "email")
    password_field = driver.find_element(By.NAME, "pass")
    username_field.send_keys(username)
    password_field.send_keys(password)
    login_button = driver.find_element(By.NAME, "login")
    login_button.click()

    # Wait for the login process to complete
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//div[@id='content']")))

    # Retrieve your friends' list
    friends_list_url = "https://www.facebook.com/friends"
    driver.get(friends_list_url)

    # Extract your friends' email addresses and phone numbers
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    friends = soup.find_all('div', {'class': '_4bl7'})

    for friend in friends:
        name = friend.find('span', {'class': '_1k6a'}).text.strip()
        email_pattern = r'[\w\.-]+@[\w\.-]+'
        email_match = re.search(email_pattern, friend.text)
        if email_match:
            email = email_match.group()
        else:
            email = None

        phone_pattern = r'\+?\d{1,4}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}'
        phone_match = re.search(phone_pattern, friend.text)
        if phone_match:
            phone = phone_match.group()
        else:
            phone = None

        print(f"Name: {name}")
        print(f"Email: {email}")
        print(f"Phone: {phone}")

    # Close the WebDriver
    driver.quit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Facebook Friend Scraper")
    parser.add_argument("username", help="Your Facebook username")
    parser.add_argument("password", help="Your Facebook password")
    args = parser.parse_args()
    main(args.username, args.password)