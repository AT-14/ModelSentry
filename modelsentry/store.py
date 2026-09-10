import json
import sqlite3
import threading
from pathlib import Path

from .monitor import RiskAssessment


class EventStore:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA busy_timeout=5000")
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS query_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                client_id TEXT NOT NULL,
                predicted_class INTEGER NOT NULL,
                confidence REAL NOT NULL,
                risk REAL NOT NULL,
                action TEXT NOT NULL,
                allowed INTEGER NOT NULL,
                signals_json TEXT NOT NULL,
                reasons_json TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    def reset(self) -> None:
        with self._lock:
            with self.connection:
                self.connection.execute("DELETE FROM query_events")
                self.connection.execute(
                    "DELETE FROM sqlite_sequence WHERE name = 'query_events'"
                )

    def record(
        self,
        timestamp: float,
        client_id: str,
        predicted_class: int,
        confidence: float,
        assessment: RiskAssessment,
        allowed: bool,
    ) -> None:
        with self._lock:
            self.connection.execute(
                """
                INSERT INTO query_events (
                    timestamp, client_id, predicted_class, confidence, risk,
                    action, allowed, signals_json, reasons_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    client_id,
                    predicted_class,
                    confidence,
                    assessment.risk,
                    assessment.action,
                    int(allowed),
                    json.dumps(assessment.signals),
                    json.dumps(assessment.reasons),
                ),
            )
            self.connection.commit()

    def close(self) -> None:
        with self._lock:
            self.connection.close()
