"""Per-student memory: short study-relevant notes, edited by a cheap model after each reply."""
from . import config, llm
from .db import db, now

MEMORY_SYSTEM = """You maintain short memory notes about one student's studying, for a course tutor. Given the current notes and the latest exchange, decide what to change.
Store only study-relevant facts: topics they are working on or preparing for, concepts they struggle with, how they like to learn. Do NOT store personal details, names, contact info, health or other sensitive information, or any solution content for assigned problems. Keep each note under 20 words. Merge duplicates, update notes that changed, remove notes that are outdated. Most exchanges need no change.
Reply with JSON only: {"ops": [{"op": "add", "text": "..."}, {"op": "update", "id": 3, "text": "..."}, {"op": "remove", "id": 2}]}  (an empty list is fine)."""


def load_notes(user_id: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute("SELECT id, text FROM memories WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
                            (user_id, config.MAX_MEMORY_NOTES)).fetchall()
    return [{"id": r["id"], "text": r["text"]} for r in rows]


def update_memory(user_id: int, user_msg: str, reply: str) -> None:
    notes = load_notes(user_id)
    current = "\n".join(f"[{n['id']}] {n['text']}" for n in notes) or "(none)"
    raw = llm.complete("memory", [
        {"role": "system", "content": MEMORY_SYSTEM},
        {"role": "user", "content": f"CURRENT NOTES:\n{current}\n\nSTUDENT: {user_msg[:1500]}\n\nTUTOR: {reply[:1500]}"}],
        max_tokens=config.HELPER_MAX_TOKENS)
    ops = llm.parse_json(raw).get("ops", [])
    valid_ids = {n["id"] for n in notes}
    with db() as conn:
        for op in ops[:5]:
            kind, text = op.get("op"), str(op.get("text", "")).strip()[:200]
            if kind == "add" and text:
                conn.execute("INSERT INTO memories(user_id,text,created_at,updated_at) VALUES(?,?,?,?)",
                             (user_id, text, now(), now()))
            elif kind == "update" and op.get("id") in valid_ids and text:
                conn.execute("UPDATE memories SET text=?, updated_at=? WHERE id=? AND user_id=?",
                             (text, now(), op["id"], user_id))
            elif kind == "remove" and op.get("id") in valid_ids:
                conn.execute("DELETE FROM memories WHERE id=? AND user_id=?", (op["id"], user_id))
        # cap the list: drop the stalest notes
        conn.execute("DELETE FROM memories WHERE user_id=? AND id NOT IN "
                     "(SELECT id FROM memories WHERE user_id=? ORDER BY updated_at DESC LIMIT ?)",
                     (user_id, user_id, config.MAX_MEMORY_NOTES))
