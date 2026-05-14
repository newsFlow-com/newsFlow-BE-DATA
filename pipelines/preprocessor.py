from bs4 import BeautifulSoup


def clean_html(raw_html: str) -> str:
    """HTML 태그 제거 후 순수 텍스트 반환"""
    soup = BeautifulSoup(raw_html, "lxml")
    return soup.get_text(separator=" ", strip=True)


def preprocess_article(article: dict) -> dict:
    """
    기사 전처리
    - HTML 제거
    - 공백 정리
    """
    article["content"] = clean_html(article.get("content", ""))
    article["title"] = article.get("title", "").strip()
    return article