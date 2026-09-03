"""Optional direct delivery to a Telegram chat.

Added because neither of Claude's own delivery surfaces proved reliable for
this workflow: push notifications from the nightly Routine were confirmed to
fail silently on two separate real, successful runs (29 Aug and 1 Sep 2026),
and the Claude mobile app's own image viewer has no way to save or share a
photo it receives. Telegram has neither limitation - a bot message is a
normal photo message, forwardable to WhatsApp with the phone's native share
sheet like any other photo.

Enable by setting two environment variables on the cloud environment (not in
this repo - never commit these):

    TELEGRAM_BOT_TOKEN   from @BotFather after creating a bot with /newbot
    TELEGRAM_CHAT_ID     the numeric chat id of the person to message

See CLAUDE.md for the full one-time setup. Absent either variable, sending
is silently skipped - the existing Claude-session delivery (SendUserFile
plus the report pasted into the chat reply) is unaffected either way, so
Telegram is additive, never a replacement the pipeline depends on.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Optional

_API = "https://api.telegram.org/bot{token}/{method}"
_BOUNDARY = "----ipoWatchTelegramBoundary"
_MESSAGE_LIMIT = 4000  # Telegram's real cap is 4096; leave headroom.


class TelegramError(RuntimeError):
    """Raised on any failure talking to the Telegram Bot API."""


def configured() -> bool:
    """True when both required environment variables are present."""
    return bool(os.environ.get("TELEGRAM_BOT_TOKEN") and os.environ.get("TELEGRAM_CHAT_ID"))


def send_report(image_path: str, report_text: str) -> None:
    """Send the creative as a photo, then the full report as its own message.

    The report is sent as a separate message rather than a photo caption
    because Telegram caps captions at 1024 characters and a busy day's
    report regularly runs longer; a separate message has a 4096-character
    limit instead, which the report fits under except on the busiest days,
    where it is chunked.

    Raises TelegramError on failure. The caller must not let that affect the
    run's own exit code - Telegram is a delivery channel, not part of the
    data-accuracy contract, so a Telegram outage must never be reported the
    same way as a bad or unverifiable number.
    """
    if not configured():
        raise TelegramError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set")

    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    date_label = os.path.basename(image_path).replace("ipo-watch-", "").replace(".png", "")

    with open(image_path, "rb") as fh:
        image_bytes = fh.read()

    _post("sendPhoto", {"chat_id": chat_id, "caption": f"\U0001F4CA IPO Watch — {date_label}"},
          files={"photo": (os.path.basename(image_path), image_bytes, "image/png")})

    for chunk in _chunk(report_text, _MESSAGE_LIMIT):
        _post("sendMessage", {"chat_id": chat_id, "text": chunk})


def lookup_chat_id(bot_token: str) -> Optional[int]:
    """Return the chat id of whoever most recently messaged this bot.

    Used only during one-time setup, so the user does not have to hunt for
    their own numeric Telegram id by hand. Requires the user to have sent
    the bot at least one message first - Telegram bots cannot see a user
    until the user has initiated contact.
    """
    url = _API.format(token=bot_token, method="getUpdates")
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode())
    except Exception as exc:  # noqa: BLE001
        raise TelegramError(f"Could not reach Telegram: {exc}") from exc
    if not payload.get("ok"):
        raise TelegramError(f"Telegram API error: {payload}")
    results = payload.get("result") or []
    if not results:
        return None
    latest = results[-1]
    msg = latest.get("message") or latest.get("channel_post") or {}
    chat = msg.get("chat") or {}
    return chat.get("id")


def _post(method: str, fields: dict, files: Optional[dict] = None) -> dict:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    url = _API.format(token=token, method=method)
    if files:
        body = _multipart_body(fields, files)
        headers = {"Content-Type": f"multipart/form-data; boundary={_BOUNDARY}"}
    else:
        body = urllib.parse.urlencode(fields).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
    except Exception as exc:  # noqa: BLE001
        raise TelegramError(f"Telegram request failed ({method}): {exc}") from exc
    if not payload.get("ok"):
        raise TelegramError(f"Telegram API error ({method}): {payload}")
    return payload


def _multipart_body(fields: dict, files: dict) -> bytes:
    parts = []
    for name, value in fields.items():
        parts.append(
            f"--{_BOUNDARY}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    for name, (filename, content, content_type) in files.items():
        parts.append(
            f"--{_BOUNDARY}\r\n"
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n".encode()
            + content + b"\r\n"
        )
    parts.append(f"--{_BOUNDARY}--\r\n".encode())
    return b"".join(parts)


def _chunk(text: str, size: int):
    for i in range(0, len(text), size):
        yield text[i:i + size]
