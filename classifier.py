from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
RULES_PATH = BASE_DIR / "config" / "rules.json"


@dataclass(frozen=True)
class CategoryRule:
    path: str
    keywords: tuple[str, ...]
    priority: int


LOW_SIGNAL_KEYWORDS = frozenset(
    {
        "app",
        "apps",
        "music",
        "video",
        "videos",
        "news",
        "browser",
        "maps",
        "navigation",
        "payment",
        "payments",
        "investment",
        "productivity",
        "security",
        "policy",
    }
)

SUPPRESSED_PHRASES_BY_KEYWORD: dict[str, tuple[str, ...]] = {
    "policy": ("privacy policy", "refund policy"),
}

P2P_LOAN_PATH = "金融 (Finance) → 借贷 (Loan) → P2P借贷 (Peer-to-Peer Lending)"
MICROLOAN_PATH = "金融 (Finance) → 借贷 (Loan) → 小额现金贷 (Microloan / Cash Loan)"
INSTALLMENT_LOAN_PATH = "金融 (Finance) → 借贷 (Loan) → 分期消费贷款 (Installment / Buy Now Pay Later)"
BUSINESS_LOAN_PATH = "金融 (Finance) → 借贷 (Loan) → 企业/商户贷款（Business Loan / SME Loan）"
SECURED_LOAN_PATH = "金融 (Finance) → 借贷 (Loan) → 抵押贷 (Secured Loan / Collateral Loan)"
ACTION_GAME_PATH = "游戏 (Games) → 动作 (Action)"
ADVENTURE_GAME_PATH = "游戏 (Games) → 冒险 (Adventure)"
RPG_GAME_PATH = "游戏 (Games) → 角色扮演 (RPG)"
STRATEGY_GAME_PATH = "游戏 (Games) → 策略 (Strategy)"
CASUAL_GAME_PATH = "游戏 (Games) → 休闲 (Casual)"
COMPETITIVE_GAME_PATH = "游戏 (Games) → 竞技 (Competitive)"
BOARD_GAME_PATH = "游戏 (Games) → 棋牌 (Board/Card)"
SPORTS_INFO_PATH = "资讯 (Information) → 体育 (Sports)"
GAMBLING_FRAUD_PATH = "欺诈 (Fraud) → 赌博 (Gambling)"
BETTING_FRAUD_PATH = "欺诈 (Fraud) → 博彩 (Betting)"
TASK_SCAM_PATH = "欺诈 (Fraud) → 刷单返利 (Task/Rebate Scam)"

INTENT_SIGNAL_GROUPS: dict[str, tuple[tuple[str, ...], ...]] = {
    P2P_LOAN_PATH: (
        ("lender", "borrower"),
        ("funding", "borrower"),
        ("investor", "borrower"),
        ("pendana", "peminjam"),
        ("pendana", "imbal hasil"),
        ("pemberi dana", "peminjam"),
        ("invest", "loan"),
        ("fund", "borrowers"),
        ("return", "lenders"),
        ("pinjam meminjam",),
        ("danai", "pinjaman"),
        ("peer to peer",),
        ("p2p",),
        ("marketplace lending",),
    ),
    MICROLOAN_PATH: (
        ("cash loan",),
        ("pinjaman tunai",),
        ("dana tunai",),
        ("instant cash",),
        ("same day", "loan"),
        ("quick loan",),
        ("pinjaman cepat",),
        ("apply", "loan"),
        ("cash advance",),
        ("urgent cash",),
        ("apply", "cash"),
        ("online", "loan"),
        ("pinjaman", "cepat"),
        ("langsung cair",),
        ("cair cepat",),
        ("tanpa jaminan",),
        ("kebutuhan mendesak",),
        ("emergency", "cash"),
        ("short term", "loan"),
    ),
    INSTALLMENT_LOAN_PATH: (
        ("buy now pay later",),
        ("paylater",),
        ("bnpl",),
        ("installment", "shopping"),
        ("cicilan", "belanja"),
        ("pay in", "installments"),
        ("split", "payments"),
        ("checkout", "installment"),
        ("shopping", "credit"),
        ("tenor", "bulan"),
        ("cicilan", "bulanan"),
        ("belanja", "sekarang"),
        ("bayar", "nanti"),
        ("checkout", "paylater"),
        ("shopping", "paylater"),
        ("paylater", "checkout"),
        ("installment", "purchase"),
    ),
    BUSINESS_LOAN_PATH: (
        ("business", "loan"),
        ("merchant", "loan"),
        ("sme", "loan"),
        ("modal", "usaha"),
        ("working capital",),
        ("invoice financing",),
        ("business owner",),
        ("merchant financing",),
        ("usaha", "merchant"),
        ("dana", "usaha"),
        ("modal", "bisnis"),
        ("pinjaman", "usaha"),
        ("business", "capital"),
        ("merchant", "cashflow"),
        ("invoice", "funding"),
        ("warung", "usaha"),
        ("toko", "usaha"),
    ),
    SECURED_LOAN_PATH: (
        ("secured", "loan"),
        ("collateral", "loan"),
        ("loan", "collateral"),
        ("pinjaman", "jaminan"),
        ("pinjaman", "agunan"),
        ("jaminan", "bpkb"),
        ("jaminan", "sertifikat"),
        ("gadai", "emas"),
        ("gadai", "bpkb"),
        ("agunan", "pinjaman"),
        ("property", "collateral"),
        ("vehicle", "title"),
        ("sertifikat", "rumah"),
        ("bpkb", "mobil"),
        ("bpkb", "motor"),
    ),
}

