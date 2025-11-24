from twilio.rest import Client

# ------------------- CONFIG -------------------
ACCOUNT_SID = "AC48105203c512f43463db547c671d84c9"
AUTH_TOKEN = "abcdef1234567890abcdef1234567890"  # Replace with your real token
FROM_NUMBER = "+15551234567"  # Your Twilio phone number (not Messaging Service for testing)
# ---------------------------------------------

def send_sms(to_number, message_text):
    try:
        client = Client(ACCOUNT_SID, AUTH_TOKEN)
        message = client.messages.create(
            body=message_text,
            from_=FROM_NUMBER,
            to=to_number
        )
        print(f"✔ SMS sent to {to_number} | SID: {message.sid}")
    except Exception as e:
        print(f"❌ Failed to send SMS to {to_number}: {e}")

# ------------------- MAIN --------------------
if __name__ == "__main__":
    to_number = input("Enter phone number to send SMS (with country code, e.g. +355699149691): ")
    message_text = input("Enter SMS text: ")
    send_sms(to_number, message_text)
