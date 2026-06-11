from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import List, Dict, Any


def render_markdown(messages: List[Dict[str, Any]], session_title: str = "Chat Export") -> str:
    lines = [f"# {session_title}\n"]
    lines.append(f"**Exported:** {datetime.now(timezone.utc).isoformat()}\n")
    lines.append("---\n")
    for msg in messages:
        role_icon = "🧑" if msg["role"] == "user" else "🤖"
        lines.append(f"### {role_icon} {msg['role'].title()}\n")
        lines.append(f"{msg['content']}\n")
        if msg.get("citations"):
            lines.append(f"*Citations: {len(msg['citations'])}*\n")
        lines.append("---\n")
    return "\n".join(lines)


def render_json(messages: List[Dict[str, Any]]) -> str:
    return json.dumps(
        {"messages": messages, "exported_at": datetime.now(timezone.utc).isoformat()},
        indent=2,
    )


def render_pdf(messages: List[Dict[str, Any]], session_title: str = "Chat Export") -> bytes:
    try:
        from weasyprint import HTML
    except ImportError:
        raise RuntimeError("weasyprint is required for PDF export")
    md = render_markdown(messages, session_title)
    html = f"<html><body><pre>{md}</pre></body></html>"
    return HTML(string=html).write_pdf()
