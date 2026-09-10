import json
import sqlite3
from pathlib import Path


MITIGATION_ACTIONS = ("throttle", "block")


def _json_object(value: str) -> dict:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return [str(item) for item in parsed] if isinstance(parsed, list) else []


def empty_live_state() -> dict:
    return {
        "total_requests": 0,
        "normal_requests": 0,
        "attack_requests": 0,
        "denied_requests": 0,
        "phase": "ready",
        "alert": None,
        "latest": None,
        "recent_events": [],
    }


def read_live_state(database: Path) -> dict:
    if not database.exists():
        return empty_live_state()
    try:
        with sqlite3.connect(database, timeout=0.5) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN")
            total = connection.execute(
                "SELECT COUNT(*) FROM query_events"
            ).fetchone()[0]
            if total == 0:
                return empty_live_state()
            normal = connection.execute(
                "SELECT COUNT(*) FROM query_events WHERE client_id = 'normal-client'"
            ).fetchone()[0]
            attack = connection.execute(
                "SELECT COUNT(*) FROM query_events WHERE client_id = 'extractor-client'"
            ).fetchone()[0]
            denied = connection.execute(
                "SELECT COUNT(*) FROM query_events WHERE allowed = 0"
            ).fetchone()[0]
            latest = connection.execute(
                "SELECT * FROM query_events ORDER BY id DESC LIMIT 1"
            ).fetchone()
            first_attack = connection.execute(
                "SELECT timestamp FROM query_events "
                "WHERE client_id = 'extractor-client' ORDER BY id LIMIT 1"
            ).fetchone()
            alert = connection.execute(
                "SELECT * FROM query_events WHERE action IN ('throttle', 'block') "
                "ORDER BY id LIMIT 1"
            ).fetchone()
            alert_attack_query = (
                connection.execute(
                    "SELECT COUNT(*) FROM query_events "
                    "WHERE client_id = 'extractor-client' AND id <= ?",
                    (alert["id"],),
                ).fetchone()[0]
                if alert is not None
                else None
            )
            recent = connection.execute(
                "SELECT id, client_id, risk, action, allowed, reasons_json "
                "FROM query_events ORDER BY id DESC LIMIT 20"
            ).fetchall()
    except sqlite3.OperationalError as error:
        state = empty_live_state()
        state["error"] = str(error)
        return state

    phase = "alert" if alert else "attack" if attack else "normal"

    def event(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        result = dict(row)
        result["signals"] = _json_object(result.pop("signals_json", "{}"))
        result["reasons"] = _json_list(result.pop("reasons_json", "[]"))
        return result

    alert_event = event(alert)
    if (
        alert_event is not None
        and alert_event["client_id"] == "extractor-client"
        and first_attack is not None
    ):
        alert_event["elapsed_seconds"] = max(
            0.0, float(alert_event["timestamp"] - first_attack["timestamp"])
        )
        alert_event["attack_query"] = int(alert_attack_query)

    return {
        "total_requests": int(total),
        "normal_requests": int(normal),
        "attack_requests": int(attack),
        "denied_requests": int(denied),
        "phase": phase,
        "alert": alert_event,
        "latest": event(latest),
        "recent_events": [dict(row) for row in recent],
    }
