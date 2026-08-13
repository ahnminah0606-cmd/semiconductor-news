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

# 노션 다중 선택(Multi-select)에 사전에 등록된 공식 기업 목록
ALLOWED_COMPANIES = [
    "한미반도체", "삼성전자", "SK하이닉스", "HPSP", "리노공업", "동진쎄미켐", 
    "주성엔지니어링", "원익IPS", "솔브레인", "하나마이크론", "DB하이텍", "TSMC", 
    "ASML", "어플라이드 머티리얼즈(AMAT)", "램리서치(LRCX)", "엔비디아(NVIDIA)", "AMD", 
    "퀄컴(QCOM)", "브로드컴(AVGO)", "앤트로픽(Anthropic)", "애플(AAPL)", "인텔(INTC)", 
    "샌디스크(SanDisk)", "웨스턴디지털(WDC)", "마이크론(MU)", "키옥시아(Kioxia)", 
    "솔리다임(Solidigm)", "시놉시스(SNPS)", "케이던스(CDNS)", "ARM", "글로벌파운드리스(GFS)", 
    "에이디테크놀로지", "가온칩스", "에이직랜드", "코아시아", "ASE", "암코(Amkor)", 
    "JCET", "두산테스나", "SFA반도체", "네페스", "LB세미콘", "에이팩트", "도쿄일렉트론(TEL)", 
    "KLA", "ISC", "티씨케이", "LX세미콘", "스크린(Screen)", "히타치 하이테크(Hitachi High-Tech)", 
    "큐니티(Qnity)", "머크(Merck)", "레조낙(Resonac)", "신에츠(Shin-Etsu)", "니콘(Nikon)", 
    "캐논(Canon)", "디스코(DISCO)", "텔레칩스", "칩스앤미디어", "어보브반도체", "제주반도체", 
    "앤씨앤", "서진시스템", "에스앤에스텍", "에프에스티", "유진테크", "넥스틴", "피에스케이", 
    "이오테크닉스", "하나머티리얼즈", "싸이맥스", "코미코", "ST마이크로일렉트로닉스(STM)", 
    "인피니온(IFX)", "NXP", "엠코어", "덴소(DENSO)", "도쿄오카공업(TOK)", "니폰산소(Nippon Sanso)", 
    "어드반테스트(Advantest)", "온세미(ON)", "테라다인(TER)", "시러스로직(CRUS)", "마벨(MRVL)", "소이텍(Soitec)",
    "텍사스 인스트루먼트(TXN)"
]

COMPANY_ALIASES = {
    # 한국
    "삼성": "삼성전자",
    "삼성전자": "삼성전자",
    "SK hynix": "SK하이닉스",
    "SK Hynix": "SK하이닉스",
    "SK하이닉스": "SK하이닉스",

    # NVIDIA
    "NVIDIA": "엔비디아(NVIDIA)",
    "Nvidia": "엔비디아(NVIDIA)",
    "엔비디아": "엔비디아(NVIDIA)",

    # Intel
    "Intel": "인텔(INTC)",
    "INTEL": "인텔(INTC)",
    "인텔": "인텔(INTC)",

    # AMD
    "AMD": "AMD",

    # Qualcomm
    "Qualcomm": "퀄컴(QCOM)",
    "QUALCOMM": "퀄컴(QCOM)",
    "퀄컴": "퀄컴(QCOM)",

    # Apple
    "Apple": "애플(AAPL)",
    "APPLE": "애플(AAPL)",
    "애플": "애플(AAPL)",

    # Broadcom
    "Broadcom": "브로드컴(AVGO)",
    "브로드컴": "브로드컴(AVGO)",

    # Micron
    "Micron": "마이크론(MU)",
    "마이크론": "마이크론(MU)",

    # TSMC
    "TSMC": "TSMC",
    "Taiwan Semiconductor": "TSMC",

    # ASML
    "ASML": "ASML",

    # Lam Research
    "Lam Research": "램리서치(LRCX)",
    "램리서치": "램리서치(LRCX)",

    # Applied Materials
    "Applied Materials": "어플라이드 머티리얼즈(AMAT)",
    "AMAT": "어플라이드 머티리얼즈(AMAT)",

    # TEL
    "Tokyo Electron": "도쿄일렉트론(TEL)",
    "TEL": "도쿄일렉트론(TEL)",
    "도쿄일렉트론": "도쿄일렉트론(TEL)",

    # KLA
    "KLA": "KLA",

    # Synopsys
    "Synopsys": "시놉시스(SNPS)",
    "시놉시스": "시놉시스(SNPS)",

    # Cadence
    "Cadence": "케이던스(CDNS)",
    "케이던스": "케이던스(CDNS)",

    # ARM
    "ARM": "ARM",

    # GlobalFoundries
    "GlobalFoundries": "글로벌파운드리스(GFS)",
    "글로벌파운드리스": "글로벌파운드리스(GFS)",

    # Texas Instruments
    "Texas Instruments": "텍사스 인스트루먼트(TXN)",
    "TI": "텍사스 인스트루먼트(TXN)",
    "텍사스 인스트루먼트": "텍사스 인스트루먼트(TXN)",
}


