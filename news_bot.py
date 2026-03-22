import html
import os
import re
import time
from difflib import SequenceMatcher
from typing import Dict, List, Any

import requests

from config import (
    NAVER_CLIENT_ID,
    NAVER_CLIENT_SECRET,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    SEARCH_DISPLAY,
    FINAL_SEND_COUNT,
    TEAM_KEYWORDS,
)

NAVER_NEWS_API_URL = "https://openapi.naver.com/v1/search/news.json"
TELEGRAM_SEND_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

DEBUG = True

# -----------------------------
# 제외 키워드
# -----------------------------
EXCLUDE_KEYWORDS = [
    # 스포츠
    "축구", "야구", "농구", "배구", "골프", "테니스", "epl", "mlb", "kbo", "k리그",
    "프로야구", "프로축구", "라운드", "우승", "타율", "홈런", "득점", "선발", "투수", "타자",
    "[mhn포토]", "포토", "화보", "라커룸", "경기", "승부", "매치",

    # 연예
    "연예", "방송", "드라마", "예능", "아이돌", "가수", "배우", "컴백", "앨범", "팬미팅",
    "시사회", "주연", "조연", "걸그룹", "보이그룹", "OST", "영화 개봉",

    # 지역/생활
    "맛집", "날씨", "주말", "나들이", "축제", "전시", "여행", "관광", "벚꽃", "단풍",
    "지역소식", "동네", "개장", "휴무", "행사", "체험", "먹거리",

    # 기타 잡성 기사
    "운세", "별자리", "오늘의 운세", "띠별", "궁합",
]

# -----------------------------
# 제외 언론사
# 포함 여부로 체크
# -----------------------------
EXCLUDE_SOURCES = [
    "스포츠",
    "OSEN",
    "엑스포츠뉴스",
    "스포츠조선",
    "스포츠서울",
    "스타뉴스",
    "텐아시아",
    "MHN",
    "마이데일리",
    "뉴스엔",
    "스포티비",
]

# -----------------------------
# 팀별 가중치
# -----------------------------
TEAM_PRIORITY_KEYWORDS = {
    "은행팀": {
        "실적": 3,
        "순이익": 3,
        "연체율": 4,
        "고정이하여신": 4,
        "건전성": 4,
        "CET1": 5,
        "자사주": 4,
        "배당": 3,
        "주주환원": 5,
        "밸류업": 5,
        "NPL": 4,
        "대손": 3,
        "충당금": 3,
        "금감원": 2,
        "금융위": 2,
        "디지털": 2,
        "AI": 2,
        "해외법인": 3,
        "인수": 3,
        "매각": 3,
    },
    "보험팀": {
        "실적": 3,
        "순이익": 3,
        "CSM": 5,
        "지급여력": 5,
        "K-ICS": 5,
        "손해율": 4,
        "보험영업": 3,
        "신계약": 4,
        "자본확충": 4,
        "배당": 2,
        "자사주": 2,
        "매각": 3,
        "인수": 3,
        "금감원": 2,
    },
    "제2금융팀": {
        "PF": 5,
        "대손": 4,
        "충당금": 4,
        "연체율": 4,
        "건전성": 4,
        "조달": 3,
        "캐피탈": 3,
        "저축은행": 3,
        "카드": 3,
        "상호금융": 3,
        "새마을금고": 3,
        "부실채권": 4,
        "NPL": 4,
        "유동성": 4,
        "금감원": 2,
        "금융위": 2,
    },
}


def debug_log(message: str) -> None:
    if DEBUG:
        print(f"[DEBUG] {message}")


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_title(title: str) -> str:
    title = strip_html(title).lower()
    title = re.sub(r"[\"'‘’“”\[\]\(\)\-–—:;,./!?]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


def similar(a: str, b: str, threshold: float = 0.88) -> bool:
    return SequenceMatcher(None, a, b).ratio() >= threshold


def contains_exclude_keyword(text: str) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in EXCLUDE_KEYWORDS)


def is_excluded_source(source: str) -> bool:
    if not source:
        return False
    return any(ex.lower() in source.lower() for ex in EXCLUDE_SOURCES)


def score_article(team_name: str, title: str, desc: str) -> int:
    weights = TEAM_PRIORITY_KEYWORDS.get(team_name, {})
    text = f"{title} {desc}".lower()

    score = 0
    for keyword, weight in weights.items():
        if keyword.lower() in text:
            score += weight

    # 제목에 키워드가 있으면 가중치 조금 더
    title_lower = title.lower()
    for keyword, weight in weights.items():
        if keyword.lower() in title_lower:
            score += weight

    return score