NEGATIVE_SIGNAL_GROUPS: dict[str, tuple[tuple[str, ...], ...]] = {
    MICROLOAN_PATH: (
        ("shopping", "installment"),
        ("merchant", "business"),
        ("lender", "borrower"),
        ("invoice", "financing"),
    ),
    INSTALLMENT_LOAN_PATH: (
        ("cash loan",),
        ("pinjaman tunai",),
        ("working capital",),
        ("tanpa jaminan", "tunai"),
    ),
    BUSINESS_LOAN_PATH: (
        ("paylater",),
        ("buy now pay later",),
        ("cash loan",),
        ("borrower", "lender"),
    ),
    SECURED_LOAN_PATH: (
        ("tanpa jaminan",),
        ("without collateral",),
        ("shopping", "installment"),
        ("merchant", "cashflow"),
    ),
    P2P_LOAN_PATH: (
        ("shopping", "installment"),
        ("working capital", "merchant"),
        ("instant", "cash"),
    ),
}

SAFE_SPORTS_INFO_GROUPS: tuple[tuple[str, ...], ...] = (
    ("sports information",),
    ("sports information", "only"),
    ("analytical purposes only",),
    ("for informational purposes only",),
    ("football match predictions", "statistics"),
    ("match insights", "statistics"),
    ("team statistics", "historical results"),
    ("fixtures", "football news"),
    ("predictions", "statistical analysis"),
    ("publicly available data",),
)

ANTI_GAMBLING_DISCLAIMER_GROUPS: tuple[tuple[str, ...], ...] = (
    ("does not offer", "gambling"),
    ("does not offer", "betting"),
    ("does not offer", "gaming functionality"),
    ("does not operate", "betting services"),
    ("do not operate", "betting services"),
    ("do not promote", "betting services"),
    ("not affiliated", "bookmakers"),
    ("not affiliated", "bookmaker"),
    ("for sports information", "only"),
    ("for analytical purposes", "only"),
)

