from openai import OpenAI
from config import OPENAI_API_KEY

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def analyze(text: str) -> dict:
    """Returns {'sentiment': 'positive'|'negative'|'neutral', 'score': float, 'reason': str}"""
    if not text or not text.strip():
        return {"sentiment": "neutral", "score": 0.0, "reason": "Empty text"}

    snippet = text[:1000]
    try:
        response = _get_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You analyze social media posts about the Swiss Beauty brand (Indian cosmetics/beauty brand). "
                        "Return ONLY a JSON object with three keys: "
                        '"sentiment" (one of: positive, negative, neutral), '
                        '"score" (float from -1.0 to 1.0, where -1 is very negative, 0 is neutral, 1 is very positive), '
                        '"reason" (one short sentence explaining why). '
                        "Examples: complaints, bad reviews = negative. Praise, recommendations = positive. "
                        "Neutral mentions with no clear opinion = neutral."
                    ),
                },
                {"role": "user", "content": snippet},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        import json
        data = json.loads(response.choices[0].message.content)
        return {
            "sentiment": data.get("sentiment", "neutral"),
            "score": float(data.get("score", 0.0)),
            "reason": data.get("reason", ""),
        }
    except Exception as e:
        print(f"  [sentiment] OpenAI error: {e}")
        return {"sentiment": "neutral", "score": 0.0, "reason": "Analysis failed"}