def normalize_companies(raw_companies):
    result = []

    for company in raw_companies:
        company = company.strip()

        if company in ALLOWED_COMPANIES:
            result.append(company)
            continue

        if company in COMPANY_ALIASES:
            mapped = COMPANY_ALIASES[company]
            if mapped in ALLOWED_COMPANIES:
                result.append(mapped)

    return list(dict.fromkeys(result))


FEEDS = [
    {"name": "EE Times", "url": "https://www.eetimes.com/feed/"},
    {"name": "SemiAnalysis", "url": "https://www.semianalysis.com/feed"},
    {"name": "Tom's Hardware", "url": "https://www.tomshardware.com/feeds/all"},
]


def fetch_full_article_content(url):
    """기사 본문 스크래핑"""
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
            paragraphs = article_body.find_all(["p", "h2", "h3", "li"]) if article_body else soup.find_all("p")
            full_text = "\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return full_text.strip()
    except Exception as e:
        print(f"⚠️ 스크래핑 오류 ({url}): {e}")
    return ""


def fetch_past_24h_articles():
    """지난 24시간 기사 수집"""
    articles = []
    now = datetime.datetime.now(datetime.timezone.utc)
    twenty_four_hours_ago = now - datetime.timedelta(hours=24)

    for feed_info in FEEDS:
        feed = feedparser.parse(feed_info["url"])
        for entry in feed.entries:
            published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
            if published_parsed:
                pub_dt = datetime.datetime(*published_parsed[:6], tzinfo=datetime.timezone.utc)
                if pub_dt >= twenty_four_hours_ago:
                    full_content = fetch_full_article_content(entry.link)
                    if not full_content or len(full_content) < 200:
                        summary_html = entry.get("summary") or entry.get("description") or ""
                        full_content = BeautifulSoup(summary_html, "html.parser").get_text().strip()

                    articles.append({
                        "title": entry.title,
                        "link": entry.link,
                        "content": full_content,
                        "source": feed_info["name"],
                        "date": pub_dt.strftime("%Y-%m-%d"),
                    })
    return articles


def check_url_exists(link):
    """중복 확인"""
    try:
        response = notion.databases.query(
            database_id=DATABASE_ID,
            filter={"property": "URL", "url": {"equals": link}}
        )
        return len(response["results"]) > 0
    except Exception:
        return False


