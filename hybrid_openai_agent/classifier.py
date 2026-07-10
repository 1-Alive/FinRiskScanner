from __future__ import annotations

import json
import os
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI


BASE_DIR = Path(__file__).resolve().parent
RULES_PATH = BASE_DIR / "config" / "rules.json"
ENV_PATH = BASE_DIR / ".env"


@dataclass(frozen=True)
class CategoryRule:
    path: str
    keywords: tuple[str, ...]
    priority: int


@dataclass(frozen=True)
class RuleScore:
    path: str
    score: int
    matched_keywords: tuple[str, ...]
    priority: int


@dataclass(frozen=True)
class ClassificationResult:
    category_path: str
    source: str
    model_used: str | None
    used_llm: bool
    rule_path: str
    rule_score: int
    reason: str


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

FINANCE_INTENT_TERMS = (
    "loan",
    "pinjaman",
    "kredit",
    "cash advance",
    "cicilan",
    "paylater",
    "working capital",
    "modal usaha",
    "borrower",
    "lender",
)

P2P_LOAN_PATH = "金融 (Finance) → 借贷 (Loan) → P2P借贷 (Peer-to-Peer Lending)"
MICROLOAN_PATH = "金融 (Finance) → 借贷 (Loan) → 小额现金贷 (Microloan / Cash Loan)"
INSTALLMENT_LOAN_PATH = "金融 (Finance) → 借贷 (Loan) → 分期消费贷款 (Installment / Buy Now Pay Later)"
BUSINESS_LOAN_PATH = "金融 (Finance) → 借贷 (Loan) → 企业/商户贷款（Business Loan / SME Loan）"

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
    P2P_LOAN_PATH: (
        ("shopping", "installment"),
        ("working capital", "merchant"),
        ("instant", "cash"),
    ),
}


def load_dotenv_file() -> None:
    if not ENV_PATH.exists():
        return

    for raw_line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip().lstrip("\ufeff")
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


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
ALLOWED_PATHS = tuple(rule.path for rule in CATEGORY_RULES)
load_dotenv_file()


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


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
    return text.count(keyword)


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
    if path == INSTALLMENT_LOAN_PATH and (
        "checkout" in text or "purchase" in text or "monthly installment" in text
    ):
        score += 140
    if path == INSTALLMENT_LOAN_PATH and (
        "tenor" in text or "cicilan bulanan" in text or "installments" in text
    ):
        score += 150
    if path == BUSINESS_LOAN_PATH and ("merchant" in text or "usaha" in text):
        score += 120
    if path == BUSINESS_LOAN_PATH and ("cashflow" in text or "working capital" in text):
        score += 150
    if path == BUSINESS_LOAN_PATH and ("invoice" in text or "business owner" in text):
        score += 140
    if path == P2P_LOAN_PATH and ("investor" in text or "pendana" in text):
        score += 120
    if path == P2P_LOAN_PATH and ("return" in text or "imbal hasil" in text):
        score += 140

    return score


def extract_json_object(text: str) -> dict[str, Any] | None:
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


