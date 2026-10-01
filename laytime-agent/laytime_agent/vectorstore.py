"""Retrieval tier: Chroma vector DB (dense) + BM25 (keyword), fused with reciprocal rank fusion."""
from __future__ import annotations

import hashlib
import logging
import math
import re

import chromadb
from rank_bm25 import BM25Okapi

from . import config, storage

log = logging.getLogger("laytime.retrieval")
_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class HashEmbedding(chromadb.EmbeddingFunction):
    """Offline fallback: hashed bag-of-words + bigrams. Lower quality, no download needed."""
    DIM = 512

    def __init__(self):
        pass

    def __call__(self, input):
        out = []
        for text in input:
            v = [0.0] * self.DIM
            toks = tokenize(text)
            for t in toks + [a + "_" + b for a, b in zip(toks, toks[1:])]:
                h = int(hashlib.md5(t.encode()).hexdigest(), 16)
                v[h % self.DIM] += 1.0 if (h >> 8) % 2 else -1.0
            n = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / n for x in v])
        return out

    @staticmethod
    def name():
        return "laytime-hash"

    def get_config(self):
        return {}

    @staticmethod
    def build_from_config(cfg):
        return HashEmbedding()


def _embedding_function():
    kind = config.EMBEDDINGS
    if kind == "openai":
        from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
        import os
        return "openai", OpenAIEmbeddingFunction(api_key=os.getenv("OPENAI_API_KEY"),
                                                 model_name=config.OPENAI_EMBEDDING_MODEL)
    if kind == "hash":
        return "hash", HashEmbedding()
    try:
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
        ef = DefaultEmbeddingFunction()
        ef(["warm-up"])          # triggers the one-time model download
        return "minilm", ef
    except Exception as e:
        log.warning("Default embedding model unavailable (%s). Falling back to offline hash embeddings.", e)
        return "hash", HashEmbedding()


_STATE = {}


def collection():
    if "col" not in _STATE:
        kind, ef = _embedding_function()
        client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        _STATE["kind"] = kind
        _STATE["col"] = client.get_or_create_collection(f"clauses_{kind}", embedding_function=ef,
                                                        metadata={"hnsw:space": "cosine"})
    return _STATE["col"]


def embedding_kind() -> str:
    collection()
    return _STATE["kind"]


def reset_collection():
    client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
    for c in client.list_collections():
        client.delete_collection(c.name if hasattr(c, "name") else c)
    _STATE.clear()


def add_chunks(chunks: list[dict]):
    if not chunks:
        return
    collection().upsert(
        ids=[c["chunk_id"] for c in chunks],
        documents=[f"{c['title']}\n{c['text']}" for c in chunks],
        metadatas=[{"case_id": c["case_id"], "doc_type": c["doc_type"], "doc_id": c["doc_id"],
                    "precedence": c["precedence"], "ref": c["ref"], "title": c["title"]} for c in chunks])


def hybrid_search(query: str, case_id: str, doc_types: list[str] | None = None, k: int | None = None) -> list[dict]:
    """Dense (Chroma) + BM25 over the same filtered set, fused with reciprocal rank fusion."""
    k = k or config.RETRIEVAL_TOP_K
    where_cases = {"case_id": {"$in": [case_id, "shared"]}}
    where = {"$and": [where_cases, {"doc_type": {"$in": doc_types}}]} if doc_types else where_cases

    # candidate set from SQLite (same filter) for BM25
    sql = "SELECT * FROM chunks WHERE case_id IN (?, 'shared')"
    args = [case_id]
    if doc_types:
        sql += f" AND doc_type IN ({','.join('?' * len(doc_types))})"
        args += doc_types
    cands = {c["chunk_id"]: c for c in storage.rows(sql, args)}
    if not cands:
        return []

    dense = collection().query(query_texts=[query], n_results=min(len(cands), k * 3), where=where)
    dense_ids = dense["ids"][0] if dense and dense.get("ids") else []

    ids = list(cands)
    bm = BM25Okapi([tokenize(cands[i]["title"] + " " + cands[i]["text"]) for i in ids])
    scores = bm.get_scores(tokenize(query))
    bm_ids = [i for _, i in sorted(zip(scores, ids), key=lambda z: -z[0])][: k * 3]

    fused = {}
    for rank, cid in enumerate(dense_ids):
        fused[cid] = fused.get(cid, 0) + 1 / (60 + rank)
    for rank, cid in enumerate(bm_ids):
        fused[cid] = fused.get(cid, 0) + 1 / (60 + rank)
    top = sorted(fused.items(), key=lambda z: -z[1])[:k]
    out = []
    for cid, s in top:
        if cid in cands:
            c = dict(cands[cid])
            c["score"] = round(s, 5)
            c["dense_rank"] = dense_ids.index(cid) + 1 if cid in dense_ids else None
            c["bm25_rank"] = bm_ids.index(cid) + 1 if cid in bm_ids else None
            out.append(c)
    return out
