"""
Uses OpenAI to generate a detailed summary and classify the category
for each brand mention — matching the format in the D2C Intel Tracker sheet.
"""
import json
from openai import OpenAI
from config import OPENAI_API_KEY, BRAND_NAME

_client = None

CATEGORIES = [
    "Product Review",
    "Customer Complaint",
    "Recommendation",
    "Partnership",
    "Campaign",
    "News Coverage",
    "Thought Leadership",
    "General Mention",
]


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def process(mention: dict) -> dict:
    """
    Returns the mention dict enriched with:
      - summary: detailed paragraph-style summary (like the D2C tracker sheet)
      - category: one of CATEGORIES
      - sentiment: positive | negative | neutral
    """
    title = mention.get("title", "")
    content = mention.get("content", "")
    platform = mention.get("platform", "")
    text = f"Title: {title}\n\nContent: {content[:1500]}"

    system_prompt = f"""You are an analyst tracking brand mentions of {BRAND_NAME} (Indian cosmetics/beauty brand) across the internet.

Given a social media post or article, return a JSON object with exactly these keys:

"summary": A detailed, paragraph-style summary (3-5 sentences) explaining what the post says, who posted it, the context, and why it matters for the brand. Write in third person, formal tone — like an analyst briefing. Do NOT start with the brand name.

"category": Classify the post into exactly ONE of these categories:
{json.dumps(CATEGORIES, indent=2)}

"sentiment": One of: positive, negative, neutral — based on how the author feels about {BRAND_NAME}.

Platform context: {platform}
"""

    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        data = json.loads(response.choices[0].message.content)
        return {
            **mention,
            "summary": data.get("summary", ""),
            "category": data.get("category", "General Mention"),
            "sentiment": data.get("sentiment", "neutral"),
        }
    except Exception as e:
        print(f"  [ai] Error processing '{title[:50]}': {e}")
        return {
            **mention,
            "summary": content[:500],
            "category": "General Mention",
            "sentiment": "neutral",
        }
