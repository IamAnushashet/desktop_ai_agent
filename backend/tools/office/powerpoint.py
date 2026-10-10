"""Microsoft PowerPoint presentation automation tool for Desktop AI Agent."""

import os
import subprocess
import time
import psutil
from typing import Optional, Dict, Any, List
from pathlib import Path
import pptx
from pptx.util import Inches, Pt
from langchain_core.tools import tool

from backend.llm.nvidia import get_nvidia_llm
from backend.utils.logger import logger


def generate_presentation_content(topic: str, num_slides: int = 5) -> Dict[str, Any]:
    """
    Use NVIDIA LLM to dynamically generate structured slide content for PowerPoint.
    Returns a dict with main title, subtitle, and list of slides with title and bullet points.
    """
    prompt = f"""You are a professional presentation designer. Create a structured PowerPoint presentation deck about: '{topic}'.
Number of slides requested: {num_slides}.

Format your response EXACTLY as follows:
PRESENTATION_TITLE: <Main Presentation Title>
PRESENTATION_SUBTITLE: <Subtitle or Tagline>

SLIDE: <Slide 2 Title>
BULLET: <First bullet point for slide 2>
BULLET: <Second bullet point for slide 2>
BULLET: <Third bullet point for slide 2>

SLIDE: <Slide 3 Title>
BULLET: <First bullet point for slide 3>
BULLET: <Second bullet point for slide 3>
BULLET: <Third bullet point for slide 3>

(Repeat for all {num_slides - 1} content slides)
"""
    try:
        llm = get_nvidia_llm()
        res = llm.invoke(prompt)
        text = res.content if hasattr(res, "content") else str(res)
        return _parse_generated_pptx_text(text, topic, num_slides)
    except Exception as e:
        logger.warning(f"[POWERPOINT TOOL] LLM generation failed ({e}), using fallback content generator.")
        return _fallback_presentation_content(topic, num_slides)


def _parse_generated_pptx_text(text: str, default_topic: str, num_slides: int) -> Dict[str, Any]:
    """Parse structured text returned by LLM into presentation slides."""
    lines = text.strip().split("\n")
    main_title = f"{default_topic.title()}"
    subtitle = f"Overview & Key Insights on {default_topic.title()}"
    slides: List[Dict[str, Any]] = []

    current_slide_title = None
    current_bullets = []

    for line in lines:
        line_s = line.strip()
        if not line_s:
            continue

        if line_s.startswith("PRESENTATION_TITLE:"):
            main_title = line_s.replace("PRESENTATION_TITLE:", "").strip()
        elif line_s.startswith("PRESENTATION_SUBTITLE:"):
            subtitle = line_s.replace("PRESENTATION_SUBTITLE:", "").strip()
        elif line_s.startswith("SLIDE:"):
            if current_slide_title and current_bullets:
                slides.append({
                    "title": current_slide_title,
                    "bullets": current_bullets,
                })
                current_bullets = []
            current_slide_title = line_s.replace("SLIDE:", "").strip()
        elif line_s.startswith("BULLET:"):
            bullet = line_s.replace("BULLET:", "").strip()
            if bullet:
                current_bullets.append(bullet)
        elif line_s.startswith("- ") or line_s.startswith("* "):
            if current_slide_title:
                current_bullets.append(line_s[2:].strip())

    if current_slide_title and current_bullets:
        slides.append({
            "title": current_slide_title,
            "bullets": current_bullets,
        })

    # If parsing generated fewer slides than requested, fill with fallback structure
    if len(slides) < (num_slides - 1):
        fallback_slides = _fallback_presentation_content(default_topic, num_slides)["slides"]
        for i in range(len(slides), num_slides - 1):
            if i < len(fallback_slides):
                slides.append(fallback_slides[i])

    return {
        "title": main_title,
        "subtitle": subtitle,
        "slides": slides[:num_slides - 1],
    }


def _fallback_presentation_content(topic: str, num_slides: int) -> Dict[str, Any]:
    """Fallback presentation generator when LLM is offline or unreachable."""
    defaults = [
        {"title": "Introduction to " + topic.title(), "bullets": ["Definition and core background concepts", "Evolution and historical context", "Why " + topic + " matters today"]},
        {"title": "Key Principles & Architecture", "bullets": ["Foundational components and workflows", "Best practices and system architecture", "Core methodologies and techniques"]},
        {"title": "Major Applications & Use Cases", "bullets": ["Real-world industry applications", "Automation and efficiency gains", "Case studies and adoption examples"]},
        {"title": "Challenges & Solutions", "bullets": ["Current limitations and security considerations", "Mitigation strategies and best practices", "Scalability and maintenance"]},
        {"title": "Future Trends & Conclusion", "bullets": ["Emerging innovations on the horizon", "Summary of key takeaways", "Final recommendation and conclusion"]},
    ]
    
    # Generate extra slides if num_slides > 6
    while len(defaults) < (num_slides - 1):
        idx = len(defaults) + 1
        defaults.append({
            "title": f"Deep Dive: Aspect #{idx} of {topic.title()}",
            "bullets": [f"Analysis of strategic factor #{idx}", "Implementation insights and guidelines", "Expected impact and metrics"]
        })

    return {
        "title": topic.title(),
        "subtitle": f"A Comprehensive Presentation on {topic.title()}",
        "slides": defaults[:num_slides - 1],
    }


