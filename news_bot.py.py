import json
import os
import re
import html
import logging
import sys
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from config import (
    NAVER_CLIENT_ID,
    NAVER_CLIENT_SECRET,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    ALLOWED_USER_IDS,
    DEFAULT_TEAM_KEYWORDS,
    SEARCH_DISPLAY,
    DISPLAY_COUNT_PER_TEAM,
)

KST = ZoneInfo("Asia/Seoul")

KEYWORDS_FILE = "keywords.json"
SENT_ARTICLES_FILE = "sent_articles.json"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)


def is_allowed_user(user_id: int) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    return user_id in ALLOWED_USER_IDS


def today_str() -> str:
    return datetime.now(KST).strftime("%Y-%m-%d")


def init_keywords_file():
    if not os.path.exists(KEYWORDS_FILE):
        with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_TEAM_KEYWORDS, f, ensure_ascii=False, indent=2)


def load_keywords() -> dict:
    init_keywords_file()
    with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        data = {
            "은행팀": data,
            "보험팀": [],
            "제2금융팀": [],
        }
        save_keywords(data)

    return data


def save_keywords(team_keywords: dict):
    cleaned_data = {}

    for team, keywords in team_keywords.items():
        cleaned = []
        seen = set()

        for kw in keywords:
            kw = kw.strip()
            if kw and kw not in seen:
                cleaned.append(kw)
                seen.add(kw)

        cleaned_data[team] = cleaned

    with open(KEYWORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)


def init_sent_articles_file():
    if not os.path.exists(SENT_ARTICLES_FILE):
        with open(SENT_ARTICLES_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)


