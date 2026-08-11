import datetime
import os
import feedparser
from bs4 import BeautifulSoup
from notion_client import Client
from openai import OpenAI

# 1. 환경 변수 로드
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
notion = Client(auth=NOTION_TOKEN)

# 수집할 RSS 피드 및 매체 정보
FEEDS = [
    {"name": "EE Times", "url": "https://www.eetimes.com/feed/"},
    {"name": "SemiAnalysis", "url": "https://www.semianalysis.com/feed"},
    {
        "name": "Tom's Hardware",
        "url": "https://www.tomshardware.com/feeds/all",
    },
]


def fetch_past_24h_articles():
    """전날 06:00부터 금일 05:59까지 수집 (약 24시간 기준)"""
    articles = []
    now = datetime.datetime.now(datetime.timezone.utc)
    twenty_four_hours_ago = now - datetime.timedelta(hours=24)

    for feed_info in FEEDS:
        feed = feedparser.parse(feed_info["url"])
        for entry in feed.entries:
            published_parsed = entry.get("published_parsed") or entry.get(
                "updated_parsed"
            )
            if published_parsed:
                pub_dt = datetime.datetime(*published_parsed[:6], tzinfo=datetime.timezone.utc)
                if pub_dt >= twenty_four_hours_ago:
                    summary_html = entry.get("summary") or entry.get("description") or ""
                    soup = BeautifulSoup(summary_html, "html.parser")
                    text_content = soup.get_text().strip()

                    articles.append({
                        "title": entry.title,
                        "link": entry.link,
                        "content": text_content,
                        "source": feed_info["name"],
                        "date": pub_dt.strftime("%Y-%m-%d"),
                    })
    return articles


def check_url_exists(link):
    """노션 DB에 이미 동일한 URL이 존재하는지 확인 (중복 방지)"""
    try:
        response = notion.databases.query(
            database_id=DATABASE_ID,
            filter={
                "property": "URL",
                "url": {
                    "equals": link
                }
            }
        )
        return len(response["results"]) > 0
    except Exception:
        return False


def analyze_with_llm(title, content, source_name):
    """토큰 절약을 위해 핵심 요약 위주로 OpenAI API 분석"""
    system_prompt = (
        "너는 반도체 엔지니어링 취업 준비생을 위한 기술 뉴스 분석가야. "
        "기사에서 핵심 내용만 압축해서 간결하게 요약해줘."
    )

    truncated_content = content[:1500] if content else ""

    # 파이썬 코드에서 '관련 기업' 태그 자동 파싱 부분은 제거하고,
    # 노션 자체의 AI 자동 채우기 기능에 맡기기 위해 기업 필드 파싱 로직을 간소화했습니다.
    user_prompt = f"""
다음 반도체 기사를 분석해줘.

출처: {source_name}
제목: {title}
본문: {truncated_content}

[중요도 기준]
- 상: HBM, High-NA EUV, Advanced Packaging 등 핵심 기술 혁신
- 중: 주요 기업 CapEx, 파운드리 동향, 정책 변화
- 하: 단순 실적, 인사 이동, 일반 IT 리뷰

아래 형식을 정확히 지켜줘:

[중요도]
(상, 중, 하 중 하나)

[본문 내용]
1. 기사 요약: (3줄 이내 핵심 요약)
2. 직무 시사점: (공정/소자/설비 관점 1~2줄)
3. 핵심 키워드: (콤마로 5개 이내)
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=600,
    )

    result_text = response.choices[0].message.content

    importance = "중"
    if "[중요도]" in result_text:
        try:
            imp_part = (
                result_text.split("[중요도]")[1]
                .split("[본문 내용]")[0]
                .strip()
            )
            if "상" in imp_part:
                importance = "상"
            elif "하" in imp_part:
                importance = "하"
            elif "중" in imp_part:
                importance = "중"
        except Exception:
            pass

    if importance == "하":
        return "SKIP", ""

    body_text = result_text.strip()
    return importance, body_text


def create_notion_page(
    title, importance, source, link, date_str, body_text
):
    """노션 데이터베이스에 페이지 생성 (기업 태그는 노션 AI 자동 채우기에 위임)"""
    notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties={
            "날짜": {"date": {"start": date_str}},
            "제목": {
                "title": [
                    {"text": {"content": f"[{importance}] {title}"}}
                ]
            },
            "출처": {"select": {"name": source}},
            "URL": {"url": link},
        },
        children=[
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": body_text[:1800]},
                        }
                    ]
                },
            }
        ],
    )


def main():
    print("🔍 24시간 내 수집된 기사 탐색 중...")
    articles = fetch_past_24h_articles()
    print(f"📰 수집된 총 기사 수: {len(articles)}개")

    for idx, article in enumerate(articles, 1):
        # 이미 노션에 등록된 URL인지 중복 체크
        if check_url_exists(article["link"]):
            print(f"⏩ [중복 스킵] 이미 등록된 기사: {article['title']}")
            continue

        print(f"\n[{idx}/{len(articles)}] AI 분석 진행 중: {article['title']}")
        importance, body_text = analyze_with_llm(
            article["title"], article["content"], article["source"]
        )

        if importance == "SKIP":
            print(f"⏩ [스킵 - 중요도 '하'] {article['title']}")
            continue

        print(f"✅ [업로드 내역 - 중요도 '{importance}'] 노션 등록 중...")
        create_notion_page(
            article["title"],
            importance,
            article["source"],
            article["link"],
            article["date"],
            body_text,
        )

    print("\n🎉 모든 작업이 완료되었습니다!")


if __name__ == "__main__":
    main()