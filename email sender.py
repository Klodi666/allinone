import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import csv
import os

# ---------------- CONFIG ----------------
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "your_email@gmail.com"   # Your email
EMAIL_PASSWORD = "your_email_password"   # App password recommended for Gmail
# ----------------------------------------

# Function to send email
def send_email(to_address, subject, body):
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

# ---------------- MAIN ----------------
if __name__ == "__main__":
    # Option 1: List of recipients
    recipients = ["email1@example.com", "email2@example.com"]
    
    # Option 2: Read from CSV file (one email per line)
    # Uncomment this if using CSV
    # csv_file = os.path.join(os.path.expanduser("~"), "Desktop", "emails.csv")
    # recipients = []
    # with open(csv_file, newline='', encoding='utf-8') as f:
    #     reader = csv.reader(f)
    #     for row in reader:
    #         if row:  # skip empty rows
    #             recipients.append(row[0])

    subject = input("Enter email subject: ")
    body = input("Enter email body: ")

    for email in recipients:
        send_email(email, subject, body)
