"""Keyword matching score between an alert and a job posting.

Score = percentage of the alert's keywords found in the posting.
A keyword found in the title counts fully, in the description 60%.
Matching is accent-insensitive and word-boundary based ("go" does
not match "google").
"""
import re
import unicodedata

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return _NON_ALNUM_RE.sub(" ", text).strip()


def score_job(keywords: list[str], title: str, description: str) -> int:
    valid = [normalize(k) for k in keywords if normalize(k)]
    if not valid:
        return 0
    title_n = f" {normalize(title)} "
    desc_n = f" {normalize(description)} "
    points = 0.0
    for kw in valid:
        needle = f" {kw} "
        if needle in title_n:
            points += 1.0
        elif needle in desc_n:
            points += 0.6
    return round(100 * points / len(valid))


_CONTRACT_PATTERNS = [
    ("alternance", ("alternance", "apprentissage", "apprenti")),
    ("stage", ("stage", "stagiaire", "internship", "intern")),
    ("cdd", ("cdd", "contrat a duree determinee", "fixed term")),
    ("cdi", ("cdi", "contrat a duree indeterminee", "full time", "permanent")),
]


def detect_contract(title: str, description: str) -> str:
    haystack = f" {normalize(title)} {normalize(description)} "
    for label, needles in _CONTRACT_PATTERNS:
        if any(f" {n} " in haystack for n in needles):
            return label
    return ""
