#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import datetime
import json
import os
import sys
import traceback
import feedparser
import requests
from bs4 import BeautifulSoup
from notion_client import Client
from openai import OpenAI

# ==============================================================================
# 1. 환경 변수 확인 및 초기화
# ==============================================================================
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DATABASE_ID = os.environ.get("DATABASE_ID")

if not OPENAI_API_KEY or not NOTION_TOKEN or not DATABASE_ID:
    print("❌ [환경 변수 오류] OPENAI_API_KEY, NOTION_TOKEN, DATABASE_ID가 설정되어 있는지 확인하세요.")
    sys.exit(1)

openai_client = OpenAI(api_key=OPENAI_API_KEY)
notion = Client(auth=NOTION_TOKEN)

# ==============================================================================
# 2. 기업 목록 및 별칭 정의 (Multi-select 정규화용)
# ==============================================================================
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
    # Intel
    "Intel": "인텔(INTC)",
    "Intel Corporation": "인텔(INTC)",
    "INTC": "인텔(INTC)",
    "Intel Corp": "인텔(INTC)",

    # NVIDIA
    "NVIDIA": "엔비디아(NVIDIA)",
    "Nvidia": "엔비디아(NVIDIA)",
    "Nvidia Corp.": "엔비디아(NVIDIA)",
    "Nvidia Corp": "엔비디아(NVIDIA)",

    # AMD
    "AMD": "AMD",
    "Advanced Micro Devices": "AMD",
    "Advanced Micro Devices Inc": "AMD",

    # Samsung
    "Samsung": "삼성전자",
    "Samsung Electronics": "삼성전자",
    "Samsung Electronics Co.": "삼성전자",
    "삼성": "삼성전자",

    # SK hynix
    "SK hynix": "SK하이닉스",
    "SK Hynix": "SK하이닉스",
    "SKHynix": "SK하이닉스",
    "SK 하이닉스": "SK하이닉스",

    # Apple
    "Apple": "애플(AAPL)",
    "Apple Inc.": "애플(AAPL)",
    "Apple Inc": "애플(AAPL)",

    # Micron
    "Micron": "마이크론(MU)",
    "Micron Technology": "마이크론(MU)",
    "Micron Tech": "마이크론(MU)",

    # TSMC
    "TSMC": "TSMC",
    "Taiwan Semiconductor Manufacturing": "TSMC",
    "Taiwan Semiconductor Manufacturing Co": "TSMC",
    "Taiwan Semiconductor": "TSMC",

    # ASML
    "ASML": "ASML",
    "ASML Holding": "ASML",

    # Applied Materials
    "Applied Materials": "어플라이드 머티리얼즈(AMAT)",
    "AMAT": "어플라이드 머티리얼즈(AMAT)",

    # Lam Research
    "Lam Research": "램리서치(LRCX)",
    "Lam": "램리서치(LRCX)",
    "LRCX": "램리서치(LRCX)",

    # Tokyo Electron
    "Tokyo Electron": "도쿄일렉트론(TEL)",
    "TEL": "도쿄일렉트론(TEL)",
    "Tokyo Electron Limited": "도쿄일렉트론(TEL)",

    # KLA
    "KLA": "KLA",
    "KLA Corporation": "KLA",
    "KLA-Tencor": "KLA",

    # Qualcomm
    "Qualcomm": "퀄컴(QCOM)",
    "Qualcomm Inc": "퀄컴(QCOM)",

    # Broadcom
    "Broadcom": "브로드컴(AVGO)",
    "Broadcom Inc": "브로드컴(AVGO)",

    # Marvell
    "Marvell": "마벨(MRVL)",
    "Marvell Technology": "마벨(MRVL)",

    # Kioxia
    "Kioxia": "키옥시아(Kioxia)",
    "Kioxia Holdings": "키옥시아(Kioxia)",

    # Solidigm
    "Solidigm": "솔리다임(Solidigm)",

    # Western Digital
    "Western Digital": "웨스턴디지털(WDC)",
    "WDC": "웨스턴디지털(WDC)",

    # SanDisk
    "SanDisk": "샌디스크(SanDisk)",

    # Synopsys
    "Synopsys": "시놉시스(SNPS)",

    # Cadence
    "Cadence": "케이던스(CDNS)",
    "Cadence Design Systems": "케이던스(CDNS)",

    # ARM
    "ARM": "ARM",
    "Arm": "ARM",
    "Arm Holdings": "ARM",

    # GlobalFoundries
    "GlobalFoundries": "글로벌파운드리스(GFS)",
    "GF": "글로벌파운드리스(GFS)",

    # Texas Instruments
    "Texas Instruments": "텍사스 인스트루먼트(TXN)",
    "TI": "텍사스 인스트루먼트(TXN)",

    # ON Semiconductor
    "ON Semiconductor": "온세미(ON)",
    "ON Semi": "온세미(ON)",
    "onsemi": "온세미(ON)",

    # Renesas
    "Renesas": "르네사스",
    "Renesas Electronics": "르네사스",

    # Infineon
    "Infineon": "인피니온(IFX)",
    "Infineon Technologies": "인피니온(IFX)",

    # NXP
    "NXP": "NXP",
    "NXP Semiconductors": "NXP",

    # STMicroelectronics
    "STMicroelectronics": "ST마이크로일렉트로닉스(STM)",
    "STM": "ST마이크로일렉트로닉스(STM)",

    # 기타 주요기업 매핑
    "Anthropic": "앤트로픽(Anthropic)",
    "HPSP": "HPSP",
    "Advantest": "어드반테스트(Advantest)",
    "Teradyne": "테라다인(TER)",
    "Cirrus Logic": "시러스로직(CRUS)",
    "Soitec": "소이텍(Soitec)",
    "Merck": "머크(Merck)",
    "Resonac": "레조낙(Resonac)",
    "Shin-Etsu": "신에츠(Shin-Etsu)",
    "Nikon": "니콘(Nikon)",
    "Canon": "캐논(Canon)",
    "DISCO": "디스코(DISCO)"
}


