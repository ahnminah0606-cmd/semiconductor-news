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


def fetch_full_article_content(url):
    """기사 URL에 직접 접속하여 본문 전체 텍스트를 스크래핑"""
    try:
        import requests
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 불필요한 태그(광고, 스크립트 등) 제거
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.extract()
                
            # 본문 영역 추정 또는 전체 텍스트 추출
            paragraphs = soup.find_all("p")
            full_text = " ".join([p.get_text() for p in paragraphs])
            return full_text.strip()
    except Exception:
        pass
    return ""


def fetch_past_24h_articles():
    """전날 06:00부터 금일 05:59까지 수집 및 본문 크롤링 수행"""
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
                    # RSS 요약 대신 실제 기사 페이지 전체 내용을 크롤링
                    full_content = fetch_full_article_content(entry.link)
                    
                    # 크롤링 실패 시 RSS 요약본이라도 대체 사용
                    if not full_content:
                        summary_html = entry.get("summary") or entry.get("description") or ""
                        soup = BeautifulSoup(summary_html, "html.parser")
                        full_content = soup.get_text().strip()

                    articles.append({
                        "title": entry.title,
                        "link": entry.link,
                        "content": full_content,
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
    """반도체 취업 준비생을 위한 고도화된 전문 심층 분석 프롬프트"""
    system_prompt = (
        "너는 글로벌 반도체 대기업 수석 엔지니어이자 취업/커리어 멘토야. "
        "반도체 공정, 소자, 패키징, 설비, 설계 관점에서 전문적이고 깊이 있는 분석을 제공해야 해."
    )

    # 전문 분석을 위해 본문 허용량을 넉넉하게 확장 (최대 4000자)
    truncated_content = content[:4000] if content else ""

    user_prompt = f"""
다음 반도체 기술 기사를 철저하게 심층 분석해줘. 취업 면접과 자소서에 바로 활용할 수 있을 정도로 전문적이고 구체적으로 작성해야 해.

출처: {source_name}
제목: {title}
본문: {truncated_content}

[중요도 기준]
- 상: HBM, High-NA EUV, 3D 패키징, GAA 등 핵심 기술 혁신 및 공정 한계 극복
- 중: 주요 기업 CapEx, 파운드리 미세공정 경쟁, 대규모 공급망 및 정책 변화
- 하: 단순 실적, 주가 변동, 일반 IT 가젯 리뷰

아래 형식을 정확히 지켜서 작성해줘:

[중요도]
(상, 중, 하 중 하나)

[본문 내용]
1. 기술 심층 분석: (기사에 언급된 핵심 기술력이 구체적으로 무엇이며, 기존 기술/공정 방식과 비교했을 때 무엇이 혁신적으로 다른지 4~5문장으로 상세히 설명)
2. 반도체 직무 시사점: (공정/소자/설비/패키징 등 엔지니어 관점에서 이 기술 트렌드가 실무와 취업 준비에 어떤 영향을 미치는지, 엔지니어가 주목해야 할 포인트를 구체적인 논리로 3문장 이상 작성)
3. 핵심 전문 키워드: (반도체 전문 기술 용어 위주로 콤마로 구분하여 5개 이내 작성)
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=1000,  # 전문적이고 긴 내용을 담기 위해 토큰 여유 확보
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
    """노션 데이터베이스에 페이지 생성 (기업 태그는 노션 AI 자동 채우기 활용)"""
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
                            "text": {"content": body_text[:2000]},  # 넉넉하게 본문 수용
                        }
                    ]
                },
            }
        ],
    )


def main():
    print("🔍 24시간 내 수집된 기사 탐색 및 본문 스크래핑 중...")
    articles = fetch_past_24h_articles()
    print(f"📰 수집된 총 기사 수: {len(articles)}개")

    for idx, article in enumerate(articles, 1):
        if check_url_exists(article["link"]):
            print(f"⏩ [중복 스킵] 이미 등록된 기사: {article['title']}")
            continue

        print(f"\n[{idx}/{len(articles)}] 반도체 심층 AI 분석 중: {article['title']}")
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

    print("\n🎉 모든 심층 분석 작업이 완료되었습니다!")


if __name__ == "__main__":
    main()