CATEGORY_INTENT_GROUPS: dict[str, tuple[tuple[str, ...], ...]] = {
    ACTION_GAME_PATH: (
        ("action", "game"),
        ("combat", "battle"),
        ("fight", "enemies"),
        ("survival", "challenge"),
    ),
    ADVENTURE_GAME_PATH: (
        ("adventure", "game"),
        ("explore", "world"),
        ("story", "quest"),
        ("discover", "secrets"),
    ),
    RPG_GAME_PATH: (
        ("role", "playing"),
        ("character", "skills"),
        ("heroes", "upgrade"),
        ("level", "characters"),
    ),
    STRATEGY_GAME_PATH: (
        ("strategy", "game"),
        ("social", "deduction"),
        ("vote", "impostors"),
        ("sabotage", "mission"),
        ("complete", "tasks"),
        ("crew", "impostor"),
    ),
    CASUAL_GAME_PATH: (
        ("casual", "game"),
        ("easy", "fun"),
        ("quick", "play"),
        ("simple", "gameplay"),
    ),
    COMPETITIVE_GAME_PATH: (
        ("multiplayer", "game"),
        ("global", "players"),
        ("last", "standing"),
        ("duo", "squad"),
        ("private", "rooms"),
        ("custom", "rules"),
    ),
    BOARD_GAME_PATH: (
        ("board", "game"),
        ("card", "game"),
        ("chess", "board"),
        ("poker", "cards"),
    ),
    "金融 (Finance) → 电子钱包 (E-wallet)": (
        ("scan", "qris"),
        ("top up", "saldo"),
        ("wallet", "balance"),
        ("dompet", "digital"),
        ("pay", "qr"),
    ),
    "金融 (Finance) → 支付 (Payment)": (
        ("pay", "bills"),
        ("bill", "payment"),
        ("merchant", "payments"),
        ("payment", "gateway"),
        ("accept", "payments"),
    ),
    "金融 (Finance) → 银行 (Banking)": (
        ("bank", "account"),
        ("mobile", "banking"),
        ("rekening", "tabungan"),
        ("transfer", "bank"),
        ("digital", "bank"),
    ),
    "金融 (Finance) → 股票 (Stocks)": (
        ("stock", "trading"),
        ("buy", "stocks"),
        ("sell", "stocks"),
        ("stock", "market"),
        ("equity", "trading"),
    ),
    "金融 (Finance) → 加密货币 (Cryptocurrency)": (
        ("buy", "crypto"),
        ("sell", "crypto"),
        ("crypto", "exchange"),
        ("blockchain", "wallet"),
        ("bitcoin", "trading"),
    ),
    "金融 (Finance) → 投资 (Investment)": (
        ("mutual", "fund"),
        ("reksa", "dana"),
        ("build", "portfolio"),
        ("investment", "portfolio"),
        ("asset", "allocation"),
    ),
    "金融 (Finance) → 理财 (Wealth Management)": (
        ("financial", "planning"),
        ("plan", "goals"),
        ("manage", "wealth"),
        ("saving", "goals"),
        ("personal", "finance"),
    ),
    SECURED_LOAN_PATH: (
        ("loan", "collateral"),
        ("pinjaman", "jaminan"),
        ("pinjaman", "agunan"),
        ("gadai", "emas"),
        ("jaminan", "bpkb"),
        ("sertifikat", "rumah"),
    ),
    "金融 (Finance) → 保险 (Insurance)": (
        ("insurance", "claim"),
        ("insurance", "policy"),
        ("premium", "coverage"),
        ("file", "claim"),
        ("buy", "insurance"),
    ),
    "消费 (Consumption) → 电商 (E-commerce)": (
        ("buy", "online"),
        ("sell", "online"),
        ("online", "shopping"),
        ("marketplace", "seller"),
        ("shop", "products"),
    ),
    "消费 (Consumption) → 外卖 (Food Delivery)": (
        ("order", "food"),
        ("delivery", "restaurant"),
        ("food", "delivery"),
        ("meal", "delivery"),
        ("menu", "restaurant"),
    ),
    "消费 (Consumption) → 团购 (Group Buying)": (
        ("group", "buying"),
        ("group", "deals"),
        ("bulk", "order"),
        ("community", "buying"),
    ),
    "消费 (Consumption) → 二手交易 (Second-hand Trade)": (
        ("buy", "used"),
        ("sell", "used"),
        ("second", "hand"),
        ("preloved", "items"),
    ),
    "消费 (Consumption) → 品牌官网 (Brand Official)": (
        ("official", "store"),
        ("brand", "membership"),
        ("loyalty", "rewards"),
        ("official", "brand"),
    ),
    "消费 (Consumption) → 超市 (Supermarket)": (
        ("grocery", "delivery"),
        ("daily", "needs"),
        ("fresh", "produce"),
        ("supermarket", "shopping"),
    ),
    "娱乐 (Entertainment) → 视频 (Video)": (
        ("watch", "movies"),
        ("watch", "series"),
        ("video", "streaming"),
        ("on demand", "video"),
    ),
    "娱乐 (Entertainment) → 音乐 (Music)": (
        ("listen", "music"),
        ("music", "playlist"),
        ("songs", "artists"),
        ("lyrics", "music"),
        ("albums", "artists"),
    ),
    "娱乐 (Entertainment) → 直播 (Live Streaming)": (
        ("watch", "live"),
        ("go", "live"),
        ("live", "host"),
        ("live", "streaming"),
    ),
    "娱乐 (Entertainment) → 阅读 (Reading)": (
        ("read", "books"),
        ("ebook", "reader"),
        ("novel", "reading"),
        ("digital", "library"),
    ),
    "娱乐 (Entertainment) → 漫画 (Comics)": (
        ("read", "comics"),
        ("webtoon", "episodes"),
        ("manga", "reader"),
        ("comic", "chapters"),
    ),
    "娱乐 (Entertainment) → 短视频 (Short Video)": (
        ("watch", "short videos"),
        ("video", "clips"),
        ("short", "clips"),
        ("creator", "clips"),
    ),
    "工具 (Tools) → VPN": (
        ("secure", "tunnel"),
        ("private", "network"),
        ("vpn", "proxy"),
        ("encrypt", "traffic"),
    ),
    "工具 (Tools) → 浏览器 (Browser)": (
        ("browse", "web"),
        ("search", "web"),
        ("internet", "browser"),
        ("open", "websites"),
    ),
    "工具 (Tools) → 输入法 (Input Method)": (
        ("typing", "keyboard"),
        ("input", "method"),
        ("keyboard", "emoji"),
        ("smart", "keyboard"),
    ),
    "工具 (Tools) → 办公 (Office)": (
        ("edit", "documents"),
        ("create", "spreadsheets"),
        ("presentation", "slides"),
        ("pdf", "editor"),
    ),
    "工具 (Tools) → 安全 (Security)": (
        ("protect", "privacy"),
        ("scan", "viruses"),
        ("app", "lock"),
        ("phone", "security"),
    ),
    "工具 (Tools) → 清理 (Cleaning)": (
        ("clean", "junk"),
        ("clear", "cache"),
        ("boost", "storage"),
        ("free", "space"),
    ),
    "工具 (Tools) → 系统工具 (System Tools)": (
        ("file", "manager"),
        ("scan", "qr"),
        ("device", "utility"),
        ("system", "tool"),
        ("calendar", "notes"),
        ("kalender", "catatan"),
        ("kalender", "jawa"),
        ("libur", "nasional"),
    ),
    "出行 (Travel) → 打车 (Ride-hailing)": (
        ("book", "ride"),
        ("ride", "driver"),
        ("motorbike", "taxi"),
        ("car", "ride"),
    ),
    "出行 (Travel) → 地图导航 (Maps/Navigation)": (
        ("gps", "navigation"),
        ("route", "planner"),
        ("turn by turn", "navigation"),
        ("maps", "directions"),
    ),
    "出行 (Travel) → 公共交通 (Public Transport)": (
        ("bus", "schedule"),
        ("train", "ticket"),
        ("public", "transport"),
        ("transit", "route"),
    ),
    "出行 (Travel) → 租车 (Car Rental)": (
        ("rent", "car"),
        ("car", "rental"),
        ("vehicle", "rental"),
        ("sewa", "mobil"),
    ),
    "出行 (Travel) → 机票酒店 (Flights/Hotels)": (
        ("book", "flights"),
        ("book", "hotels"),
        ("flight", "booking"),
        ("hotel", "booking"),
    ),
    "生活服务 (Life Services) → 医疗健康 (Health/Medical)": (
        ("doctor", "consultation"),
        ("medical", "appointment"),
        ("telemedicine", "doctor"),
        ("pharmacy", "medicine"),
    ),
    "生活服务 (Life Services) → 房产 (Real Estate)": (
        ("buy", "house"),
        ("rent", "apartment"),
        ("property", "listing"),
        ("real", "estate"),
    ),
    "生活服务 (Life Services) → 求职招聘 (Jobs)": (
        ("find", "jobs"),
        ("job", "search"),
        ("career", "opportunities"),
        ("apply", "jobs"),
    ),
    "生活服务 (Life Services) → 家政服务 (Home Services)": (
        ("book", "cleaning"),
        ("home", "service"),
        ("book", "handyman"),
        ("household", "service"),
    ),
    "生活服务 (Life Services) → 快递 (Courier)": (
        ("track", "parcel"),
        ("send", "package"),
        ("courier", "tracking"),
        ("shipment", "tracking"),
    ),
    "生活服务 (Life Services) → 票务 (Ticketing)": (
        ("book", "tickets"),
        ("event", "tickets"),
        ("cinema", "ticket"),
        ("concert", "tickets"),
    ),
    "社交 (Social) → 即时通讯 (IM)": (
        ("send", "messages"),
        ("group", "chat"),
        ("voice", "message"),
        ("instant", "messaging"),
    ),
    "社交 (Social) → 社交网络 (Social Network)": (
        ("share", "posts"),
        ("follow", "friends"),
        ("social", "feed"),
        ("stories", "posts"),
    ),
    "社交 (Social) → 约会 (Dating)": (
        ("match", "singles"),
        ("find", "partner"),
        ("dating", "chat"),
        ("romance", "match"),
    ),
    "社交 (Social) → 社区 (Community)": (
        ("discussion", "community"),
        ("interest", "groups"),
        ("forum", "threads"),
        ("community", "topics"),
    ),
    "教育 (Education) → 语言学习 (Language Learning)": (
        ("learn", "english"),
        ("vocabulary", "grammar"),
        ("language", "practice"),
        ("speaking", "practice"),
    ),
    "教育 (Education) → K12": (
        ("students", "teachers"),
        ("homework", "help"),
        ("school", "learning"),
        ("math", "science"),
    ),
    "教育 (Education) → 职业教育 (Vocational)": (
        ("job", "skills"),
        ("professional", "certification"),
        ("career", "training"),
        ("upskilling", "course"),
    ),
    "教育 (Education) → 早教 (Early Education)": (
        ("kids", "learning"),
        ("preschool", "activities"),
        ("toddlers", "learning"),
        ("early", "education"),
    ),
    "教育 (Education) → 在线课程 (Online Courses)": (
        ("online", "courses"),
        ("video", "lessons"),
        ("learn", "online"),
        ("course", "platform"),
    ),
    "资讯 (Information) → 新闻 (News)": (
        ("breaking", "news"),
        ("latest", "news"),
        ("headline", "news"),
        ("news", "updates"),
    ),
    "资讯 (Information) → 体育 (Sports)": (
        ("sports", "news"),
        ("live", "scores"),
        ("match", "statistics"),
        ("league", "standings"),
    ),
    "资讯 (Information) → 财经资讯 (Financial News)": (
        ("market", "news"),
        ("stock", "news"),
        ("financial", "news"),
        ("investment", "insights"),
    ),
    "资讯 (Information) → 天气 (Weather)": (
        ("weather", "forecast"),
        ("temperature", "forecast"),
        ("rain", "radar"),
        ("air", "quality"),
    ),
    TASK_SCAM_PATH: (
        ("complete", "tasks"),
        ("recharge", "withdraw"),
        ("grab", "orders"),
        ("task", "commission"),
        ("admin fee", "before disbursement"),
        ("verification fee", "before loan"),
        ("pay", "admin fee"),
        ("loan", "after payment"),
        ("guaranteed", "profit"),
        ("fixed", "daily returns"),
        ("principal", "guaranteed"),
        ("daily", "bonus"),
        ("deposit", "usdt"),
        ("cloud", "mining"),
        ("mining", "rewards"),
        ("passive income", "crypto"),
    ),
}