def normalize_companies(raw_companies):
    """
    GPT가 추출해준 원본 기업명 리스트를 정규화하여
    ALLOWED_COMPANIES에 정의된 정확한 이름만 중복 없이 반환합니다.
    """
    result = []
    if not raw_companies:
        return result

    for company in raw_companies:
        clean_name = company.strip()
        if not clean_name:
            continue

        # 1. ALLOWED_COMPANIES에 직접 존재하는 경우
        if clean_name in ALLOWED_COMPANIES:
            result.append(clean_name)
            continue

        # 2. ALIASES에 정의되어 매핑 가능한 경우
        if clean_name in COMPANY_ALIASES:
            mapped = COMPANY_ALIASES[clean_name]
            if mapped in ALLOWED_COMPANIES:
                result.append(mapped)

    # 순서 유지하며 중복 제거
    return list(dict.fromkeys(result))


# ==============================================================================
# 3. RSS 피드 정의 및 수집 함수
# ==============================================================================
FEEDS = [
    {"name": "EE Times", "url": "https://www.eetimes.com/feed/"},
    {"name": "SemiAnalysis", "url": "https://www.semianalysis.com/feed"},
    {"name": "Tom's Hardware", "url": "https://www.tomshardware.com/feeds/all"},
]


def fetch_full_article_content(url):
    """기사 URL로부터 본문 텍스트 스크래핑"""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            for element in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
                element.decompose()

            article_body = (
                soup.find("div", class_="entry-content")
                or soup.find("div", class_="post-content")
                or soup.find("article")
                or soup.find("div", class_="article-body")
            )

            paragraphs = article_body.find_all(["p", "h2", "h3", "li"]) if article_body else soup.find_all("p")
            full_text = "\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
            return full_text.strip()
    except Exception as e:
        print(f"⚠️ [스크래핑 경고] ({url}): {e}")
    return ""


def fetch_past_24h_articles():
    """최근 24시간 동안 수집된 RSS 기사 파싱"""
    articles = []
    now = datetime.datetime.now(datetime.timezone.utc)
    twenty_four_hours_ago = now - datetime.timedelta(hours=24)

    for feed_info in FEEDS:
        try:
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
        except Exception as e:
            print(f"⚠️ [RSS 피드 읽기 오류] {feed_info['name']}: {e}")

    return articles


def check_url_exists(link):
    """Notion 데이터베이스에 이미 등록된 URL인지 중복 확인"""
    try:
        response = notion.databases.query(
            database_id=DATABASE_ID,
            filter={"property": "URL", "url": {"equals": link}}
        )
        return len(response.get("results", [])) > 0
    except Exception as e:
        print(f"⚠️ [Notion DB URL 조회 오류]: {e}")
        return False


