import smtplib
import ssl
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List
from scrapers.base import Listing


def send_alert(listings: List[Listing]) -> None:
    """Stuur een e-mail met nieuwe woningaanbiedingen."""
    sender = os.environ["GMAIL_ADDRESS"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ["RECIPIENT_EMAIL"]

    subject = f"🏠 {len(listings)} nieuwe woning(en) in Amsterdam"

    text_parts = [f"{len(listings)} nieuwe woning(en) gevonden:\n"]
    html_parts = [
        "<html><body>",
        f"<h2>{len(listings)} nieuwe woning(en) gevonden</h2>",
    ]

    for listing in listings:
        text_parts.append("-" * 50)
        text_parts.append(listing.summary())
        text_parts.append("")

        price_str = f"€{listing.price}/mnd" if listing.price else "prijs onbekend"
        bedrooms_str = f"{listing.bedrooms} slaapkamers" if listing.bedrooms else ""
        m2_str = f"{listing.m2} m²" if listing.m2 else ""
        details = " · ".join(filter(None, [price_str, bedrooms_str, m2_str, listing.neighborhood, listing.postcode]))

        html_parts.append(f"""
        <div style="border:1px solid #ddd;padding:12px;margin:8px 0;border-radius:4px;">
          <strong><a href="{listing.url}">{listing.title or listing.source}</a></strong><br>
          <span style="color:#555">{details}</span><br>
          <small style="color:#888">{listing.source}</small>
          {f'<br><small>Beschikbaar: {listing.available_from}</small>' if listing.available_from else ''}
        </div>""")

    html_parts.append("</body></html>")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText("\n".join(text_parts), "plain", "utf-8"))
    msg.attach(MIMEText("\n".join(html_parts), "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())

    print(f"E-mail verstuurd met {len(listings)} listing(s) naar {recipient}")
