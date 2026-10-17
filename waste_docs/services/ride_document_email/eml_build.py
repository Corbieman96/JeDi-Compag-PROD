from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from email.policy import SMTPUTF8


@dataclass(frozen=True)
class EmailAttachment:
    filename: str
    data: bytes
    maintype: str = "application"
    subtype: str = "pdf"


def build_eml_bytes(
    *,
    recipient_email: str,
    subject: str,
    body: str,
    attachments: list[EmailAttachment],
    from_email: str | None = None,
    reply_to: str | None = None,
) -> bytes:
    msg = EmailMessage(policy=SMTPUTF8)
    if from_email:
        msg["From"] = from_email
    if reply_to:
        msg["Reply-To"] = reply_to
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg["X-Unsent"] = "1"
    msg.set_content(body, charset="utf-8")
    for att in attachments:
        msg.add_attachment(
            att.data,
            maintype=att.maintype,
            subtype=att.subtype,
            filename=att.filename,
        )
    return msg.as_bytes()
