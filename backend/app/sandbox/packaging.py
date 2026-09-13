"""Packaging utilities for generating release ZIP packages."""

import io
import json
import zipfile
from typing import Any, Dict, Optional


def create_release_zip(
    code_files: Dict[str, str],
    patches: Dict[str, str],
    audit_summary: Optional[Dict[str, Any]],
    session_id: str
) -> bytes:
    """Creates an in-memory ZIP archive containing source code, patches, and audit summary."""
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Source code files
        for filename, content in code_files.items():
            zf.writestr(f"src/{filename}", content)
            
        # 2. Security patches
        for filename, patch_content in patches.items():
            zf.writestr(f"patches/{filename}.patch", patch_content)
            
        # 3. Audit summary (JSON & Markdown)
        if audit_summary:
            zf.writestr("audit_summary.json", json.dumps(audit_summary, indent=2))
            
            md_lines = [
                "# TARA Release Audit Summary",
                f"**Session ID:** `{session_id}`",
                f"**Completed At:** {audit_summary.get('completed_at', 'N/A')}",
                "",
                "## Execution Timeline",
            ]
            for item in audit_summary.get("timeline", []):
                md_lines.append(f"- **{item.get('phase', 'Phase')}**: {item.get('status', '')}")
                
            md_lines.extend(["", "## Key Architecture & Design Decisions"])
            for decision in audit_summary.get("key_decisions", []):
                md_lines.append(f"- {decision}")
                
            md_lines.extend(["", "## Unresolved Risks & Recommendations"])
            for risk in audit_summary.get("unresolved_risks", []):
                md_lines.append(f"- [WARNING] {risk}")
                
            zf.writestr("AUDIT_SUMMARY.md", "\n".join(md_lines) + "\n")
            
    zip_buffer.seek(0)
    return zip_buffer.getvalue()