def load_sent_articles() -> dict:
    init_sent_articles_file()
    with open(SENT_ARTICLES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def save_sent_articles(data: dict):
    with open(SENT_ARTICLES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_today_sent_links() -> set[str]:
    data = load_sent_articles()
    return set(data.get(today_str(), []))


def add_today_sent_links(links: list[str]):
    data = load_sent_articles()
    today = today_str()

    existing = set(data.get(today, []))
    existing.update(links)
    data[today] = sorted(existing)

    keys = sorted(data.keys())
    if len(keys) > 7:
        for old_key in keys[:-7]:
            del data[old_key]

    save_sent_articles(data)


def clean_title(title: str) -> str:
    title = re.sub(r"</?b>", "", title)
    title = html.unescape(title)
    return title.strip()


def is_sports_article(title: str, link: str) -> bool:
    title_lower = title.lower()
    link_lower = link.lower()

    sports_link_patterns = [
        "sports.naver.com",
        "/sports/",
        "sid=107",
    ]
    for pattern in sports_link_patterns:
        if pattern in link_lower:
            return True

    sports_keywords = [
        "mhn포토", "골프", "축구", "야구", "농구", "배구",
        "프로야구", "메이저리그", "mlb", "kbo", "k리그",
        "챔피언스리그", "투수", "타자", "홈런", "득점",
        "라운드", "우승", "준우승", "패럴림픽", "올림픽",
        "선수", "감독", "4강", "결승", "시즌", "연장전"
    ]
    return any(keyword.lower() in title_lower for keyword in sports_keywords)


def is_entertainment_article(title: str, link: str) -> bool:
    title_lower = title.lower()
    link_lower = link.lower()

    entertainment_link_patterns = [
        "entertain.naver.com",
        "m.entertain.naver.com",
        "/entertain/",
        "sid=106",
    ]
    for pattern in entertainment_link_patterns:
        if pattern in link_lower:
            return True

    entertainment_keywords = [
        "아이돌", "컴백", "팬미팅", "드라마", "예능", "배우",
        "가수", "걸그룹", "보이그룹", "콘서트", "앨범", "티저",
        "주연", "출연", "방송인", "연예", "열애", "결혼", "이혼",
        "영화", "시사회", "ost", "뮤직비디오", "화보", "셀카",
        "근황", "패션", "레드카펫"
    ]
    return any(keyword.lower() in title_lower for keyword in entertainment_keywords)


def is_local_life_article(title: str, link: str) -> bool:
    title_lower = title.lower()
    link_lower = link.lower()

    local_life_keywords = [
        "펫로스", "반려견", "반려묘", "산책", "동네", "마을", "주민",
        "행사", "축제", "공연", "강연", "전시", "체험", "캠페인",
        "봉사", "나눔", "기부", "후원", "사연", "미담", "훈훈",
        "개최", "성료", "성황", "참가자", "참여자", "지역사회",
        "주민센터", "복지관", "도서관", "청소년센터", "마을회관",
        "포항", "창원", "진주", "구미", "여수", "순천", "목포",
        "춘천", "원주", "강릉", "전주", "군산", "익산", "제주",
        "서귀포", "천안", "아산", "청주", "충주", "김해", "양산"
    ]

    local_link_patterns = [
        "/life/",
        "/local/",
        "/region/",
        "/society/",
    ]

    for pattern in local_link_patterns:
        if pattern in link_lower:
            return True

    return any(keyword.lower() in title_lower for keyword in local_life_keywords)


def is_unwanted_article(title: str, link: str) -> bool:
    return (
        is_sports_article(title, link)
        or is_entertainment_article(title, link)
        or is_local_life_article(title, link)
    )


def fetch_news_from_naver(keyword: str) -> list[dict]:
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
    }

    url = "https://openapi.naver.com/v1/search/news.json"
    params = {
        "query": keyword,
        "display": SEARCH_DISPLAY,
        "sort": "date",
    }

    response = requests.get(url, headers=headers, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    articles = []
    for item in data.get("items", []):
        title = clean_title(item.get("title", ""))
        link = item.get("link", "")
        pub_date = item.get("pubDate", "")

        if title and link and not is_unwanted_article(title, link):
            articles.append(
                {
                    "keyword": keyword,
                    "title": title,
                    "link": link,
                    "pub_date": pub_date,
                }
            )

    return articles


def collect_team_articles() -> dict:
    team_keywords = load_keywords()
    today_sent_links = get_today_sent_links()

    result = {}

    for team_name, keywords in team_keywords.items():
        team_articles = []

        for keyword in keywords:
            try:
                team_articles.extend(fetch_news_from_naver(keyword))
            except Exception as e:
                logging.exception("키워드 조회 실패: %s | %s", keyword, e)

        seen_links = set()
        unique_articles = []

        for article in team_articles:
            link = article["link"]
            if link not in seen_links:
                seen_links.add(link)
                unique_articles.append(article)

        new_articles = [
            article for article in unique_articles
            if article["link"] not in today_sent_links
        ]

        result[team_name] = new_articles[:DISPLAY_COUNT_PER_TEAM]

    return result


def make_team_message(team_name: str, articles: list[dict], label: str = "뉴스 브리핑") -> str:
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    message = f"[{label}]\n{now}\n\n"
    message += f"<{team_name}>\n"

    if not articles:
        message += "새 기사가 없습니다."
        return message

    for idx, article in enumerate(articles, start=1):
        message += f"{idx}. {article['title']}\n{article['link']}\n\n"

    return message.strip()


def split_message(text: str, max_length: int = 3500) -> list[str]:
    chunks = []
    current = ""

    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > max_length:
            if current:
                chunks.append(current)
            current = line
        else:
            current += line

    if current:
        chunks.append(current)

    return chunks


async def send_news(app, label: str = "뉴스 브리핑") -> str:
    team_articles = collect_team_articles()

    sent_links = []
    sent_summary = []

    for team_name, articles in team_articles.items():
        team_message = make_team_message(team_name, articles, label=label)
        chunks = split_message(team_message)

        for chunk in chunks:
            await app.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=chunk,
                disable_web_page_preview=True,
            )

        if articles:
            sent_links.extend([article["link"] for article in articles])

        sent_summary.append(f"{team_name}: {len(articles)}건")

    if sent_links:
        add_today_sent_links(sent_links)

    return " / ".join(sent_summary)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_allowed_user(user.id):
        return

    text = (
        "뉴스봇 준비 완료입니다.\n\n"
        "사용 가능한 명령어:\n"
        "/list - 현재 팀별 키워드 보기\n"
        "/add 팀명 키워드 - 키워드 추가\n"
        "/remove 팀명 키워드 - 키워드 삭제\n"
        "/sendnow - 즉시 뉴스 발송\n"
        "/myid - 내 텔레그램 사용자 ID 확인\n"
        "/help - 도움말"
    )
    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_allowed_user(user.id):
        return

    text = (
        "명령어 안내\n\n"
        "/list\n"
        "/add 은행팀 KB금융\n"
        "/add 보험팀 IFRS17\n"
        "/add 제2금융팀 카드론\n"
        "/remove 은행팀 KB금융\n"
        "/remove 보험팀 IFRS17\n"
        "/sendnow\n"
        "/myid"
    )
    await update.message.reply_text(text)


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    await update.message.reply_text(f"당신의 텔레그램 사용자 ID: {user.id}")


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_allowed_user(user.id):
        return

    team_keywords = load_keywords()
    text = "[현재 팀별 키워드]\n\n"

    for team_name, keywords in team_keywords.items():
        text += f"<{team_name}>\n"
        if keywords:
            text += "\n".join(f"- {kw}" for kw in keywords)
        else:
            text += "등록된 키워드가 없습니다."
        text += "\n\n"

    await update.message.reply_text(text.strip())


async def add_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_allowed_user(user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "형식: /add 팀명 키워드\n예: /add 은행팀 KB금융"
        )
        return

    team_name = context.args[0].strip()
    new_keyword = " ".join(context.args[1:]).strip()

    team_keywords = load_keywords()

    if team_name not in team_keywords:
        await update.message.reply_text(
            f"등록되지 않은 팀입니다: {team_name}\n현재 팀: {', '.join(team_keywords.keys())}"
        )
        return

    if new_keyword in team_keywords[team_name]:
        await update.message.reply_text(
            f"이미 등록된 키워드입니다: [{team_name}] {new_keyword}"
        )
        return

    team_keywords[team_name].append(new_keyword)
    save_keywords(team_keywords)

    await update.message.reply_text(
        f"키워드 추가 완료: [{team_name}] {new_keyword}"
    )


async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_allowed_user(user.id):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "형식: /remove 팀명 키워드\n예: /remove 은행팀 KB금융"
        )
        return

    team_name = context.args[0].strip()
    target_keyword = " ".join(context.args[1:]).strip()

    team_keywords = load_keywords()

    if team_name not in team_keywords:
        await update.message.reply_text(
            f"등록되지 않은 팀입니다: {team_name}\n현재 팀: {', '.join(team_keywords.keys())}"
        )
        return

    if target_keyword not in team_keywords[team_name]:
        await update.message.reply_text(
            f"등록되지 않은 키워드입니다: [{team_name}] {target_keyword}"
        )
        return

    team_keywords[team_name].remove(target_keyword)
    save_keywords(team_keywords)

    await update.message.reply_text(
        f"키워드 삭제 완료: [{team_name}] {target_keyword}"
    )


