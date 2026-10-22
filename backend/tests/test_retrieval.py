"""Hybrid retrieval: chunk embeddings at upload, rank fusion, the similarity floor, backfill and fallbacks."""
import numpy as np

from conftest import SOL1, ask, execute, new_chat, new_user, q1, setup_course, student_in, upload_ok


def _chunks(doc_ids=None, vectors=None):
    from app.retrieval import Chunk, Index
    chunks = [Chunk(id=i, doc_id=f"d{i}", title=f"Doc {i}", kind="reading", page=1, text=t)
              for i, t in enumerate(["bayes theorem prior posterior likelihood update " * 3,
                                     "variance spread squared deviation mean " * 3,
                                     "bootstrap resampling confidence interval " * 3])]
    return chunks, Index(chunks, vectors)


def test_upload_stores_embeddings_without_using_allowance(app):
    owner = new_user(app)
    c = setup_course(owner)
    row = q1("SELECT COUNT(*) AS n, COUNT(c.embedding) AS e, MIN(c.embed_model) AS m FROM chunks c "
             "JOIN documents d ON d.id=c.doc_id WHERE d.course_id=?", c["id"])
    assert row["n"] > 0 and row["e"] == row["n"] and row["m"] == "mock"
    usage = q1("SELECT COUNT(*) AS n, COALESCE(SUM(total_tokens),0) AS t, COALESCE(SUM(prompt_tokens),0) AS p "
               "FROM usage_log WHERE course_id=? AND purpose='embed'", c["id"])
    assert usage["n"] > 0 and usage["t"] == 0 and usage["p"] > 0  # cost is recorded, allowance untouched


def test_turn_embeds_the_query_with_attribution(app):
    owner = new_user(app)
    c = setup_course(owner)
    s = student_in(app, c)
    chat = new_chat(s, c["id"])
    done = ask(s, chat, "Why does Bayes theorem need a prior?")[-1]
    assert done["type"] == "done" and done["message"]["citations"]
    row = q1("SELECT user_id, total_tokens FROM usage_log WHERE chat_id=? AND purpose='embed_query'", chat)
    assert row["user_id"] == s.user["id"] and row["total_tokens"] == 0


def test_rank_fusion_finds_what_bm25_misses():
    from app.embeddings import unit
    vecs = [unit([1, 0, 0]), unit([0, 1, 0]), unit([0, 0, 1])]
    chunks, index = _chunks(vectors=vecs)
    # no shared words, so BM25 finds nothing; the embedding side still points at the variance chunk
    assert index.retrieve("how wide is it around the average", None, 3) == []
    assert index.retrieve("how wide is it around the average", unit([0, 1, 0]), 3) == [chunks[1]]
    # a chunk both rankings agree on comes first
    fused = index.retrieve("bootstrap resampling", unit([0.2, 0, 1]), 3)
    assert fused[0] is chunks[2] and chunks[1] not in fused  # below the similarity floor: never added


def test_without_vectors_retrieval_is_bm25():
    chunks, index = _chunks()
    assert not index.dense
    assert index.retrieve("bootstrap confidence interval", None, 3) == [chunks[2]]
    assert index.retrieve("bootstrap confidence interval", np.ones(3, dtype=np.float32), 3) == [chunks[2]]


def test_embedding_search_never_reaches_protected_solutions(app):
    from app import knowledge
    from app.embeddings import unit
    from app.llm import _mock_vector
    owner = new_user(app)
    c = setup_course(owner)
    kb = knowledge.cache.get(c["id"])
    hits = kb.index.dense_search(unit(_mock_vector(SOL1)), 50)
    assert hits and {h.doc_id for _, h in hits} <= kb.public and c["s1"] not in {h.doc_id for _, h in hits}
    s = student_in(app, c)
    ask(s, new_chat(s, c["id"]), SOL1)  # pasting the solution text doesn't pull the solution into the prompt
    from conftest import tutor_prompts
    assert "three eighths" not in tutor_prompts()[-1]


def test_backfill_fills_missing_vectors_without_touching_content_version(app):
    from app import knowledge
    owner = new_user(app)
    c = setup_course(owner)
    execute("UPDATE chunks SET embedding=NULL, embed_model=NULL WHERE doc_id IN "
            "(SELECT id FROM documents WHERE course_id=?)", c["id"])
    execute("UPDATE courses SET content_version=content_version+1 WHERE id=?", c["id"])  # e.g. a fresh process
    before = q1("SELECT content_version, index_version FROM courses WHERE id=?", c["id"])
    knowledge.cache.get(c["id"])  # finds the gap; the backfill runs inline in tests
    after = q1("SELECT content_version, index_version FROM courses WHERE id=?", c["id"])
    assert after["content_version"] == before["content_version"]  # starter questions aren't regenerated
    assert after["index_version"] == before["index_version"] + 1
    assert q1("SELECT COUNT(*) AS n FROM chunks c JOIN documents d ON d.id=c.doc_id WHERE d.course_id=? "
              "AND c.embedding IS NULL", c["id"])["n"] == 0
    assert knowledge.cache.get(c["id"]).index.dense


def test_embedding_outage_falls_back_to_bm25(app, monkeypatch):
    from app import llm

    def down(*a, **kw):
        raise RuntimeError("embeddings unavailable")

    monkeypatch.setattr(llm, "embed", down)
    owner = new_user(app)
    c = setup_course(owner)  # uploads still succeed, without vectors
    assert q1("SELECT COUNT(c.embedding) AS e FROM chunks c JOIN documents d ON d.id=c.doc_id WHERE d.course_id=?",
              c["id"])["e"] == 0
    extra = upload_ok(owner, c["id"], "reading", {"More.txt": "Bootstrap resampling builds confidence intervals."})
    assert q1("SELECT status FROM documents WHERE id=?", extra[0])["status"] == "ready"
    s = student_in(app, c)
    done = ask(s, new_chat(s, c["id"]), "Why does Bayes theorem need a prior?")[-1]
    assert done["type"] == "done" and done["message"]["citations"]