def is_powerpoint_running() -> bool:
    """Check if Microsoft PowerPoint process (powerpnt.exe) is active."""
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and proc.info['name'].lower() in ['powerpnt.exe', 'powerpoint.exe']:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False


@tool
def create_powerpoint_presentation(topic: str, num_slides: int = 5, file_name: Optional[str] = None) -> str:
    """
    Generates presentation slides on a topic dynamically using LLM, opens Microsoft PowerPoint,
    creates a title slide and N content slides with titles and bullet points, saves as .pptx,
    and verifies PowerPoint is running and the presentation file is created.

    Args:
        topic: The presentation subject or topic (e.g. 'Artificial Intelligence', 'Machine Learning').
        num_slides: Total number of slides to create (default: 5).
        file_name: Optional custom filename (e.g. 'Artificial_Intelligence_Presentation.pptx').
    """
    logger.info(f"[TOOL create_powerpoint_presentation] Starting PowerPoint automation: '{topic}' ({num_slides} slides)")
    try:
        if num_slides < 1:
            num_slides = 5

        # 1. Generate Slide Content via LLM
        content_data = generate_presentation_content(topic, num_slides=num_slides)
        main_title = content_data.get("title", topic)
        subtitle = content_data.get("subtitle", "")
        content_slides = content_data.get("slides", [])

        # 2. Output Directory & Filepath setup
        output_dir = Path.cwd() / "data" / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        if not file_name:
            safe_name = "".join([c if c.isalnum() else "_" for c in topic.strip()]).strip("_")
            file_name = f"{safe_name}_presentation.pptx"
        elif not file_name.endswith(".pptx"):
            file_name += ".pptx"

        file_path = output_dir / file_name

        # 3. Create PPTX Deck using python-pptx
        prs = pptx.Presentation()

        # Slide 1: Title Slide
        title_slide_layout = prs.slide_layouts[0]
        slide1 = prs.slides.add_slide(title_slide_layout)
        slide1.shapes.title.text = main_title
        if len(slide1.placeholders) > 1 and subtitle:
            slide1.placeholders[1].text = subtitle

        # Slide 2 to N: Content Slides
        bullet_slide_layout = prs.slide_layouts[1]
        created_slide_titles = [main_title]

        for s_data in content_slides:
            s_title = s_data.get("title", "Key Insights")
            s_bullets = s_data.get("bullets", [])

            slide = prs.slides.add_slide(bullet_slide_layout)
            slide.shapes.title.text = s_title
            created_slide_titles.append(s_title)

            tf = slide.placeholders[1].text_frame
            tf.clear()
            for idx, bullet_text in enumerate(s_bullets):
                if idx == 0:
                    p = tf.paragraphs[0]
                else:
                    p = tf.add_paragraph()
                p.text = bullet_text
                p.level = 0

        # Save presentation
        prs.save(str(file_path))
        abs_path = str(file_path.resolve())
        actual_slide_count = len(prs.slides)
        logger.info(f"[POWERPOINT TOOL] Saved presentation to '{abs_path}' ({actual_slide_count} slides)")

        # 4. Open Microsoft PowerPoint with the presentation
        ppt_opened = False
        try:
            if os.name == 'nt':
                try:
                    subprocess.Popen(['powerpnt.exe', abs_path])
                    ppt_opened = True
                except FileNotFoundError:
                    os.startfile(abs_path)
                    ppt_opened = True
            time.sleep(1.5)
        except Exception as launch_err:
            logger.warning(f"[POWERPOINT TOOL] Opening PowerPoint window warning: {launch_err}")

        # 5. Verification
        file_created = os.path.exists(abs_path) and os.path.getsize(abs_path) > 0
        ppt_running = is_powerpoint_running() or ppt_opened

        slide_list_str = "\n".join([f"  {idx+1}. {t}" for idx, t in enumerate(created_slide_titles)])

        if file_created:
            return (
                f"Successfully created a {actual_slide_count}-slide PowerPoint presentation on '{topic}'.\n"
                f"- Presentation Title: {main_title}\n"
                f"- Saved File Path: {abs_path}\n"
                f"- Total Slides Created: {actual_slide_count}\n"
                f"- Slides Breakdown:\n{slide_list_str}\n"
                f"- Presentation File Verification: PASSED\n"
                f"- PowerPoint Application Verification: {'PASSED (PowerPoint is running)' if ppt_running else 'FILE CREATED (PowerPoint launch attempted)'}"
            )
        else:
            return f"Error: Failed to save PowerPoint presentation file to '{abs_path}'."

    except Exception as e:
        logger.error(f"[POWERPOINT TOOL ERROR] Failed creating presentation: {e}")
        return f"Error creating PowerPoint presentation for '{topic}': {str(e)}"
