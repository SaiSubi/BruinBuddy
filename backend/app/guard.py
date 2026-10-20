"""Deterministic solution-leak guard.

Builds word-shingles from tutor-only solution text, minus any shingle that also appears in public
materials (solutions repeat the problem statement, which students may legitimately see).
A reply that shares several solution-only shingles is treated as a leak.
"""
import re
import unicodedata

from .db import db

N = 6
THRESHOLD = 2


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", unicodedata.normalize("NFKC", text).lower())


def _shingles(text: str) -> set[tuple[str, ...]]:
    w = _words(text)
    return {tuple(w[i:i + N]) for i in range(len(w) - N + 1)}


class LeakGuard:
    def __init__(self) -> None:
        sol: set = set()
        pub: set = set()
        with db() as conn:
            for r in conn.execute("SELECT text, tutor_only FROM chunks"):
                (sol if r["tutor_only"] else pub).update(_shingles(r["text"]))
        self.solution_only = sol - pub

    def leaks(self, reply: str) -> bool:
        return len(_shingles(reply) & self.solution_only) >= THRESHOLD
