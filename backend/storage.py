"""PostgreSQL + pgvector persistence for interview sessions."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import psycopg

logger = logging.getLogger("algo-storage")


class SessionStore:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "")
        self.enabled = bool(self.database_url)

    def _connect(self):
        return psycopg.connect(self.database_url, autocommit=True)

    async def ensure_schema(self) -> None:
        if not self.enabled:
            logger.warning("DATABASE_URL is not set; persistence disabled.")
            return
        import asyncio

        await asyncio.to_thread(self._ensure_schema_sync)

    def _ensure_schema_sync(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS interview_sessions (
                    id TEXT PRIMARY KEY,
                    round_type TEXT NOT NULL,
                    resume_text TEXT DEFAULT '',
                    resume_file_name TEXT DEFAULT '',
                    weak_areas JSONB NOT NULL DEFAULT '[]',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS session_events (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT REFERENCES interview_sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS skill_graphs (
                    id BIGSERIAL PRIMARY KEY,
                    session_id TEXT REFERENCES interview_sessions(id) ON DELETE CASCADE,
                    skill TEXT NOT NULL,
                    score DOUBLE PRECISION NOT NULL DEFAULT 0,
                    evidence TEXT DEFAULT '',
                    embedding vector(1536),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
                """
            )
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_skill_graphs_session_skill ON skill_graphs(session_id, skill);"
            )

    async def upsert_session(
        self,
        *,
        session_id: str,
        round_type: str,
        resume_text: str,
        resume_file_name: str,
        weak_areas: list[str],
    ) -> None:
        if not self.enabled:
            return
        import asyncio

        await asyncio.to_thread(
            self._upsert_session_sync,
            session_id,
            round_type,
            resume_text,
            resume_file_name,
            weak_areas,
        )

    def _upsert_session_sync(
        self,
        session_id: str,
        round_type: str,
        resume_text: str,
        resume_file_name: str,
        weak_areas: list[str],
    ) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO interview_sessions (id, round_type, resume_text, resume_file_name, weak_areas)
                VALUES (%s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                    round_type = EXCLUDED.round_type,
                    resume_text = EXCLUDED.resume_text,
                    resume_file_name = EXCLUDED.resume_file_name,
                    weak_areas = EXCLUDED.weak_areas,
                    updated_at = now();
                """,
                (session_id, round_type, resume_text, resume_file_name, json.dumps(weak_areas)),
            )

    async def add_event(self, session_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        if not self.enabled:
            return
        import asyncio

        await asyncio.to_thread(self._add_event_sync, session_id, role, content, metadata or {})

    def _add_event_sync(self, session_id: str, role: str, content: str, metadata: dict[str, Any]) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO session_events (session_id, role, content, metadata)
                VALUES (%s, %s, %s, %s::jsonb);
                """,
                (session_id, role, content, json.dumps(metadata)),
            )

    async def upsert_skill_scores(self, session_id: str, scores: list[dict[str, Any]]) -> None:
        if not self.enabled:
            return
        import asyncio

        await asyncio.to_thread(self._upsert_skill_scores_sync, session_id, scores)

    def _upsert_skill_scores_sync(self, session_id: str, scores: list[dict[str, Any]]) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            for item in scores:
                skill = str(item.get("skill", "")).strip()
                if not skill:
                    continue
                score = float(item.get("score", 0))
                evidence = str(item.get("evidence", ""))
                cur.execute(
                    """
                    INSERT INTO skill_graphs (session_id, skill, score, evidence)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING;
                    """,
                    (session_id, skill, score, evidence),
                )
                cur.execute(
                    """
                    UPDATE skill_graphs
                    SET score = %s, evidence = %s, updated_at = now()
                    WHERE session_id = %s AND skill = %s;
                    """,
                    (score, evidence, session_id, skill),
                )
