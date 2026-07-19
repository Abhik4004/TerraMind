"""
PII redaction — strips personal information from text before it is sent to the LLM.

Security rule: the language model (and any third-party model endpoint) should
never receive a user's personal data. This module masks common PII — emails,
phone numbers, payment cards, government IDs — while carefully preserving
geographic coordinates (decimal lat/lon), which the pipeline depends on and
which are NOT personal information.

Usage:
    from src.utils.pii_filter import redact_pii, redact_history
    safe = redact_pii(user_query)
"""
import re
from typing import List, Dict, Tuple

# Decimal numbers (e.g. coordinates "22.5726") are protected from redaction so
# lat/lon survive intact — they're not PII and the geo-bounds logic needs them.
_DECIMAL = re.compile(r"-?\d+\.\d+")

# High-confidence PII patterns, applied in order (most specific first).
_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    # Payment cards: 13–16 digits, optionally separated by space/dash.
    ("CARD", re.compile(r"(?<!\w)(?:\d[ -]?){13,16}(?!\w)")),
    # US SSN
    ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # India Aadhaar: 12 digits, usually grouped 4-4-4.
    ("AADHAAR", re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")),
    # India PAN: 5 letters, 4 digits, 1 letter.
    ("PAN", re.compile(r"\b[A-Za-z]{5}\d{4}[A-Za-z]\b")),
]

# Phone numbers vary too much for a fixed regex (5-5, 3-3-4, +country, etc.), so
# we match a loose candidate then confirm by digit count (10–15 = phone).
_PHONE_CANDIDATE = re.compile(r"\+?\(?\d[\d\s\-()]{7,}\d")


def _redact_phones(text: str) -> str:
    def _sub(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        return "[REDACTED_PHONE]" if 10 <= len(digits) <= 15 else m.group(0)

    return _PHONE_CANDIDATE.sub(_sub, text)


def _protect_decimals(text: str) -> Tuple[str, List[str]]:
    """Replace decimal numbers with placeholders so PII rules can't touch them."""
    saved: List[str] = []

    def _sub(m: re.Match) -> str:
        saved.append(m.group(0))
        return f"\x00D{len(saved) - 1}\x00"

    return _DECIMAL.sub(_sub, text), saved


def _restore_decimals(text: str, saved: List[str]) -> str:
    for i, val in enumerate(saved):
        text = text.replace(f"\x00D{i}\x00", val)
    return text


def redact_pii(text: str) -> str:
    """
    Return `text` with personal information masked (e.g. "[REDACTED_EMAIL]").

    Geographic coordinates and other decimal numbers are preserved. Safe to call
    on any user-supplied string before handing it to the LLM.
    """
    if not text:
        return text

    protected, saved = _protect_decimals(text)
    for label, pattern in _PATTERNS:
        protected = pattern.sub(f"[REDACTED_{label}]", protected)
    protected = _redact_phones(protected)  # after CARD/AADHAAR so those win
    return _restore_decimals(protected, saved)


def redact_history(history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Redact PII from every message's content in a chat-history list."""
    if not history:
        return history
    return [
        {**msg, "content": redact_pii(msg.get("content", ""))}
        for msg in history
    ]


def contains_pii(text: str) -> bool:
    """Quick check: does the text contain any detectable PII?"""
    return redact_pii(text) != text
