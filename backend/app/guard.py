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


NUMBER = re.compile(r"\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?")


def _numbers(text: str) -> set[str]:
    return set(NUMBER.findall(unicodedata.normalize("NFKC", text)))


def short_answer_leaks(reply: str, target: str, public_text: str) -> bool:
    """Checkpoint answers are short ("P(A) = 0.2"), too short for shingles. A reply leaks a target if it repeats the
    whole target, or any number from the target that the student hasn't already been shown. Single digits count only
    when they are the whole answer, since hints mention small counts all the time."""
    words, said = _words(target), _words(reply)
    if len(words) >= 2 and f" {' '.join(words)} " in f" {' '.join(said)} ":
        return True
    if len(words) == 1 and len(words[0]) >= 4 and words[0] in said and words[0] not in _words(public_text):
        return True
    secret = _numbers(target) - _numbers(public_text)
    if len(_numbers(target)) > 1 or len(words) > 1:
        secret = {n for n in secret if len(n) > 1}
    return bool(secret & _numbers(reply)) or LeakGuard([target], [public_text]).leaks(reply)
