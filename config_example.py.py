# 네이버 API
NAVER_CLIENT_ID = "YOUR_NAVER_CLIENT_ID"
NAVER_CLIENT_SECRET = "YOUR_NAVER_CLIENT_SECRET"

# 텔레그램 봇
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

# 뉴스가 발송될 채널/방 Chat ID
TELEGRAM_CHAT_ID = "YOUR_TELEGRAM_CHAT_ID"

# 허용 사용자 ID
ALLOWED_USER_IDS = []

# 네이버 검색 시 키워드당 가져올 기사 수
SEARCH_DISPLAY = 40

# 팀별 최종 발송 기사 수
DISPLAY_COUNT_PER_TEAM = 20

# 기본 팀별 키워드
DEFAULT_TEAM_KEYWORDS = {
    "은행팀": [
        "은행",
        "시중은행",
        "금융지주",
        "국민은행",
        "신한은행",
        "하나은행",
        "우리은행",
        "기업은행",
        "농협은행",
        "인터넷은행",
        "카카오뱅크",
        "토스뱅크",
        "케이뱅크",
    ],
    "보험팀": [
        "보험",
        "생명보험",
        "손해보험",
        "삼성생명",
        "한화생명",
        "교보생명",
        "메리츠화재",
        "DB손해보험",
        "현대해상",
        "동양생명",
        "ABL생명",
    ],
    "제2금융팀": [
        "저축은행",
        "캐피탈",
        "카드사",
        "부동산 PF",
        "상호금융",
        "새마을금고",
        "신협",
        "여전채",
        "카드론",
        "캐피탈사",
    ],
}