# ==============================================================================
# 4. GPT 기술 심층 분석 (현직 공정기술 엔지니어 수준)
# ==============================================================================
def analyze_with_llm(title, content, source_name):
    """삼성전자/SK하이닉스 수석 엔지니어 시각의 심층 기술 분석 수행"""
    system_prompt = (
        "너는 삼성전자와 SK하이닉스에서 15년 이상 근무한 반도체 공정·소자·패키징 수석 엔지니어이자 최고 기술 자문위원이다. "
        "TSMC, Intel, NVIDIA, ASML의 최신 반도체 기술 동향 및 제조 공정을 전문 분석한다. "
        "기사를 단순 요약하지 말고 물리적/화학적 기술 원리, 단위 공정(Photolithography, Etching, Deposition, CMP 등), "
        "사용 장비 및 소재, 기술적 난이도(Yield Issue, Leakage Current, Thermal Management), 경쟁 기술과의 스펙 차이, "
        "반도체 산업 생태계에 미치는 파급 효과를 전문 공정용어로 명확하고 깊이 있게 설명하라. "
        "답변은 현직 공정기술/소자/패키징 엔지니어 교육 및 직무 역량 강화 자료 수준으로 상세하게 작성해야 한다."
    )

    truncated_content = content[:6500] if content else ""

    user_prompt = f"""
다음 반도체 기술 기사를 수석 엔지니어 시각에서 심층 분석하라.

출처: {source_name}
원문 제목: {title}

본문:
{truncated_content}

==========================
[중요도 평가 기준]
==========================
■ 상
- HBM / CXL / 차세대 메모리
- High-NA EUV / EUV 노광 공정
- GAA(MBCFET) / CFET / 3D Transistor
- Backside Power Delivery (BSPDN) / PowerVia
- Chiplet / Advanced Packaging (CoWoS, Foveros, I-Cube 등)
- Hybrid Bonding / Direct Bonding
- 첨단 파운드리 공정 (3nm 이하) 및 AI 반도체 핵심 패러다임 변화

■ 중
- 설비 투자(CapEx) 및 파운드리 경쟁
- 수율 개선(Yield Enhancement) 및 defect 제어
- 글로벌 반도체 공급망 변화 / 생산라인 증설
- 신규 장비·소재(ALDs, High-k, EUV Pellicle 등) 도입
- 후공정(OSAT) 및 차량용 반도체 동향

■ 하
- 단순 실적 발표 / 단순 주가 변동
- 일반 IT 제품 리뷰 및 소비자 가전/게임 관련 뉴스
- 확인되지 않은 단순 루머성 기사

==========================
[관련 기업 추출]
==========================
기사에서 다루는 주요 반도체 관련 기업명을 쉼표(,)로 구분하여 기술하라. (최대 10개)
언급이 없으면 빈칸으로 남겨라.
예시: Intel, NVIDIA, TSMC, Samsung Electronics, SK hynix, ASML, Lam Research, Micron

==========================
[응답 형식]
==========================

[한글 제목]
핵심 기술 내용이 명확히 드러나는 한국어 직관적 제목

[중요도]
상 / 중 / 하 중 하나만 명시

[관련 기업]
회사1, 회사2, 회사3

[본문 내용]

1. 기술 심층 분석 (10문장 이상)
다음 항목을 철저히 포함하여 기술할 것:
- 핵심 기술의 물리적/소자적 작동 원리
- 기존 공정/기술 대비 성능, 전력 효율, 면적(PPA) 이점
- 공정 적용 분야 (노광, 식각, 증착, CMP, 패키징 등 특정 단위 공정 명시)
- 핵심 소모 장비 및 소재 (주요 장비사 및 소재명)
- 기술 구현 시 직면하는 기술적 난이도 및 한계 (열 질량, 수율, 기계적 변형 등)
- 경쟁사 기술 솔루션과의 차별점 및 기술 격차
- 반도체 산업 생태계 및 공급망에 미치는 영향 및 향후 발전 방향

2. 반도체 직무 시사점 (6문장 이상)
다음 직무별 시사점과 면접 포인트를 상세히 포함할 것:
- 공정기술 직무: 수율 확보 및 Defect 제어 관점
- 장비기술 직무: 장비 셋업, 가동률 및 Process Window 확보 관점
- 소자/설계 직무: Short Channel Effect 제어 및 PPA 최적화 관점
- 패키징/후공정 직무: Warpage, Thermal Dissipation, Interconnection 관점
- 기술 면접 예상 질문 및 답변 방향

3. 핵심 전문 키워드 (8개 이상)
(예시: HBM3e, CoWoS-S, High-NA EUV, BSPDN, GAAFET, Hybrid Bonding, ALD, TSV)
"""

    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=3000,
    )

    result_text = response.choices[0].message.content or ""

    # 1) 한글 제목 추출
    korean_title = title
    if "[한글 제목]" in result_text and "[중요도]" in result_text:
        try:
            korean_title = result_text.split("[한글 제목]")[1].split("[중요도]")[0].strip()
        except Exception:
            pass

    # 2) 중요도 추출
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

    # 중요도 "하" 기사는 등록하지 않고 건너뜀
    if importance == "하":
        return "SKIP", "", "", []

    # 3) 관련 기업 추출 및 정규화
    matched_companies = []
    if "[관련 기업]" in result_text:
        try:
            comp_part = result_text.split("[관련 기업]")[1]
            if "[본문 내용]" in comp_part:
                comp_part = comp_part.split("[본문 내용]")[0]
            elif "1." in comp_part:
                comp_part = comp_part.split("1.")[0]

            raw_companies = [c.strip() for c in comp_part.strip().split(",") if c.strip()]
            matched_companies = normalize_companies(raw_companies)
        except Exception:
            pass

    body_text = result_text.strip()
    return importance, korean_title, body_text, matched_companies