class HybridClassifier:
    def __init__(self) -> None:
        self.fallback_category = FALLBACK_CATEGORY
        self.rules = CATEGORY_RULES
        self.allowed_paths = set(ALLOWED_PATHS)
        self.llm_enabled = os.environ.get(
            "ENABLE_LLM_PRIMARY",
            os.environ.get("ENABLE_LLM_FALLBACK", "true"),
        ).lower() == "true"
        self.model = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
        self.reasoning_effort = os.environ.get("OPENAI_REASONING_EFFORT", "low")
        self.rule_validation_threshold = int(os.environ.get("RULE_VALIDATION_THRESHOLD", "1400"))
        self.rule_validation_margin = int(os.environ.get("RULE_VALIDATION_MARGIN", "420"))
        self.loan_validation_threshold = int(os.environ.get("LOAN_VALIDATION_THRESHOLD", "1750"))
        self.loan_validation_margin = int(os.environ.get("LOAN_VALIDATION_MARGIN", "520"))
        self.api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self.client = OpenAI(api_key=self.api_key) if self.api_key and self.llm_enabled else None
        self._cache: dict[str, ClassificationResult] = {}

    def score_rules(self, description: str) -> list[RuleScore]:
        text = normalize_text(description)
        if not text:
            return []

        scores: list[RuleScore] = []
        for rule in self.rules:
            matched_keywords: list[str] = []
            weighted_score = 0
            specificity_bonus = 0

            for keyword in rule.keywords:
                occurrences = keyword_occurrences(text, keyword)
                if occurrences <= 0:
                    continue

                matched_keywords.append(keyword)
                weight = keyword_weight(keyword)
                weighted_score += occurrences * weight * 100
                specificity_bonus += len(keyword)

            intent_bonus = loan_intent_score(rule.path, text)
            if not matched_keywords and intent_bonus <= 0:
                continue

            total_score = weighted_score + len(matched_keywords) * 20 + specificity_bonus + intent_bonus
            scores.append(
                RuleScore(
                    path=rule.path,
                    score=total_score,
                    matched_keywords=tuple(matched_keywords),
                    priority=rule.priority,
                )
            )

        scores.sort(key=lambda item: (-item.score, item.priority))
        return scores

    def classify(self, description: str) -> ClassificationResult:
        normalized = normalize_text(description)
        if normalized in self._cache:
            return self._cache[normalized]

        ranked_scores = self.score_rules(description)
        top_rule = ranked_scores[0] if ranked_scores else RuleScore(self.fallback_category, 0, (), 9999)

        if self.client is not None:
            llm_result = self.classify_with_llm_primary(description)
            if llm_result is not None:
                validated_result = self.validate_llm_result(description, llm_result, ranked_scores)
                self._cache[normalized] = validated_result
                return validated_result

        result = ClassificationResult(
            category_path=top_rule.path,
            source="rule_fallback",
            model_used=None,
            used_llm=False,
            rule_path=top_rule.path,
            rule_score=top_rule.score,
            reason="大模型不可用，使用规则结果" if top_rule.score > 0 else "大模型不可用且规则弱命中，回退默认规则",
        )
        self._cache[normalized] = result
        return result

    def call_llm(self, system_prompt: str, user_prompt: str) -> dict[str, Any] | None:
        if self.client is None:
            return None

        try:
            response = self.client.responses.create(
                model=self.model,
                reasoning={"effort": self.reasoning_effort},
                input=[
                    {
                        "role": "system",
                        "content": [{"type": "input_text", "text": system_prompt}],
                    },
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": user_prompt}],
                    },
                ],
            )
        except Exception:
            return None

        output_text = getattr(response, "output_text", "") or ""
        if not output_text and getattr(response, "output", None):
            try:
                output_text = response.output[0].content[0].text  # type: ignore[index]
            except Exception:
                output_text = ""

        payload = extract_json_object(output_text)
        if not payload:
            return None

        category_path = str(payload.get("category_path", "")).strip()
        if category_path not in self.allowed_paths:
            return None

        return payload

    def classify_with_llm_primary(self, description: str) -> ClassificationResult | None:
        allowed_paths_text = "\n".join(f"- {path}" for path in ALLOWED_PATHS)
        system_prompt = (
            "You classify Indonesian mobile apps into exactly one allowed category path.\n"
            "Rules:\n"
            "1. Output must be one exact allowed category path.\n"
            "2. Choose the app's primary function, not a side feature.\n"
            "3. For finance loan apps, distinguish carefully:\n"
            "   - P2P lending: connects lenders/investors with borrowers.\n"
            "   - Microloan / cash loan: direct cash borrowing, urgent funds, fast disbursement.\n"
            "   - Installment / BNPL: shopping first, pay later, checkout installments.\n"
            "   - Business loan / SME loan: merchants, stores, SMEs, working capital, invoices.\n"
            "4. Return JSON only with keys category_path and reason.\n"
            "5. category_path must exactly match one item from the allowed paths."
        )
        user_prompt = f"Allowed category paths:\n{allowed_paths_text}\n\nApp description:\n{description}"
        payload = self.call_llm(system_prompt, user_prompt)
        if not payload:
            return None

        return ClassificationResult(
            category_path=str(payload["category_path"]).strip(),
            source="llm_primary",
            model_used=self.model,
            used_llm=True,
            rule_path="",
            rule_score=0,
            reason=str(payload.get("reason", "大模型主分类")).strip() or "大模型主分类",
        )

    def validate_llm_result(
        self,
        description: str,
        llm_result: ClassificationResult,
        ranked_scores: list[RuleScore],
    ) -> ClassificationResult:
        if not ranked_scores:
            return ClassificationResult(
                category_path=llm_result.category_path,
                source="llm_primary_validated",
                model_used=self.model,
                used_llm=True,
                rule_path=self.fallback_category,
                rule_score=0,
                reason=f"{llm_result.reason}；规则无强信号冲突",
            )

        top_rule = ranked_scores[0]
        second_score = ranked_scores[1].score if len(ranked_scores) > 1 else 0
        margin = top_rule.score - second_score
        llm_path = llm_result.category_path
        text = normalize_text(description)
        finance_intent = any(term in text for term in FINANCE_INTENT_TERMS)
        loan_related = "借贷 (Loan)" in top_rule.path or finance_intent or "借贷 (Loan)" in llm_path

        if llm_path == top_rule.path:
            return ClassificationResult(
                category_path=llm_path,
                source="llm_primary_validated",
                model_used=self.model,
                used_llm=True,
                rule_path=top_rule.path,
                rule_score=top_rule.score,
                reason=f"{llm_result.reason}；规则校验一致",
            )

        strong_rule_conflict = top_rule.score >= self.rule_validation_threshold and margin >= self.rule_validation_margin
        strong_loan_conflict = loan_related and (
            top_rule.score >= self.loan_validation_threshold and margin >= self.loan_validation_margin
        )

        if strong_rule_conflict or strong_loan_conflict:
            verified_result = self.verify_with_rule_context(description, llm_result, ranked_scores[:6])
            if verified_result is not None:
                return verified_result

            return ClassificationResult(
                category_path=top_rule.path if strong_loan_conflict else llm_path,
                source="rule_override_after_validation_failure" if strong_loan_conflict else "llm_primary_with_rule_conflict",
                model_used=self.model if not strong_loan_conflict else None,
                used_llm=not strong_loan_conflict,
                rule_path=top_rule.path,
                rule_score=top_rule.score,
                reason="规则强冲突且复核失败，借贷类优先采用规则结果" if strong_loan_conflict else "模型主判与规则强冲突，建议人工复核",
            )

        return ClassificationResult(
            category_path=llm_path,
            source="llm_primary_validated",
            model_used=self.model,
            used_llm=True,
            rule_path=top_rule.path,
            rule_score=top_rule.score,
            reason=f"{llm_result.reason}；规则未发现强冲突",
        )

    def verify_with_rule_context(
        self,
        description: str,
        llm_result: ClassificationResult,
        candidate_scores: list[RuleScore],
    ) -> ClassificationResult | None:
        candidate_lines = "\n".join(
            f"- {item.path} | rule_score={item.score} | matched={', '.join(item.matched_keywords) or 'none'}"
            for item in candidate_scores
        )
        system_prompt = (
            "You are validating a previous app classification.\n"
            "You must choose exactly one allowed category path.\n"
            "Pay extra attention to finance loan subtypes and resolve conflicts using the app's true primary intent.\n"
            "Return JSON only with keys category_path and reason."
        )
        user_prompt = (
            f"Previous LLM classification:\n- {llm_result.category_path}\n\n"
            f"Rule validation evidence:\n{candidate_lines}\n\n"
            f"App description:\n{description}\n\n"
            "Re-evaluate and return the final category path."
        )
        payload = self.call_llm(system_prompt, user_prompt)
        if not payload:
            return None

        return ClassificationResult(
            category_path=str(payload["category_path"]).strip(),
            source="llm_verified_by_rules",
            model_used=self.model,
            used_llm=True,
            rule_path=candidate_scores[0].path if candidate_scores else self.fallback_category,
            rule_score=candidate_scores[0].score if candidate_scores else 0,
            reason=str(payload.get("reason", "规则校验后模型复核")).strip() or "规则校验后模型复核",
        )
