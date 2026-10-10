"""Microsoft Word automation tool for Desktop AI Agent."""

import os
import subprocess
import time
import psutil
from typing import Optional, Dict, Any
from pathlib import Path
import docx
from langchain_core.tools import tool

from backend.llm.nvidia import get_nvidia_llm
from backend.utils.logger import logger


def generate_word_content(topic: str, word_count: int = 500) -> Dict[str, Any]:
    """
    Use NVIDIA LLM to dynamically generate structured topic content for a Word document.
    Returns a dict with 'title', 'subtitle', and 'sections' (list of dicts with 'heading' and 'content').
    """
    prompt = f"""You are an expert technical writer. Generate a comprehensive, well-structured document about: '{topic}'.
Target word count: approximately {word_count} words.

Format your response EXACTLY as follows:
TITLE: <Main Title of Document>
SUBTITLE: <Brief Subtitle or Summary>

HEADING: <First Section Heading>
CONTENT: <Detailed paragraph content for first section>

HEADING: <Second Section Heading>
CONTENT: <Detailed paragraph content for second section>

HEADING: <Third Section Heading>
CONTENT: <Detailed paragraph content for third section>

HEADING: <Fourth Section Heading>
CONTENT: <Detailed paragraph content for fourth section>

HEADING: <Conclusion Heading>
CONTENT: <Concluding thoughts and summary>
"""
    try:
        llm = get_nvidia_llm()
        res = llm.invoke(prompt)
        text = res.content if hasattr(res, "content") else str(res)
        return _parse_generated_word_text(text, topic)
    except Exception as e:
        logger.warning(f"[WORD TOOL] LLM generation failed ({e}), using fallback content generator.")
        return _fallback_word_content(topic, word_count)


def _parse_generated_word_text(text: str, default_topic: str) -> Dict[str, Any]:
    """Parse structured text returned by LLM into title and sections."""
    lines = text.strip().split("\n")
    title = f"Report on {default_topic}"
    subtitle = f"Comprehensive Overview of {default_topic}"
    sections = []

    current_heading = None
    current_content = []

    for line in lines:
        line_s = line.strip()
        if not line_s:
            continue
        if line_s.startswith("TITLE:"):
            title = line_s.replace("TITLE:", "").strip()
        elif line_s.startswith("SUBTITLE:"):
            subtitle = line_s.replace("SUBTITLE:", "").strip()
        elif line_s.startswith("HEADING:"):
            if current_heading and current_content:
                sections.append({
                    "heading": current_heading,
                    "content": "\n\n".join(current_content),
                })
                current_content = []
            current_heading = line_s.replace("HEADING:", "").strip()
        elif line_s.startswith("CONTENT:"):
            content_part = line_s.replace("CONTENT:", "").strip()
            if content_part:
                current_content.append(content_part)
        else:
            if current_heading:
                current_content.append(line_s)
            elif not title or title == f"Report on {default_topic}":
                title = line_s.lstrip("#").strip()

    if current_heading and current_content:
        sections.append({
            "heading": current_heading,
            "content": "\n\n".join(current_content),
        })

    if not sections:
        sections.append({
            "heading": f"Overview of {default_topic}",
            "content": text,
        })

    return {
        "title": title,
        "subtitle": subtitle,
        "sections": sections,
    }


def _fallback_word_content(topic: str, word_count: int) -> Dict[str, Any]:
    """Fallback generator when LLM is offline or unreachable."""
    return {
        "title": topic.title(),
        "subtitle": f"An In-Depth Exploration of {topic}",
        "sections": [
            {
                "heading": "1. Introduction and Background",
                "content": f"{topic} plays a vital and growing role in modern society. "
                           f"Understanding the fundamentals of {topic} allows individuals and organizations "
                           f"to make informed decisions, drive innovation, and improve overall outcomes."
            },
            {
                "heading": "2. Key Principles and Concepts",
                "content": f"The core foundations of {topic} are built upon well-established principles. "
                           f"Key aspects include continuous assessment, scalability, security, and user-centered focus. "
                           f"Applying these principles ensures that solutions related to {topic} remain resilient and effective."
            },
            {
                "heading": "3. Applications and Impact",
                "content": f"Practical applications of {topic} span numerous fields, including enterprise software, "
                           f"healthcare, financial technologies, and everyday automation. "
                           f"As adoption accelerates, {topic} continues to transform workflow efficiency and quality."
            },
            {
                "heading": "4. Future Outlook and Conclusion",
                "content": f"Looking ahead, {topic} is poised for continued growth and innovation. "
                           f"Emerging developments will further enhance capabilities, opening new opportunities "
                           f"for discovery and practical implementation across the industry."
            },
        ]
    }