async def sendnow_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user or not is_allowed_user(user.id):
        return

    await update.message.reply_text("즉시 발송을 시작합니다.")

    try:
        summary = await send_news(context.application, label="즉시 뉴스 브리핑")
        await update.message.reply_text(f"발송 완료.\n{summary}")
    except Exception as e:
        await update.message.reply_text(f"발송 중 에러 발생: {e}")


def get_oneshot_label(arg: str) -> str:
    mapping = {
        "morning": "오전 뉴스 브리핑",
        "afternoon": "오후 뉴스 브리핑",
        "evening": "저녁 뉴스 브리핑",
        "now": "즉시 뉴스 브리핑",
    }
    return mapping.get(arg, "뉴스 브리핑")


async def run_oneshot(mode: str):
    init_keywords_file()
    init_sent_articles_file()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    label = get_oneshot_label(mode)
    summary = await send_news(app, label=label)
    print(f"1회 발송 완료: {summary}")


def run_bot():
    init_keywords_file()
    init_sent_articles_file()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("myid", myid_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("add", add_command))
    app.add_handler(CommandHandler("remove", remove_command))
    app.add_handler(CommandHandler("sendnow", sendnow_command))

    print("뉴스봇 실행 중...")
    print("명령어: /list /add /remove /sendnow /myid")

    app.run_polling()


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--oneshot":
        mode = sys.argv[2].strip().lower()
        asyncio.run(run_oneshot(mode))
    else:
        run_bot()


if __name__ == "__main__":
    main()