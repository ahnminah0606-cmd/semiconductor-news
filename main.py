import datetime
import os
import re
import feedparser
import requests
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
            # 발행 날짜 파싱
            published_parsed = entry.get("published_parsed") or entry.get(
                "updated_parsed"
            )
            if published_parsed:
                pub_dt = datetime.datetime(*published_parsed[:6], tzinfo=datetime.timezone.utc)
                if pub_dt >= twenty_four_hours_ago:
                    # summary 또는 description 태그 유연하게 파싱
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


def analyze_with_llm(title, content, source_name):
    """OpenAI API로 중요도 평가 및 심화 기술 분석"""
    system_prompt = (
        "너는 반도체 대기업(삼성전자/SK하이닉스) 공정·소자·설비 엔지니어링 취업 비서야. "
        "제공된 기사가 반도체 기술/공정/소자/설비/산업 생태계 관점에서 심화 분석할 가치가 있는지 평가하고 요약해줘."
    )

    user_prompt = f"""
아래 영문 반도체 기사를 분석해줘.

[기사 정보]
출처: {source_name}
제목: {title}
본문: {content}

[중요도 평가 기준]
- 상: HBM, High-NA EUV, Advanced Packaging, ALD, Sub-nanometer, 수율 개선 등 핵심 기술/공정/소자 혁신 기사
- 중: 반도체 주요 기업(TSMC, 삼성, SK하이닉스, ASML 등)의 설비 투자(CapEx), 파운드리 시장 동향, 주요 규제/정책 변화
- 하: 단순 주가/실적 변동, 기업 인사 이동, 단순 가전/IT 완제품 리뷰, 기술 깊이가 없는 일반 뉴스

아래 포맷을 엄격히 지켜서 답변해줘:

[중요도]
(상, 중, 하 중 단 하나만 작성)

[관련 기업 및 분야]
(삼성전자, SK하이닉스, ASML 등 콤마 구분)

[본문 내용]
1. 기사 요약 (기술적 관점 3줄 내외)
2. 기술 상식 및 심화 배경 (원리, 한계, 타 기술 비교 등)
3. 직무 시사점 (공정/소자/설비 지원자 관점)
4. 핵심 기술 키워드 5개
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=1500,
    )

    result_text = response.choices[0].message.content

    # 중요도 추출
    importance = "중"
    if "[중요도]" in result_text:
        try:
            imp_part = (
                result_text.split("[중요도]")[1]
                .split("[관련 기업 및 분야]")[0]
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

    # '하' 등급은 업로드 대상에서 스킵
    if importance == "하":
        return "SKIP", [], ""

    # 기업 태그 및 본문 파싱
    companies = []
    body_text = result_text

    if "[관련 기업 및 분야]" in result_text and "[본문 내용]" in result_text:
        parts = result_text.split("[본문 내용]")
        company_part = (
            parts[0].split("[관련 기업 및 분야]")[1].replace("-", "").strip()
        )
        body_text = parts[1].strip()

        raw_companies = company_part.split(",")
        # 글자 수 제한 및 공백 제거 방어 로직
        companies = [c.strip()[:50] for c in raw_companies if c.strip()]

    return importance, companies, body_text


def create_notion_page(
    title, importance, source, link, date_str, companies, body_text
):
    """노션 데이터베이스에 페이지 생성"""
    # 관련 기업 태그 목록 생성 (최대 5개)
    multi_select_companies = [{"name": comp} for comp in companies[:5]] if companies else []

    notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties={
            # 1. 기사 제목 (노션 표의 Title 열 이름)
            "이름": {
                "title": [
                    {"text": {"content": f"[{importance}] {title}"}}
                ]
            },
            # 2. 출처
            "출처": {"select": {"name": source}},
            # 3. 날짜
            "날짜": {"date": {"start": date_str}},
            # 4. 관련 기업
            "관련 기업": {"multi_select": multi_select_companies},
            # 5. URL
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
                        }  # 노션 글자수 제한 대응 (1,800자)
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
        print(f"\n[{idx}/{len(articles)}] AI 분석 진행 중: {article['title']}")
        importance, companies, body_text = analyze_with_llm(
            article["title"], article["content"], article["source"]
        )

        if importance == "SKIP":
            print(f"⏩ [스킵 - 중요도 '하'] {article['title']}")
            continue

        print(f"✅ [업로드 - 중요도 '{importance}'] 노션 등록 중...")
        create_notion_page(
            article["title"],
            importance,
            article["source"],
            article["link"],
            article["date"],
            companies,
            body_text,
        )

    print("\n🎉 모든 작업이 완료되었습니다!")


if __name__ == "__main__":
    main()