CATEGORY_NEGATIVE_INTENT_GROUPS: dict[str, tuple[tuple[str, ...], ...]] = {
    STRATEGY_GAME_PATH: (
        ("recharge", "withdraw"),
        ("task", "commission"),
    ),
    COMPETITIVE_GAME_PATH: (
        ("recharge", "withdraw"),
        ("task", "commission"),
    ),
    "金融 (Finance) → 加密货币 (Cryptocurrency)": (
        ("guaranteed", "profit"),
        ("fixed", "daily returns"),
        ("cloud", "mining"),
    ),
    "金融 (Finance) → 投资 (Investment)": (
        ("principal", "guaranteed"),
        ("fixed", "daily returns"),
        ("guaranteed", "profit"),
    ),
    "金融 (Finance) → 电子钱包 (E-wallet)": (
        ("bank", "account"),
        ("mobile", "banking"),
    ),
    "金融 (Finance) → 银行 (Banking)": (
        ("scan", "qris"),
        ("wallet", "balance"),
    ),
    SECURED_LOAN_PATH: (
        ("tanpa", "jaminan"),
        ("without", "collateral"),
        ("instant", "cash"),
    ),
    "资讯 (Information) → 体育 (Sports)": (
        ("place", "bet"),
        ("bet", "now"),
        ("sports", "betting"),
    ),
    GAMBLING_FRAUD_PATH: (
        ("for sports information", "only"),
        ("does not offer", "gambling"),
    ),
    BETTING_FRAUD_PATH: (
        ("for sports information", "only"),
        ("does not offer", "betting"),
    ),
    TASK_SCAM_PATH: (
        ("registered", "lender"),
        ("licensed", "lender"),
        ("play", "game"),
        ("gameplay", "mode"),
        ("vote", "impostors"),
        ("crew", "impostor"),
    ),
}