def search_news(keyword: str) -> List[Dict[str, Any]]:
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }
    params = {
        "query": keyword,
        "display": SEARCH_DISPLAY,
        "start": 1,
        "sort": "date",
    }

    debug_log(f"네이버 검색 요청 keyword={keyword}, params={params}")

    try:
        response = requests.get(
            NAVER_NEWS_API_URL,
            headers=headers,
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        items = data.get("items", [])
        debug_log(f"검색 완료 keyword={keyword}, fetched={len(items)}")
        return items
    except Exception as e:
        print(f"[ERROR] 네이버 검색 실패 keyword={keyword}: {e}")
        return []


def filter_articles(team_name: str, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered = []

    for item in articles:
        title = strip_html(item.get("title", ""))
        desc = strip_html(item.get("description", ""))
        link = item.get("originallink") or item.get("link") or ""
        pub_date = item.get("pubDate", "")

        source = ""
        # 네이버 뉴스 API 응답엔 언론사명이 직접 없을 수 있어 제목/설명/링크로만 판단
        # 필요하면 별도 파싱 추가
        source_guess = f"{title} {desc} {link}"

        combined_text = f"{title} {desc}"

        if contains_exclude_keyword(combined_text):
            continue

        if is_excluded_source(source_guess):
            continue

        filtered.append({
            "title": title,
            "description": desc,
            "link": link,
            "pubDate": pub_date,
            "source": source,
            "team": team_name,
        })

    debug_log(f"{team_name} 1차 필터 후={len(filtered)}")
    return filtered


def dedupe_articles(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # 1) 완전 중복 제거
    unique = []
    seen_titles = set()

    for item in articles:
        norm = normalize_title(item["title"])
        if norm in seen_titles:
            continue
        seen_titles.add(norm)
        unique.append(item)

    debug_log(f"완전중복 제거 후={len(unique)}")

    # 2) 유사 중복 제거
    deduped = []
    saved_titles = []

    for item in unique:
        norm = normalize_title(item["title"])
        is_dup = False

        for saved in saved_titles:
            if similar(norm, saved, threshold=0.88):
                is_dup = True
                break

        if not is_dup:
            deduped.append(item)
            saved_titles.append(norm)

    debug_log(f"유사중복 제거 후={len(deduped)}")
    return deduped


def collect_team_articles(team_name: str, keywords: List[str]) -> List[Dict[str, Any]]:
    all_articles = []

    for keyword in keywords:
        items = search_news(keyword)
        debug_log(f"{team_name} keyword={keyword} 검색결과={len(items)}")

        filtered = filter_articles(team_name, items)
        debug_log(f"{team_name} keyword={keyword} 필터후={len(filtered)}")

        all_articles.extend(filtered)
        time.sleep(0.2)

    debug_log(f"{team_name} 전체 수집 합계={len(all_articles)}")

    deduped = dedupe_articles(all_articles)

    for item in deduped:
        item["score"] = score_article(team_name, item["title"], item["description"])

    # 점수 우선, 동점이면 최신이 앞
    ranked = sorted(
        deduped,
        key=lambda x: (x.get("score", 0), x.get("pubDate", "")),
        reverse=True,
    )

    final_items = ranked[:FINAL_SEND_COUNT]

    debug_log(
        f"{team_name} 최종 정리: 검색합계={len(all_articles)}, "
        f"중복제거후={len(deduped)}, 최종발송={len(final_items)}"
    )

    return final_items


def build_team_message(team_name: str, articles: List[Dict[str, Any]]) -> str:
    now_str = time.strftime("%Y-%m-%d %H:%M")

    lines = [
        "[즉시 뉴스 브리핑]",
        now_str,
        "",
        f"<{team_name}>",
    ]

    if not articles:
        lines.append("전송할 기사가 없습니다.")
        return "\n".join(lines)

    for idx, item in enumerate(articles, start=1):
        title = item["title"]
        link = item["link"]
        score = item.get("score", 0)

        lines.append(f"{idx}. {title}")
        lines.append(link)
        lines.append(f"(score: {score})")
        lines.append("")

    return "\n".join(lines).strip()


def send_telegram_message(text: str) -> bool:
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(TELEGRAM_SEND_URL, data=payload, timeout=15)
        response.raise_for_status()
        result = response.json()
        if not result.get("ok"):
            print(f"[ERROR] 텔레그램 전송 실패: {result}")
            return False
        return True
    except Exception as e:
        print(f"[ERROR] 텔레그램 전송 예외: {e}")
        return False


def main():
    debug_log(f"SEARCH_DISPLAY={SEARCH_DISPLAY}")
    debug_log(f"FINAL_SEND_COUNT={FINAL_SEND_COUNT}")

    for team_name, keywords in TEAM_KEYWORDS.items():
        print(f"\n===== {team_name} 시작 =====")
        articles = collect_team_articles(team_name, keywords)
        message = build_team_message(team_name, articles)

        success = send_telegram_message(message)
        if success:
            print(f"[INFO] {team_name} 텔레그램 전송 완료 ({len(articles)}건)")
        else:
            print(f"[ERROR] {team_name} 텔레그램 전송 실패")

        time.sleep(1)


if __name__ == "__main__":
    main()