# ==============================================================================
# 5. Notion Page 생성 (API 최신 스키마 준수)
# ==============================================================================
def create_notion_page(korean_title, importance, source, link, date_str, body_text, companies):
    """
    Notion REST API 공식 스키마에 맞춰 페이지 및 블록 생성.
    - Title: title
    - Select: select (출처)
    - URL: url (URL)
    - Date: date (날짜)
    - Multi-select: multi_select (관련 기업)
    """

    # Properties 파라미터 구성
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

    # 날짜 속성 안전 검증 및 등록 (YYYY-MM-DD)
    if date_str and isinstance(date_str, str) and len(date_str.strip()) >= 10:
        clean_date = date_str.strip()[:10]
        properties["날짜"] = {
            "date": {
                "start": clean_date
            }
        }

    # Multi-select 속성 정규화 등록
    if companies and isinstance(companies, list):
        properties["관련 기업"] = {
            "multi_select": [{"name": comp} for comp in companies]
        }
    else:
        properties["관련 기업"] = {
            "multi_select": []
        }

    # Notion Block Content 구성 (2,000자 초과 방지)
    content_blocks = []
    chunk_size = 1900
    chunks = [body_text[i:i + chunk_size] for i in range(0, len(body_text), chunk_size)]

    for chunk in chunks:
        content_blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": chunk
                        }
                    }
                ]
            },
        })

    # Notion Page 생성 요청
    notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties=properties,
        children=content_blocks,
    )
    print(f"✅ [Notion 등록 성공] [{importance}] {korean_title}")


# ==============================================================================
# 6. 메인 실행 루프 (안전한 예외 처리 적용)
# ==============================================================================
def main():
    print("🚀 [프로세스 시작] 최근 24시간 반도체 기사 수집 및 Notion 자동화...")
    
    articles = fetch_past_24h_articles()
    print(f"📰 [수집 결과] 총 {len(articles)}개의 기사가 수집되었습니다.")

    success_count = 0
    skip_count = 0
    fail_count = 0

    for idx, article in enumerate(articles, 1):
        print(f"\n------------------------------------------------------------")
        print(f"[{idx}/{len(articles)}] 기사 처리 중: {article['title']}")

        try:
            # 1. Notion 중복 검사
            if check_url_exists(article["link"]):
                print(f"⏩ [중복 스킵] 이미 등록된 URL입니다: {article['link']}")
                skip_count += 1
                continue

            # 2. GPT 심층 분석
            importance, korean_title, body_text, companies = analyze_with_llm(
                article["title"], article["content"], article["source"]
            )

            if importance == "SKIP":
                print(f"⏩ [중요도 '하' 스킵] 기술 분석 대상에서 제외되었습니다.")
                skip_count += 1
                continue

            print(f"🔍 [분석 완료] 중요도: {importance} | 매칭된 기업: {companies}")

            # 3. Notion 등록
            create_notion_page(
                korean_title=korean_title,
                importance=importance,
                source=article["source"],
                link=article["link"],
                date_str=article["date"],
                body_text=body_text,
                companies=companies,
            )
            success_count += 1

        except Exception as e:
            # 개별 기사 등록 중 예외가 발생하더라도 traceback만 출력하고 루프를 계속 진행
            fail_count += 1
            print(f"❌ [기사 처리 중 오류 발생] 다음 기사로 계속 진행합니다.")
            print(f"오류 내용: {e}")
            traceback.print_exc()

    print("\n============================================================")
    print(f"🎉 [작업 완료] 성공: {success_count}건 | 스킵: {skip_count}건 | 실패: {fail_count}건")
    print("============================================================")


if __name__ == "__main__":
    main()