def load_rules() -> tuple[str, tuple[CategoryRule, ...]]:
    payload = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    fallback_category = str(payload["fallback_category"])
    rules = tuple(
        CategoryRule(
            path=str(item["path"]),
            keywords=tuple(str(keyword) for keyword in item["keywords"]),
            priority=int(item["priority"]),
        )
        for item in payload["rules"]
    )
    return fallback_category, rules


FALLBACK_CATEGORY, CATEGORY_RULES = load_rules()


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.replace("_x000d_", " ")
    normalized = normalized.replace("_x000D_", " ")
    normalized = normalized.lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def normalize_package_name(package_name: str) -> str:
    package = normalize_text(package_name)
    package = package.replace("/", ".").replace("_", ".").replace("-", ".")
    package = re.sub(r"[^a-z0-9.]+", ".", package)
    package = re.sub(r"\.+", ".", package).strip(".")
    return package


def package_name_to_text(package_name: str) -> str:
    normalized = normalize_package_name(package_name)
    if not normalized:
        return ""

    parts = [part for part in normalized.split(".") if part and not part.isdigit()]
    aliases = {
        "wallet": "wallet ewallet dompet digital",
        "pay": "pay payment pembayaran",
        "loan": "loan pinjaman kredit",
        "cash": "cash tunai",
        "paylater": "paylater cicilan installment",
        "crypto": "crypto cryptocurrency bitcoin",
        "bank": "bank banking rekening tabungan",
        "stock": "stock saham trading",
        "invest": "investment investasi",
        "insurance": "insurance asuransi",
        "shop": "shopping marketplace ecommerce",
        "store": "store shopping official",
        "mart": "supermarket grocery",
        "food": "food delivery order makanan",
        "ride": "ride hailing taxi ojek",
        "maps": "maps navigation gps",
        "travel": "travel flight hotel booking",
        "hotel": "hotel booking",
        "health": "health medical doctor",
        "doctor": "doctor medical consultation",
        "job": "jobs recruitment career",
        "courier": "courier parcel delivery",
        "chat": "chat messaging im",
        "social": "social network community",
        "dating": "dating match singles",
        "learn": "education online course learning",
        "course": "online course learning",
        "news": "news information headline",
        "sport": "sports news score",
        "weather": "weather forecast",
        "vpn": "vpn secure proxy",
        "browser": "browser web search",
        "cleaner": "clean junk cache",
        "security": "security antivirus privacy",
        "game": "game gameplay players",
        "casino": "casino judi gambling slot",
        "slot": "slot gambling casino",
        "bet": "betting taruhan sportsbook",
        "task": "task rebate commission",
    }
    expanded_parts: list[str] = []
    for part in parts:
        expanded_parts.append(part)
        expanded_parts.append(aliases.get(part, part))

    return " ".join(expanded_parts)


