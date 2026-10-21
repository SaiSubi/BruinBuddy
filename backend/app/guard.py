"""Deterministic solution-leak guard (one per course).

Builds word-shingles from the course's protected solution text, minus any shingle that also appears in its
public materials (solutions repeat the problem statement, which students may legitimately see).
A reply that shares several solution-only shingles is treated as a leak.
"""
import re
import unicodedata
from collections.abc import Iterable

N = 6
THRESHOLD = 2


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKC", text).lower())


def _shingles(text: str) -> set[tuple[str, ...]]:
    w = _words(text)
    return {tuple(w[i:i + N]) for i in range(len(w) - N + 1)}


class LeakGuard:
    def __init__(self, protected_texts: Iterable[str], public_texts: Iterable[str]) -> None:
        sol: set = set()
        pub: set = set()
        for t in protected_texts:
            sol |= _shingles(t)
        for t in public_texts:
            pub |= _shingles(t)
        self.solution_only = sol - pub

    def leaks(self, reply: str) -> bool:
        return len(_shingles(reply) & self.solution_only) >= THRESHOLD
