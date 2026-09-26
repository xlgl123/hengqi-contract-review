from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.schemas import ReviewListItem, ReviewResult


class ReviewStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    engine_mode TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )

    def save(self, result: ReviewResult) -> None:
        stored_payload = result.model_dump(mode="json", exclude={"document_blocks"})
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO reviews
                    (review_id, filename, engine_mode, result_json, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    result.review_id,
                    result.filename,
                    result.engine_mode,
                    json.dumps(stored_payload, ensure_ascii=False),
                    result.created_at,
                    result.expires_at,
                ),
            )

    def get(self, review_id: str) -> ReviewResult | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT result_json FROM reviews WHERE review_id = ?", (review_id,)
            ).fetchone()
        if row is None:
            return None
        return ReviewResult.model_validate_json(row["result_json"])

    def list_recent(self, limit: int = 10) -> list[ReviewListItem]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT result_json FROM reviews ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        items: list[ReviewListItem] = []
        for row in rows:
            result = ReviewResult.model_validate_json(row["result_json"])
            items.append(
                ReviewListItem(
                    review_id=result.review_id,
                    filename=result.filename,
                    engine_mode=result.engine_mode,
                    contract_type=result.summary.contract_type,
                    total_risks=result.risk_bill.total_risks,
                    high_risks=result.risk_bill.high,
                    created_at=result.created_at,
                    expires_at=result.expires_at,
                )
            )
        return items

    def delete(self, review_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM reviews WHERE review_id = ?", (review_id,))
            return cursor.rowcount > 0

    def purge_expired(self, now_iso: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM reviews WHERE expires_at < ?", (now_iso,))
            return cursor.rowcount
