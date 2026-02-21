"""
Deliver node — write files, send email, create Notion page.
"""

import json
import logging
import os
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from competitive_intel.config import (
    FINAL_DIR,
    NOTIFY_EMAIL,
    NOTION_API_KEY,
    NOTION_DATABASE_ID,
    today_str,
)
from competitive_intel.state import PipelineState

log = logging.getLogger(__name__)

_NOTION_BLOCK_LIMIT = 100  # Notion API max blocks per request


def deliver_node(state: PipelineState) -> dict[str, Any]:
    """
    Write brief and metadata to disk; optionally send email and create Notion page.
    Updates state["metadata"] with delivery status.
    """
    brief = state.get("brief") or state.get("final_brief") or ""
    feedback = state.get("feedback")
    research = state.get("research") or []
    date = today_str()

    metadata: dict[str, Any] = {
        "date": date,
        "competitors_researched": [r.get("company", "unknown") for r in research],
        "num_competitors": len(research),
        "approved": feedback.get("approved", False) if feedback else False,
        "quality_score": feedback.get("overall_score", 0) if feedback else 0,
        "brief_length_chars": len(brief),
        "email_sent": False,
        "notion_created": False,
    }

    # 1. Write brief to files/final/{date}_intelligence_brief.md
    try:
        brief_path = FINAL_DIR / f"{date}_intelligence_brief.md"
        brief_path.write_text(brief, encoding="utf-8")
        metadata["brief_path"] = str(brief_path)
        log.info("Wrote brief: %s", brief_path)
    except Exception as exc:
        log.warning("Failed to write brief: %s", exc)
        metadata["brief_error"] = str(exc)

    # 2. Send email (SMTP)
    if NOTIFY_EMAIL and brief:
        try:
            _send_email(brief, date, metadata)
            metadata["email_sent"] = True
            log.info("Email sent to %s", NOTIFY_EMAIL)
        except Exception as exc:
            log.warning("Email delivery failed: %s", exc)
            metadata["email_error"] = str(exc)

    # 3. Create Notion page
    if NOTION_API_KEY and NOTION_DATABASE_ID and brief:
        try:
            _create_notion_page(brief, date)
            metadata["notion_created"] = True
            log.info("Notion page created")
        except Exception as exc:
            log.warning("Notion creation failed: %s", exc)
            metadata["notion_error"] = str(exc)

    # 4. Write metadata LAST so it includes email/notion status
    try:
        meta_path = FINAL_DIR / f"{date}_metadata.json"
        meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        log.info("Wrote metadata: %s", meta_path)
    except Exception as exc:
        log.warning("Failed to write metadata: %s", exc)

    return {"metadata": metadata, "final_brief": brief}


def _markdown_to_html(md: str) -> str:
    """Convert a markdown brief to simple HTML for email clients."""
    lines = md.split("\n")
    html_lines = []
    for line in lines:
        if line.startswith("### "):
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("- ") or line.startswith("* "):
            html_lines.append(f"<li>{line[2:]}</li>")
        elif line.strip() == "---":
            html_lines.append("<hr>")
        elif line.strip() == "":
            html_lines.append("<br>")
        else:
            line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", line)
            html_lines.append(f"<p>{line}</p>")
    return "\n".join(html_lines)


def _send_email(brief: str, date: str, metadata: dict) -> None:
    """Send brief via SMTP with plain-text and HTML alternatives."""
    host = os.environ.get("SMTP_HOST", "localhost")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    from_addr = os.environ.get("SMTP_FROM", user or "noreply@local")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Competitive Intelligence Brief — {date}"
    msg["From"] = from_addr
    msg["To"] = NOTIFY_EMAIL

    plain_body = (
        f"Competitive Intelligence Brief for {date}\n\n"
        f"Quality score: {metadata.get('quality_score', 'N/A')}\n\n"
        f"---\n\n{brief}"
    )
    html_body = (
        f"<html><body>"
        f"<p><strong>Competitive Intelligence Brief for {date}</strong><br>"
        f"Quality score: {metadata.get('quality_score', 'N/A')}</p>"
        f"<hr>"
        f"{_markdown_to_html(brief)}"
        f"</body></html>"
    )

    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(host, port) as server:
        if user and password:
            server.starttls()
            server.login(user, password)
        server.sendmail(from_addr, [NOTIFY_EMAIL], msg.as_string())


def _build_notion_blocks(brief: str) -> list[dict]:
    """Convert markdown brief lines into Notion block objects."""
    blocks = []
    for line in brief.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": stripped[4:]}}]},
            })
        elif stripped.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": stripped[3:]}}]},
            })
        elif stripped.startswith("# "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {"rich_text": [{"type": "text", "text": {"content": stripped[2:]}}]},
            })
        else:
            # Notion rich_text blocks have a 2000-char limit per text object
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": stripped[:2000]}}]},
            })
    return blocks


def _create_notion_page(brief: str, date: str) -> None:
    """Create a page in the configured Notion database, paginating blocks if needed."""
    from notion_client import Client

    client = Client(auth=NOTION_API_KEY)
    title = f"Competitive Intel Brief — {date}"
    content_blocks = _build_notion_blocks(brief)

    # Create page with first batch (Notion API limit: 100 blocks per request)
    page = client.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties={
            "title": {"title": [{"text": {"content": title}}]},
        },
        children=content_blocks[:_NOTION_BLOCK_LIMIT],
    )

    # Append remaining blocks in chunks to avoid the 100-block API limit
    remaining = content_blocks[_NOTION_BLOCK_LIMIT:]
    if remaining:
        page_id = page["id"]
        log.info(
            "Notion: appending %d additional blocks in chunks of %d",
            len(remaining),
            _NOTION_BLOCK_LIMIT,
        )
        for i in range(0, len(remaining), _NOTION_BLOCK_LIMIT):
            chunk = remaining[i: i + _NOTION_BLOCK_LIMIT]
            client.blocks.children.append(block_id=page_id, children=chunk)