def keyword_weight(keyword: str) -> int:
    if len(keyword) >= 20:
        weight = 9
    elif len(keyword) >= 14:
        weight = 7
    elif " " in keyword:
        weight = 5
    elif len(keyword) >= 8:
        weight = 4
    else:
        weight = 3

    if keyword in LOW_SIGNAL_KEYWORDS:
        weight = max(1, weight - 2)

    return weight


def keyword_occurrences(text: str, keyword: str) -> int:
    suppressed_phrases = SUPPRESSED_PHRASES_BY_KEYWORD.get(keyword, ())
    if any(phrase in text for phrase in suppressed_phrases):
        return 0
    escaped = re.escape(keyword)
    pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    return len(re.findall(pattern, text))


def contains_all(text: str, terms: tuple[str, ...]) -> bool:
    return all(term in text for term in terms)


def loan_intent_score(path: str, text: str) -> int:
    score = 0

    for group in INTENT_SIGNAL_GROUPS.get(path, ()):
        if contains_all(text, group):
            score += 650 if len(group) > 1 else 420

    for group in NEGATIVE_SIGNAL_GROUPS.get(path, ()):
        if contains_all(text, group):
            score -= 300 if len(group) > 1 else 180

    if path == MICROLOAN_PATH and ("cash" in text or "tunai" in text):
        score += 120
    if path == MICROLOAN_PATH and ("cair" in text or "disbursement" in text):
        score += 140
    if path == MICROLOAN_PATH and ("tanpa jaminan" in text or "without collateral" in text):
        score += 160
    if path == INSTALLMENT_LOAN_PATH and ("shopping" in text or "belanja" in text):
        score += 120
    if path == INSTALLMENT_LOAN_PATH and ("checkout" in text or "purchase" in text):
        score += 140
    if path == INSTALLMENT_LOAN_PATH and ("tenor" in text or "monthly installment" in text or "cicilan bulanan" in text):
        score += 150
    if path == BUSINESS_LOAN_PATH and ("merchant" in text or "usaha" in text):
        score += 120
    if path == BUSINESS_LOAN_PATH and ("cashflow" in text or "working capital" in text):
        score += 150
    if path == BUSINESS_LOAN_PATH and ("invoice" in text or "business owner" in text):
        score += 140
    if path == SECURED_LOAN_PATH and ("jaminan" in text or "agunan" in text or "collateral" in text):
        score += 160
    if path == SECURED_LOAN_PATH and ("bpkb" in text or "sertifikat rumah" in text or "gadai emas" in text):
        score += 180
    if path == P2P_LOAN_PATH and ("investor" in text or "pendana" in text):
        score += 120
    if path == P2P_LOAN_PATH and ("return" in text or "imbal hasil" in text):
        score += 140

    return score


