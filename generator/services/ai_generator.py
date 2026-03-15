"""
AI article generation using Claude claude-opus-4-6.

Two-phase approach:
  1. pick_topic_and_style()  — analyses source articles and selects a timely jewelry topic
  2. stream_generated_article() — streams a new article that mirrors the source style
"""
import json
import logging
from datetime import date
from typing import Generator

import anthropic

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-6"

# Current month/year context injected into every prompt
_TODAY = date.today()
_SEASON_DESC = {
    12: "winter holiday season", 1: "winter / new year", 2: "winter / Valentine's Day",
    3: "early spring", 4: "spring", 5: "late spring / Mother's Day",
    6: "early summer", 7: "summer", 8: "late summer",
    9: "early autumn", 10: "autumn", 11: "late autumn / holiday gifting season",
}.get(_TODAY.month, "spring")

_DATE_CONTEXT = f"{_TODAY.strftime('%B %Y')} ({_SEASON_DESC})"


def _build_articles_block(articles: list[dict]) -> str:
    """Format scraped articles into a readable block for Claude."""
    parts = []
    for i, art in enumerate(articles, 1):
        parts.append(
            f"--- Article {i}: {art['title']} ---\n"
            f"URL: {art['url']}\n\n"
            f"{art['text']}\n"
        )
    return "\n\n".join(parts)


def pick_topic_and_style(articles: list[dict], api_key: str) -> dict:
    """
    Make a non-streaming call to Claude to:
      - analyse the writing style of the source articles
      - select a relevant, on-trend jewelry topic for the current time of year

    Returns a dict with keys: topic, style_notes, tone, structure_notes
    """
    client = anthropic.Anthropic(api_key=api_key)

    articles_block = _build_articles_block(articles)

    system = (
        "You are an expert content strategist and jewelry industry analyst. "
        "You deeply understand writing styles, editorial tone, and what makes "
        "jewelry content resonate with readers. "
        "You always respond with valid JSON only — no markdown, no preamble."
    )

    user = f"""Analyze the following {len(articles)} article(s) and then select the best \
jewelry trend topic to write about for {_DATE_CONTEXT}.

SOURCE ARTICLES:
{articles_block}

Your tasks:
1. Identify the writing style, tone, vocabulary level, and structural patterns \
   (e.g. listicle, long-form editorial, how-to, Q&A, narrative).
2. Choose ONE specific, timely jewelry topic that:
   - Is trending or highly relevant for {_DATE_CONTEXT}
   - Would naturally appeal to the audience implied by the source articles
   - Has not already been covered by the source articles
   Examples of possible directions (do not limit yourself to these):
   • Seasonal gemstone or colour trends (e.g. pantone colour of the year)
   • Specific jewellery styles rising in popularity (e.g. chunky chains, vintage revival)
   • Occasion-driven buying guides (e.g. gifting, weddings)
   • Sustainability & lab-grown diamonds
   • Stackable or layering jewellery
   • Fine vs demi-fine vs fashion jewellery

Return ONLY a JSON object with these exact keys:
{{
  "topic": "<concise topic title — 5–10 words>",
  "topic_detail": "<2–3 sentence explanation of why this topic is timely right now>",
  "style_notes": "<detailed description of writing style, vocabulary level, sentence length, POV>",
  "tone": "<e.g. conversational, authoritative, aspirational, educational, etc.>",
  "structure_notes": "<describe the structural pattern: intro, body format, CTA, word count range>",
  "key_phrases": ["<3–5 recurring phrases or stylistic markers from the source articles>"]
}}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": user}],
    )

    # Extract text block (thinking blocks may precede it)
    text = ""
    for block in response.content:
        if block.type == "text":
            text = block.text
            break

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback if Claude wraps the JSON in markdown fences
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Could not parse topic JSON from Claude response: {text[:300]}")


def stream_generated_article(
    articles: list[dict],
    topic_info: dict,
    api_key: str,
) -> Generator[str, None, None]:
    """
    Stream the generated article token-by-token.

    Yields string chunks as they arrive from the Claude API.
    """
    client = anthropic.Anthropic(api_key=api_key)

    articles_block = _build_articles_block(articles)

    topic = topic_info.get("topic", "jewelry trends")
    topic_detail = topic_info.get("topic_detail", "")
    style_notes = topic_info.get("style_notes", "")
    tone = topic_info.get("tone", "")
    structure_notes = topic_info.get("structure_notes", "")
    key_phrases_raw = topic_info.get("key_phrases", [])
    key_phrases = ", ".join(key_phrases_raw) if key_phrases_raw else "N/A"

    system = (
        "You are a professional jewellery content writer with deep knowledge of "
        "jewellery trends, gemology, styling, and the jewellery market. "
        "You write compelling, accurate articles that engage readers and drive purchases. "
        "Today's date is " + _DATE_CONTEXT + "."
    )

    user = f"""Your task is to write a brand-new article about the following topic \
in EXACTLY the same writing style, tone, and structure as the source articles below.

═══════════════════════════════════════
TOPIC TO WRITE ABOUT
═══════════════════════════════════════
{topic}

Why this topic is relevant right now ({_DATE_CONTEXT}):
{topic_detail}

═══════════════════════════════════════
STYLE GUIDE (derived from source articles)
═══════════════════════════════════════
Writing style: {style_notes}
Tone: {tone}
Structure / format: {structure_notes}
Key stylistic phrases to echo (not copy verbatim): {key_phrases}

═══════════════════════════════════════
SOURCE ARTICLES (for style reference only — do NOT copy content)
═══════════════════════════════════════
{articles_block}

═══════════════════════════════════════
INSTRUCTIONS
═══════════════════════════════════════
- Write ONLY the article — no preamble, no explanation, no meta-commentary.
- Start directly with the article headline (use a # heading).
- Match the word count, paragraph rhythm, and section structure of the source articles.
- The subject matter must be ENTIRELY about the new jewelry topic; do not mention \
  the source articles.
- Incorporate current {_DATE_CONTEXT} context naturally (seasonal references, \
  upcoming occasions, current trends).
- All facts about jewelry should be accurate and up-to-date for {_DATE_CONTEXT}.
- Use the same vocabulary level and POV (first person, second person, or third \
  person) as the source articles."""

    with client.messages.stream(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for text_chunk in stream.text_stream:
            yield text_chunk
