"""
Migration prompt generator — reads an export directory and produces
a self-contained prompt for recreating account structure in a new Claude account.
"""

import json
from pathlib import Path

from app.utils import sanitize_filename


def generate_migration_prompt(export_dir: str) -> str:
    export_path = Path(export_dir)

    # Load projects
    projects = []
    projects_file = export_path / "projects.json"
    if projects_file.exists():
        with open(projects_file, "r", encoding="utf-8") as f:
            projects = json.load(f)

    # Load conversations index
    conversations = []
    convs_file = export_path / "conversations.json"
    if convs_file.exists():
        with open(convs_file, "r", encoding="utf-8") as f:
            conversations = json.load(f)

    lines = []

    # --- Header ---
    lines.append("# Claude Account Migration")
    lines.append("")
    lines.append("I'm migrating from another Claude account. Below is my complete")
    lines.append("account structure — memory, projects, knowledge documents, and")
    lines.append("conversation history. Please help me recreate this setup on this")
    lines.append("new account.")
    lines.append("")

    # --- Memory ---
    memory_file = export_path / "memory.md"
    if memory_file.exists():
        memory_text = memory_file.read_text(encoding="utf-8")
        if memory_text.startswith("# Claude Memory"):
            memory_text = memory_text.split("\n", 2)[-1].strip()
        lines.append("## Memory from Previous Account")
        lines.append("")
        lines.append("Below is my complete memory from the previous account. Please")
        lines.append("internalize all of this as your memory about me — this is who")
        lines.append("I am, what I work on, and what we've discussed.")
        lines.append("")
        lines.append(memory_text)
        lines.append("")

    # --- Instructions ---
    lines.append("## What I Need You To Do")
    lines.append("")
    lines.append("1. **Absorb the memory above** as context about me")
    lines.append("2. **Create these projects** with their names and descriptions")
    lines.append("3. **Note the knowledge documents** listed below — I will upload")
    lines.append("   them as project knowledge files. The full content is included")
    lines.append("   so you have context even before I upload them.")
    lines.append("4. **Review the conversation summaries** so you have context about")
    lines.append("   what we've discussed previously.")
    lines.append("")

    # --- Projects ---
    lines.append("## Projects")
    lines.append("")
    if projects:
        for p in projects:
            name = p.get("name", "Untitled")
            desc = p.get("description", "")
            is_private = p.get("is_private", True)
            created = p.get("created_at", "")[:10]
            lines.append(f"### {name}")
            lines.append(f"- **Description:** {desc or '(none)'}")
            lines.append(f"- **Private:** {is_private}")
            lines.append(f"- **Created:** {created}")
            lines.append("")

            proj_dir_name = sanitize_filename(name, 60)
            knowledge_dir = export_path / proj_dir_name / "knowledge"
            if knowledge_dir.is_dir():
                doc_files = sorted(knowledge_dir.iterdir())
                if doc_files:
                    lines.append(f"#### Knowledge Documents ({len(doc_files)} files)")
                    lines.append("")
                    for doc_path in doc_files:
                        lines.append(f"**`{doc_path.name}`**")
                        lines.append("")
                        try:
                            content = doc_path.read_text(encoding="utf-8")
                            lines.append("<details>")
                            lines.append(f"<summary>View content ({len(content)} chars)</summary>")
                            lines.append("")
                            lines.append(content)
                            lines.append("")
                            lines.append("</details>")
                        except Exception:
                            lines.append("*(content could not be read)*")
                        lines.append("")
            lines.append("---")
            lines.append("")
    else:
        lines.append("*(No projects found)*")
        lines.append("")

    # --- Conversation History ---
    lines.append("## Conversation History")
    lines.append("")
    lines.append("Summary of past conversations for context. Grouped by project.")
    lines.append("")

    proj_uuid_to_name = {p["uuid"]: p["name"] for p in projects}
    grouped: dict[str, list] = {"(No Project)": []}
    for p in projects:
        grouped[p["name"]] = []
    for conv in conversations:
        proj_uuid = conv.get("project_uuid")
        if proj_uuid and proj_uuid in proj_uuid_to_name:
            grouped.setdefault(proj_uuid_to_name[proj_uuid], []).append(conv)
        else:
            grouped["(No Project)"].append(conv)

    for group_name, convs in grouped.items():
        if not convs:
            continue
        lines.append(f"### {group_name}")
        lines.append("")
        lines.append("| # | Date | Model | Title | Summary |")
        lines.append("|---|------|-------|-------|---------|")
        for i, c in enumerate(convs, 1):
            date = c.get("created_at", "")[:10]
            model = c.get("model", "?")
            model_short = (
                model.replace("claude-", "")
                .replace("-20250929", "")
                .replace("-20251001", "")
                .replace("-20251101", "")
            )
            name = c.get("name", "Untitled").replace("|", "/")
            summary = (c.get("summary", "") or "").replace("|", "/").replace("\n", " ")[:150]
            lines.append(f"| {i} | {date} | {model_short} | {name} | {summary} |")
        lines.append("")

    # --- Footer ---
    lines.append("---")
    lines.append("")
    lines.append("*Generated by [claudexit](https://github.com/Rahul-999-alpha/claudexit)*")

    return "\n".join(lines)
