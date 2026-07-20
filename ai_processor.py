import json
from openai import OpenAI
from config import OPENAI_API_KEY

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

CATEGORY_RULES = """
Classify into EXACTLY ONE category using these strict definitions:

1. **Product Review** — A user shares their first-hand experience after actually using a {brand_name} product. They describe how it performed, texture, longevity, shade, packaging. May be positive or negative.
   Examples: "I tried the {brand_name} lip liner and here's what I think", "{brand_name} haul and review", "Been using this foundation for 2 weeks — honest review"

2. **Customer Complaint** — A user expresses frustration, disappointment, or a problem with a {brand_name} product or service. May include requests for help, warnings to others, or returns/refund mentions.
   Examples: "dont waste your money on swiss beauty lip liners", "the pigmentation ruined my lips", "ordered 3 days ago and no delivery yet"

3. **Recommendation** — A user recommends or asks for recommendations about {brand_name} products without writing a full review. Includes "should I buy", "anyone tried", "looking for dupes", "influence/deinfluence" posts where the user is seeking or giving quick opinions.
   Examples: "Is {brand_name} worth it?", "Influence/Deinfluence: swiss beauty", "Looking for a dupe for {brand_name} gloss"

4. **Partnership** — {brand_name} has officially partnered, collaborated with, or signed a deal with another brand, organisation, celebrity, or event. Includes brand ambassador announcements, co-branded launches, and event sponsorships.
   Examples: "{brand_name} partners with District", "Taapsee Pannu named brand ambassador", "{brand_name} X Wishlink Creator Event"

5. **Campaign** — {brand_name} has launched or is running a marketing campaign, ad film, promotional event, contest, or brand activation. Includes new product launches, festive campaigns, and brand-owned content.
   Examples: "{brand_name} launches 'We Got You, Girl!'", "{brand_name} Cricket League", "{brand_name} glitter station at Karan Aujla's concert"

6. **News Coverage** — A journalist, publication, or news outlet has reported on {brand_name}. Includes funding news, leadership appointments, revenue milestones, expansion plans, market analysis.
   Examples: "{brand_name} explores PE round", "{brand_name} appoints Hemant Gupta as CFO", "{brand_name} eyes Rs 1000 crore by FY26"

7. **Thought Leadership** — A {brand_name} founder, CMO, CEO, or senior leader shares their industry perspective, philosophy, or opinion. Includes interviews, op-eds, and quotes in media.
   Examples: "{brand_name} CMO: You can absolutely be premium at affordable prices", "Our product is the core of the brand: Saahil Nayar", "Consumers no longer want to choose between makeup and skincare"

8. **General Mention** — {brand_name} is mentioned in passing without any of the above intent. Includes price/deal alerts from coupon accounts, unrelated context ("Swiss beauty" meaning Switzerland), or posts where the brand is not the focus.
   Use this ONLY when no other category clearly fits.

IMPORTANT GUARDRAILS:
- If a post is from a deal/coupon account sharing a discount link → General Mention (NOT Campaign — campaigns are brand-driven)
- If "swiss beauty" refers to Switzerland scenery or people → General Mention
- If a post is both a complaint AND a review → Customer Complaint takes priority
- If a post recommends AND reviews → Product Review takes priority over Recommendation
- Never default to General Mention when another category fits even partially
"""

SENTIMENT_RULES = """
Determine sentiment based on the author's attitude toward {brand_name} specifically:

- **positive** — praise, satisfaction, excitement, gratitude, pride, endorsement
- **negative** — complaint, disappointment, distrust, warning others, frustration
- **neutral** — factual reporting, passing mention, no clear opinion expressed, deal alerts, Switzerland references

IMPORTANT:
- News articles are usually neutral unless they report something negative (e.g. CEO exit, funding failure)
- Campaign posts from the brand itself are positive
- "Influence/Deinfluence" posts asking for opinions → neutral until opinion is clear
- Complaints are always negative even if politely worded
"""


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def process(mention: dict, brand_name: str = "the brand") -> dict:
    title = mention.get("title", "")
    content = mention.get("content", "")
    platform = mention.get("platform", "")
    text = f"Title: {title}\n\nContent: {content[:1500]}"

    system_prompt = f"""You are a senior brand intelligence analyst tracking mentions of {brand_name} (Indian cosmetics/beauty brand) across the internet. You are precise, consistent, and never make lazy classifications.

Given a post or article, return a JSON object with exactly these keys:

"summary": 3-5 sentence analyst-style briefing in third person. Explain: what the post says, who posted it, the context, and why it matters for {brand_name}. Do NOT start with the brand name. Be specific — mention product names, people, events if present.

"category": Classify using these rules:
{CATEGORY_RULES.format(brand_name=brand_name)}

"sentiment": Classify using these rules:
{SENTIMENT_RULES.format(brand_name=brand_name)}

Platform: {platform}
Available categories: {json.dumps(CATEGORIES)}
"""

    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        data = json.loads(response.choices[0].message.content)

        category = data.get("category", "General Mention")
        if category not in CATEGORIES:
            category = "General Mention"

        return {
            **mention,
            "summary": data.get("summary", ""),
            "category": category,
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
