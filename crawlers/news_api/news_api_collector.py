import httpx
import os
from dotenv import load_dotenv

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_URL = "https://newsapi.org/v2/top-headlines"


async def fetch_news_api(category: str = "technology", country: str = "kr") -> list[dict]:
    """NewsAPI에서 기사 수집"""
    params = {
        "apiKey": NEWS_API_KEY,
        "category": category,
        "country": country,
        "pageSize": 100,
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(NEWS_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

    articles = []
    for item in data.get("articles", []):
        articles.append({
            "title": item.get("title", ""),
            "content": item.get("content", "") or item.get("description", ""),
            "source_url": item.get("url", ""),
            "publisher": item.get("source", {}).get("name", ""),
            "published_at": item.get("publishedAt"),
        })

    return articles