def semantic_intent_adjustment(path: str, text: str) -> int:
    score = 0

    for group in CATEGORY_INTENT_GROUPS.get(path, ()):
        if contains_all(text, group):
            score += 260 if len(group) == 1 else 420

    for group in CATEGORY_NEGATIVE_INTENT_GROUPS.get(path, ()):
        if contains_all(text, group):
            score -= 260 if len(group) == 1 else 420

    if path == SPORTS_INFO_PATH:
        for group in SAFE_SPORTS_INFO_GROUPS:
            if contains_all(text, group):
                score += 420 if len(group) == 1 else 650
        for group in ANTI_GAMBLING_DISCLAIMER_GROUPS:
            if contains_all(text, group):
                score += 500 if len(group) == 1 else 800

    if path in {GAMBLING_FRAUD_PATH, BETTING_FRAUD_PATH}:
        for group in ANTI_GAMBLING_DISCLAIMER_GROUPS:
            if contains_all(text, group):
                score -= 900 if len(group) == 1 else 1400
        if "bookmaker" in text or "bookmakers" in text:
            if "not affiliated" in text or "not affiliated with any" in text:
                score -= 700

    if path == TASK_SCAM_PATH and ("licensed lender" in text or "registered lender" in text):
        score -= 500

    return score


def classify_app(description: str = "", package_name: str = "") -> str:
    description_text = normalize_text(description)
    package_text = package_name_to_text(package_name)
    text = " ".join(part for part in (description_text, package_text) if part).strip()

    if not text:
        return FALLBACK_CATEGORY

    best_path = FALLBACK_CATEGORY
    best_score = 0
    best_priority = 10**9

    for rule in CATEGORY_RULES:
        match_count = 0
        weighted_score = 0
        specificity_bonus = 0

        for keyword in rule.keywords:
            occurrences = keyword_occurrences(text, keyword)
            if occurrences <= 0:
                continue

            weight = keyword_weight(keyword)
            match_count += 1
            weighted_score += occurrences * weight * 100
            specificity_bonus += len(keyword)

        if match_count == 0:
            intent_bonus = loan_intent_score(rule.path, text)
            semantic_bonus = semantic_intent_adjustment(rule.path, text)
            if intent_bonus + semantic_bonus <= 0:
                continue
            score = intent_bonus + semantic_bonus
        else:
            intent_bonus = loan_intent_score(rule.path, text)
            semantic_bonus = semantic_intent_adjustment(rule.path, text)
            score = weighted_score + match_count * 20 + specificity_bonus + intent_bonus + semantic_bonus

        if score > best_score or (score == best_score and rule.priority < best_priority):
            best_path = rule.path
            best_score = score
            best_priority = rule.priority

    return best_path


def classify_description(description: str) -> str:
    return classify_app(description=description)
