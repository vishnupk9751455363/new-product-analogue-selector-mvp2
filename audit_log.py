"""
src/audit_log.py
Immutable Audit Trail Handler for Plan Proposals and Human Planner Overrides.

REQUIREMENT:
------------
Every time a planner accepts, overrides, or edits a system-suggested plan, that change
is written to an immutable audit log (who, when, what changed, why, source).
Updates and deletions are strictly blocked by SQLite triggers at the database layer.
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class PlanAuditLogger:
    """Manages appending and retrieving audit trail entries in plan_changes table."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def record_change(
        self,
        product_id: str,
        changed_by: str,
        field_changed: str,
        old_value: Any,
        new_value: Any,
        reason: str,
        source: str  # 'system' or 'planner_override'
    ) -> int:
        """
        Appends an immutable change record to the plan_changes table.

        Args:
            product_id: Target product identifier.
            changed_by: Username, planner id, or system engine name.
            field_changed: Name of field or forecast horizon modified.
            old_value: Previous value (serialized to string or JSON).
            new_value: New value (serialized to string or JSON).
            reason: Text rationale describing justification.
            source: 'system' or 'planner_override'.

        Returns:
            change_id: Primary key of newly inserted audit record.
        """
        if source not in ("system", "planner_override"):
            raise ValueError(f"Invalid source '{source}'. Must be 'system' or 'planner_override'.")

        old_str = json.dumps(old_value) if isinstance(old_value, (dict, list)) else str(old_value)
        new_str = json.dumps(new_value) if isinstance(new_value, (dict, list)) else str(new_value)
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%fZ")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO plan_changes (
                    product_id, changed_by, changed_at, field_changed,
                    old_value, new_value, reason, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (product_id, changed_by, now_utc, field_changed, old_str, new_str, reason, source)
            )
            change_id = cursor.lastrowid
            conn.commit()
            return change_id
        finally:
            conn.close()

    def get_audit_trail(self, product_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves chronological audit history, optionally filtered by product_id.
        """
        conn = self._get_connection()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            if product_id:
                cursor.execute(
                    "SELECT * FROM plan_changes WHERE product_id = ? ORDER BY changed_at ASC, change_id ASC",
                    (product_id,)
                )
            else:
                cursor.execute(
                    "SELECT * FROM plan_changes ORDER BY changed_at ASC, change_id ASC"
                )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
