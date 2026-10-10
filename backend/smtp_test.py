"""Manual SMTP probe. Run directly only when sending a test message is intended."""
import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    recipient = os.environ.get("SMTP_TEST_TO")
    if not recipient:
        raise RuntimeError("Set SMTP_TEST_TO before running the SMTP probe")
    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = recipient
    message["Subject"] = "CareerQuest SMTP test"
    message.set_content("It works.")
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"])) as connection:
        connection.starttls()
        connection.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        connection.send_message(message)
    print("SENT")


if __name__ == "__main__":
    main()
