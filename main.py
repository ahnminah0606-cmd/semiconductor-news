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
    """기사 본문 전체를 누락 없이 스크래핑"""
    try:
        import requests
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            
            for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
                element.decompose()
                
            article_body = (
                soup.find("div", class_="entry-content") or 
                soup.find("div", class_="post-content") or 
                soup.find("article") or
                soup.find("div", class_="article-body")
            )
            
            if article_body:
                paragraphs = article_body.find_all(["p", "h2", "h3", "li"])
            else:
                paragraphs = soup.find_all("p")
                
            full_text = "\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return full_text.strip()
    except Exception as e:
        print(f"⚠️ 스크래핑 중 오류 발생 ({url}): {e}")
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
                if pub_dt >= twenty_four_hours_:`
                if pub_dt >= twenty_four_hours_ago:
                    full_content = fetch_full_article_content(entry.link)
                    
                    if not full_content or len(full_content) < 200:
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
    """반도체 소자/공정/패키징 하드코어 전문 분석 프롬프트"""
    system_prompt = (
        "너는 글로벌 반도체 선도 기업(삼성전자, SK하이닉스, TSMC 등)의 공정/소자/패키징 15년 차 수석 엔지니어이자, "
        "취업 준비생의 밀착 커리어 멘토야. 뜬구름 잡는 일반적인 설명이나 교과서적인 내용은 절대 배제하고, "
        "실무 현장 및 학회(IEDM, ISSCC) 수준의 깊이 있고 날카로운 전문 공학 용어와 물리적 메커니즘을 바탕으로 분석해야 해."
    )

    truncated_content = content[:6000] if content else ""

    user_prompt = f"""
다음 반도체 기술 기사를 극도로 전문적이고 심층적으로 분석해줘. 취업 면접(기술 면접) 및 직무 포트폴리오에 즉시 투입할 수 있도록 전문 공학적 분석을 제공해야 해.

출처: {source_name}
제목: {title}
본문: {truncated_content}

[중요도 기준]
- 상: HBM, High-NA EUV, 3D 패키징(Hybrid Bonding 등), GAA/CFET 등 핵심 공정/소자 기술 혁신 및 한계 돌파
- 중: 주요 기업 CapEx, 파운드리 미세공정 수율 경쟁, 공급망 및 소부장 국산화/생태계 변화
- 하: 단순 실적, 주가 변동, 일반 IT 가젯 리뷰

아래 형식을 정확히 지켜서 작성해줘:

[중요도]
(상, 중, 하 중 하나)

[본문 내용]
1. 기술 심층 분석: (기사에 언급된 기술이 기존 레거시 공정/아키텍처 대비 물리적·구조적으로 무엇이 혁신적으로 다른지 상세히 분석할 것. 공정 한계(RC 딜레이, 숏채널 효과, 열팽창계수Mismatch 등), 수율(Yield) 향상 요인, 재료적 특성 변화 등 공학적 원리를 포함하여 최소 6~7문장 이상으로 매우 깊이 있게 서술)
2. 반도체 직무 시사점: (공정/소자/설비/패키징 엔지니어 관점에서 이 트렌드가 실무 현장에 미치는 파급효과와 직무 수행 시 직면할 핵심 병목(Bottleneck) 및 트러블슈팅 포인트를 짚어줄 것. 면접관에게 전문성을 어필할 수 있는 수준으로 최소 4~5문장 이상 구체적으로 작성)
3. 핵심 전문 키워드: (일반적인 단어 금지. 반도체 세부 공정, 소자 물리, 패키징 전문 용어 위주로 콤마로 구분하여 5개 이상 작성)
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
    """노션 데이터베이스에 페이지 생성"""
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
                            "text": {"content": body_text[:2000]},
                        }
                    ]
                },
            }
        ],
    )


def main():
    print("🔍 24시간 내 수집된 기사 탐색 및 본문 정밀 스크래핑 중...")
    articles = fetch_past_24h_articles()
    print(f"📰 수집된 총 기사 수: {len(articles)}개")

    for idx, article in enumerate(articles, 1):
        if check_url_exists(article["link"]):
            print(f"⏩ [중복 스킵] 이미 등록된 기사: {article['title']}")
            continue

        print(f"\n[{idx}/{len(articles)}] 반도체 하드코어 심층 AI 분석 중: {article['title']}")
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