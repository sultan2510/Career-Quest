"""Idempotently load CareerQuest's RAG documents without deleting other rows.

Run from the repository root: python -m backend.ingest
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import asyncpg

HERE = Path(__file__).resolve().parent


def load_env() -> None:
    path = HERE / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.strip().partition("=")
            if separator and key and not key.startswith("#"):
                os.environ.setdefault(key, value)


async def ingest(db, documents: list[dict]) -> None:
    """Upsert only managed source keys; preserve legacy and unrelated rows."""
    rows = [(doc["id"], doc["title"], doc["text"], doc.get("url"),
             doc.get("kind", "knowledge"), json.dumps(doc.get("metadata", {})))
            for doc in documents]
    async with db.transaction():
        await db.executemany(
            "insert into rag_chunks(source_key,title,content,url,kind,metadata) "
            "values($1,$2,$3,$4,$5,$6::jsonb) "
            "on conflict (source_key) do update set title=excluded.title, content=excluded.content, "
            "url=excluded.url, kind=excluded.kind, metadata=excluded.metadata",
            rows,
        )


async def main() -> None:
    from backend.rag_service import load_documents

    load_env()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("Set DATABASE_URL before ingesting RAG documents")
    connection = await asyncpg.connect(database_url, statement_cache_size=0)
    try:
        migration = (HERE / "migrations/001_rag_sources.sql").read_text(encoding="utf-8")
        await connection.execute(migration)
        documents = load_documents()
        await ingest(connection, documents)
        print(f"Ingested {len(documents)} managed documents")
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())