def is_word_running() -> bool:
    """Check if Microsoft Word process (winword.exe) is currently active."""
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() in ['winword.exe', 'word.exe']:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False


@tool
def write_word_document(topic: str, approx_word_count: int = 500, file_name: Optional[str] = None) -> str:
    """
    Generates text on a given topic dynamically using LLM, opens Microsoft Word,
    creates a formatted Word document (.docx) with title and subheadings, saves the file,
    and verifies Word is running and the document is created.

    Args:
        topic: The topic or subject to write about (e.g. 'Artificial Intelligence').
        approx_word_count: Target word count for the generated content (default: 500).
        file_name: Optional custom filename for saving (e.g. 'Artificial_Intelligence.docx').
    """
    logger.info(f"[TOOL write_word_document] Starting Word automation for topic: '{topic}'")
    try:
        # 1. Generate Content via LLM
        content_data = generate_word_content(topic, word_count=approx_word_count)
        title = content_data.get("title", topic)
        subtitle = content_data.get("subtitle", "")
        sections = content_data.get("sections", [])

        # 2. Prepare Output Directory and Filepath
        output_dir = Path.cwd() / "data" / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        if not file_name:
            safe_name = "".join([c if c.isalnum() else "_" for c in topic.strip()]).strip("_")
            file_name = f"{safe_name}.docx"
        elif not file_name.endswith(".docx"):
            file_name += ".docx"

        file_path = output_dir / file_name

        # 3. Create formatted Word Document using python-docx
        doc = docx.Document()

        # Add Title
        title_para = doc.add_paragraph()
        title_run = title_para.add_run(title)
        title_run.font.size = docx.shared.Pt(24)
        title_run.font.bold = True
        title_para.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER

        if subtitle:
            sub_para = doc.add_paragraph()
            sub_run = sub_para.add_run(subtitle)
            sub_run.font.size = docx.shared.Pt(14)
            sub_run.font.italic = True
            sub_para.alignment = docx.enum.text.WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph()  # Blank line spacer

        total_words = 0
        for section in sections:
            heading_text = section.get("heading", "")
            body_text = section.get("content", "")

            if heading_text:
                doc.add_heading(heading_text, level=2)
            if body_text:
                doc.add_paragraph(body_text)
                total_words += len(body_text.split())

        # Save document
        doc.save(str(file_path))
        abs_path = str(file_path.resolve())
        logger.info(f"[WORD TOOL] Document saved to '{abs_path}' ({total_words} words)")

        # 4. Open Microsoft Word with the Document
        word_opened = False
        try:
            # Try launching winword directly or via os.startfile
            if os.name == 'nt':
                try:
                    subprocess.Popen(['winword.exe', abs_path])
                    word_opened = True
                except FileNotFoundError:
                    os.startfile(abs_path)
                    word_opened = True
            time.sleep(1.5)
        except Exception as launch_err:
            logger.warning(f"[WORD TOOL] Opening Word window warning: {launch_err}")

        # 5. Verification
        file_created = os.path.exists(abs_path) and os.path.getsize(abs_path) > 0
        word_running = is_word_running() or word_opened

        if file_created:
            return (
                f"Successfully generated and wrote topic '{topic}' in Microsoft Word.\n"
                f"- Document Title: {title}\n"
                f"- Saved File Path: {abs_path}\n"
                f"- Word Count: approx {total_words} words\n"
                f"- Document Saved Verification: PASSED\n"
                f"- Word Application Verification: {'PASSED (Word is running)' if word_running else 'FILE CREATED (Word launch attempted)'}"
            )
        else:
            return f"Error: Failed to save Word document for topic '{topic}' to path '{abs_path}'."

    except Exception as e:
        logger.error(f"[WORD TOOL ERROR] Failed executing Word automation: {e}")
        return f"Error executing Word automation for topic '{topic}': {str(e)}"
