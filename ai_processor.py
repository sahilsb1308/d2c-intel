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

CATEGORY_RULES = """
Classify into EXACTLY ONE category using these strict definitions:

1. **Product Review** — A user shares their first-hand experience after actually using a Swiss Beauty product. They describe how it performed, texture, longevity, shade, packaging. May be positive or negative.
   Examples: "I tried the Swiss Beauty lip liner and here's what I think", "Swiss Beauty haul and review", "Been using this foundation for 2 weeks — honest review"

2. **Customer Complaint** — A user expresses frustration, disappointment, or a problem with a Swiss Beauty product or service. May include requests for help, warnings to others, or returns/refund mentions.
   Examples: "dont waste your money on swiss beauty lip liners", "the pigmentation ruined my lips", "ordered 3 days ago and no delivery yet"

3. **Recommendation** — A user recommends or asks for recommendations about Swiss Beauty products without writing a full review. Includes "should I buy", "anyone tried", "looking for dupes", "influence/deinfluence" posts where the user is seeking or giving quick opinions.
   Examples: "Is Swiss Beauty worth it?", "Influence/Deinfluence: swiss beauty", "Looking for a dupe for Swiss Beauty gloss"

4. **Partnership** — Swiss Beauty has officially partnered, collaborated with, or signed a deal with another brand, organisation, celebrity, or event. Includes brand ambassador announcements, co-branded launches, and event sponsorships.
   Examples: "Swiss Beauty partners with District", "Taapsee Pannu named brand ambassador", "Swiss Beauty X Wishlink Creator Event"

5. **Campaign** — Swiss Beauty has launched or is running a marketing campaign, ad film, promotional event, contest, or brand activation. Includes new product launches, festive campaigns, and brand-owned content.
   Examples: "Swiss Beauty launches 'We Got You, Girl!'", "Swiss Beauty Cricket League", "Swiss Beauty glitter station at Karan Aujla's concert"

6. **News Coverage** — A journalist, publication, or news outlet has reported on Swiss Beauty. Includes funding news, leadership appointments, revenue milestones, expansion plans, market analysis.
   Examples: "Swiss Beauty explores PE round", "Swiss Beauty appoints Hemant Gupta as CFO", "Swiss Beauty eyes Rs 1000 crore by FY26"

7. **Thought Leadership** — A Swiss Beauty founder, CMO, CEO, or senior leader shares their industry perspective, philosophy, or opinion. Includes interviews, op-eds, and quotes in media.
   Examples: "Swiss Beauty CMO: You can absolutely be premium at affordable prices", "Our product is the core of the brand: Saahil Nayar", "Consumers no longer want to choose between makeup and skincare"

8. **General Mention** — Swiss Beauty is mentioned in passing without any of the above intent. Includes price/deal alerts from coupon accounts, unrelated context ("Swiss beauty" meaning Switzerland), or posts where the brand is not the focus.
   Use this ONLY when no other category clearly fits.

IMPORTANT GUARDRAILS:
- If a post is from a deal/coupon account sharing a discount link → General Mention (NOT Campaign — campaigns are brand-driven)
- If "swiss beauty" refers to Switzerland scenery or people → General Mention
- If a post is both a complaint AND a review → Customer Complaint takes priority
- If a post recommends AND reviews → Product Review takes priority over Recommendation
- Never default to General Mention when another category fits even partially
"""

SENTIMENT_RULES = """
Determine sentiment based on the author's attitude toward Swiss Beauty specifically:

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


def process(mention: dict) -> dict:
    title = mention.get("title", "")
    content = mention.get("content", "")
    platform = mention.get("platform", "")
    text = f"Title: {title}\n\nContent: {content[:1500]}"

    system_prompt = f"""You are a senior brand intelligence analyst tracking mentions of {BRAND_NAME} (Indian cosmetics/beauty brand) across the internet. You are precise, consistent, and never make lazy classifications.

Given a post or article, return a JSON object with exactly these keys:

"summary": 3-5 sentence analyst-style briefing in third person. Explain: what the post says, who posted it, the context, and why it matters for {BRAND_NAME}. Do NOT start with the brand name. Be specific — mention product names, people, events if present.

"category": Classify using these rules:
{CATEGORY_RULES}

"sentiment": Classify using these rules:
{SENTIMENT_RULES}

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