def analyze_with_llm(title, content, source_name):
    """요청된 수석 엔지니어 전용 시스템 및 유저 프롬프트 적용"""
    system_prompt = (
        "너는 삼성전자와 SK하이닉스에서 15년 이상 근무한 공정·소자·패키징 수석 엔지니어이며, "
        "TSMC, Intel, NVIDIA, ASML의 최신 기술 동향까지 분석하는 반도체 기술 전문가다. "
        "기사를 단순 요약하지 말고 기술적 원리, 공정, 장비, 소재, 경쟁 기술과의 차이, 산업적 의미를 깊이 있게 설명하라. "
        "답변은 현직 엔지니어 교육자료 수준으로 작성하며, 추상적인 표현 대신 구체적인 기술 내용을 포함한다."
    )
    truncated_content = content[:6000] if content else ""

    user_prompt = f"""
다음 반도체 기술 기사를 분석해줘.

출처: {source_name}
원문 제목: {title}

본문:
{truncated_content}

==========================
[중요도 평가 기준]
==========================

■ 상
- HBM
- High-NA EUV
- EUV
- GAA
- CFET
- Backside Power Delivery
- Chiplet
- 3D 패키징
- Hybrid Bonding
- CoWoS
- 차세대 메모리
- 첨단 공정
- AI 반도체 핵심 기술
- 반도체 산업의 패러다임 변화

■ 중
- 기업 투자(CapEx)
- 파운드리 경쟁
- 수율 개선
- 공급망 변화
- 생산라인 증설
- 신규 고객 확보
- 장비·소재 기술
- 후공정 기술
- 자동차 반도체
- 산업 동향

■ 하
- 단순 실적 발표
- 주가 변동
- 일반 IT 제품 리뷰
- 소비자 전자제품
- 게임
- 루머성 기사

==========================
[기업 추출]
==========================

기사에서 언급된 반도체 관련 기업만 추출해.

규칙

- 영어 또는 한국어 모두 가능
- 일반적으로 많이 사용하는 이름 사용
- 쉼표(,)로 구분
- 최대 10개
- 기사에 없는 기업은 쓰지 말 것
- 없으면 빈칸

예시

Intel
NVIDIA
Apple
TSMC
AMD
ASML
Lam Research
삼성전자
SK hynix
Qualcomm

==========================
[응답 형식]
==========================

[한글 제목]

자연스럽고 직관적인 한국어 제목

[중요도]

상 / 중 / 하

[관련 기업]

회사1, 회사2, 회사3

[본문 내용]

1. 기술 심층 분석

다음 내용을 반드시 포함하여 10문장 이상 작성한다.

- 핵심 기술의 원리
- 기존 기술 대비 차이점
- 왜 필요한 기술인지
- 어떤 공정(Process)에서 사용되는지
- 사용되는 장비 또는 소재
- 기술적 난이도와 해결 과제
- 경쟁사 기술과의 차이
- 반도체 산업에 미치는 영향
- 앞으로의 발전 방향

단순 기사 요약이 아니라
현직 삼성전자·SK하이닉스 공정기술/소자/장비 엔지니어 교육자료 수준으로 작성한다.

2. 반도체 직무 시사점

다음 내용을 반드시 포함하여 6문장 이상 작성한다.

- 공정기술 직무
- 장비기술 직무
- 소자 직무
- 패키징 직무
- 면접에서 나올 수 있는 질문
- 취업 준비 시 알아야 할 핵심 내용

3. 핵심 전문 키워드

최소 8개 이상 작성한다.

예시

HBM
CoWoS
High-NA EUV
Chiplet
Hybrid Bonding
GAA
CFET
TSV
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=2500,
    )

    result_text = response.choices[0].message.content

    # 한글 제목 파싱
    korean_title = title
    if "[한글 제목]" in result_text and "[중요도]" in result_text:
        try:
            korean_title = result_text.split("[한글 제목]")[1].split("[중요도]")[0].strip()
        except Exception:
            pass

    # 중요도 파싱
    importance = "중"
    if "[중요도]" in result_text:
        try:
            imp_part = result_text.split("[중요도]")[1].split("[관련 기업]")[0].strip()
            if "상" in imp_part:
                importance = "상"
            elif "하" in imp_part:
                importance = "하"
            elif "중" in imp_part:
                importance = "중"
        except Exception:
            pass

    if importance == "하":
        return "SKIP", "", "", []

    # 관련 기업 검증 및 정규화 (파이썬 코드 단에서 2차 매핑 적용)
    matched_companies = []
    if "[관련 기업]" in result_text:
        try:
            comp_part = result_text.split("[관련 기업]")[1].split("[본문 내용]")[0].strip()
            raw_companies = [c.strip() for c in comp_part.split(",") if c.strip()]
            matched_companies = normalize_companies(raw_companies)
        except Exception:
            pass

    body_text = result_text.strip()
    return importance, korean_title, body_text, matched_companies


def create_notion_page(
    korean_title, importance, source, link, date_str, body_text, companies
):
    """노션 API 호출 (2000자 초과 본문 분할 처리 추가)"""
    properties = {
        "제목": {
            "title": [
                {
                    "text": {
                        "content": f"[{importance}] {korean_title}"
                    }
                }
            ]
        },
        "출처": {
            "select": {
                "name": source
            }
        },
        "URL": {
            "url": link
        }
    }

    # 날짜
    if date_str:
        print("날짜 =", date_str)
        properties["날짜"] = {
            "date": {
                "start": str(date_str)
            }
        }

    # 관련 기업
    if companies:
        properties["관련 기업"] = {
            "multi_select": [
                {"name": comp}
                for comp in companies
            ]
        }

    import json
    print(json.dumps(properties, ensure_ascii=False, indent=2))

    # 심층 분석 본문 길이가 길어질 경우를 대비한 2000자 단위 분할 블록 생성
    content_blocks = []
    chunks = [body_text[i:i+1900] for i in range(0, len(body_text), 1900)]
    for chunk in chunks:
        content_blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": chunk}}]
            },
        })

    import json

try:
    print("====== Notion Properties ======")
    print(json.dumps(properties, ensure_ascii=False, indent=2))

    notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties=properties,
        children=content_blocks,
    )

except Exception as e:
    print(f"❌ 노션 등록 실패: {e}")
    raise e


def main():
    print("🔍 기사 수집 시작...")
    articles = fetch_past_24h_articles()
    print(f"📰 수집된 총 기사 수: {len(articles)}개")

    for idx, article in enumerate(articles, 1):
        if check_url_exists(article["link"]):
            print(f"⏩ [중복 스킵] {article['title']}")
            continue

        print(f"\n[{idx}/{len(articles)}] 분석 중: {article['title']}")
        importance, korean_title, body_text, companies = analyze_with_llm(
            article["title"], article["content"], article["source"]
        )

        if importance == "SKIP":
            print(f"⏩ [스킵 - 중요도 '하'] {article['title']}")
            continue

        print(f"✅ [노션 등록 중] 중요도: {importance} | 매칭된 기업: {companies}")
        create_notion_page(
            korean_title,
            importance,
            article["source"],
            article["link"],
            article["date"],
            body_text,
            companies,
        )

    print("\n🎉 모든 작업이 완료되었습니다!")


if __name__ == "__main__":
    main()