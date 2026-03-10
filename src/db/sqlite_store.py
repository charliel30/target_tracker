"""
sqlite_store.py

A simple SQLite-backed store for temporal target data.
Uses Python's built-in sqlite3 module — no external dependencies.
"""

import os
import sqlite3


class SQLiteStore:
    """Manages a SQLite database for storing and querying target intelligence data."""

    def __init__(self, db_path: str):
        """Open (or create) the database and ensure all tables exist."""
        self.db_path = db_path
        parent = os.path.dirname(db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        # check_same_thread=False is required because the OpenAI Agents SDK
        # runs sync @function_tool handlers via asyncio.to_thread(), which
        # executes them in a different thread than the one that created this
        # connection.  Without this flag, any agent-invoked query tool would
        # raise: sqlite3.ProgrammingError: SQLite objects created in a thread
        # can only be used in that same thread.
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        # Return rows as dict-like objects so callers can use column names
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_tables(self):
        """Create tables if they don't already exist."""
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS suspicious_activities (
                target_name TEXT,
                timestamp   TEXT,
                description TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS nonsuspicious_activities (
                target_name TEXT,
                timestamp   TEXT,
                description TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS known_whereabouts (
                target_name TEXT,
                city        TEXT,
                start_date  TEXT,
                end_date    TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS priors (
                target_name TEXT,
                date        TEXT,
                description TEXT
            )
        """)

        self.conn.commit()

    # ------------------------------------------------------------------
    # Bulk load
    # ------------------------------------------------------------------

    def load_targets(self, targets: dict):
        """
        Bulk-load temporal data from a targets dict.

        Clears all existing data first, then inserts every record.

        targets format:
            {
                "Alice": {
                    "suspicious_activities":    [{"timestamp": ..., "description": ...}, ...],
                    "nonsuspicious_activities": [{"timestamp": ..., "description": ...}, ...],
                    "known_whereabouts":        [{"city": ..., "start_date": ..., "end_date": ...}, ...],
                    "priors":                   [{"date": ..., "description": ...}, ...],
                },
                ...
            }
        """
        cursor = self.conn.cursor()

        # Wipe existing data so we start fresh
        for table in ("suspicious_activities", "nonsuspicious_activities",
                      "known_whereabouts", "priors"):
            cursor.execute(f"DELETE FROM {table}")

        for target_name, data in targets.items():
            # Suspicious activities
            for item in data.get("suspicious_activities", []):
                cursor.execute(
                    "INSERT INTO suspicious_activities VALUES (?, ?, ?)",
                    (target_name, item["timestamp"], item["description"]),
                )

            # Non-suspicious activities
            for item in data.get("nonsuspicious_activities", []):
                cursor.execute(
                    "INSERT INTO nonsuspicious_activities VALUES (?, ?, ?)",
                    (target_name, item["timestamp"], item["description"]),
                )

            # Known whereabouts
            for item in data.get("known_whereabouts", []):
                cursor.execute(
                    "INSERT INTO known_whereabouts VALUES (?, ?, ?, ?)",
                    (target_name, item["city"], item["start_date"], item["end_date"]),
                )

            # Priors (past offences / criminal history)
            for item in data.get("priors", []):
                cursor.execute(
                    "INSERT INTO priors VALUES (?, ?, ?)",
                    (target_name, item["date"], item["description"]),
                )

        self.conn.commit()

    # ------------------------------------------------------------------
    # Single-record inserts
    # ------------------------------------------------------------------

    def add_activity(self, target_name: str, activity_type: str, data: dict):
        """
        Add a single activity for a target.

        activity_type: "suspicious" or "nonsuspicious"
        data: {"timestamp": ..., "description": ...}
        """
        table = (
            "suspicious_activities"
            if activity_type == "suspicious"
            else "nonsuspicious_activities"
        )
        self.conn.execute(
            f"INSERT INTO {table} VALUES (?, ?, ?)",
            (target_name, data["timestamp"], data["description"]),
        )
        self.conn.commit()

    def add_whereabouts(self, target_name: str, data: dict):
        """
        Add a single whereabouts record for a target.

        data: {"city": ..., "start_date": ..., "end_date": ...}
        """
        self.conn.execute(
            "INSERT INTO known_whereabouts VALUES (?, ?, ?, ?)",
            (target_name, data["city"], data["start_date"], data["end_date"]),
        )
        self.conn.commit()

    def add_prior(self, target_name: str, data: dict):
        """
        Add a single prior (past offence) record for a target.

        data: {"date": ..., "description": ...}
        """
        self.conn.execute(
            "INSERT INTO priors VALUES (?, ?, ?)",
            (target_name, data["date"], data["description"]),
        )
        self.conn.commit()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def query_whereabouts(
        self,
        city: str,
        start_date: str = None,
        end_date: str = None,
    ) -> list:
        """
        Find targets known to be in a given city, optionally within a date range.

        Dates are compared lexicographically, so ISO-8601 format (YYYY-MM-DD) works best.
        Returns a list of dicts with keys: target_name, city, start_date, end_date.
        """
        query = "SELECT * FROM known_whereabouts WHERE city = ?"
        params = [city]

        # Narrow by date range when provided
        if start_date:
            query += " AND end_date >= ?"   # record ends on or after our window opens
            params.append(start_date)
        if end_date:
            query += " AND start_date <= ?"  # record starts on or before our window closes
            params.append(end_date)

        rows = self.conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def query_priors(self, location_keyword: str = None) -> list:
        """
        Find targets with priors, optionally filtered by a keyword in the description.

        Returns a list of dicts with keys: target_name, date, description.
        """
        if location_keyword:
            rows = self.conn.execute(
                "SELECT * FROM priors WHERE description LIKE ?",
                (f"%{location_keyword}%",),
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM priors").fetchall()

        return [dict(row) for row in rows]

    def query_activities(self, target_name: str, suspicious_only: bool = False) -> list:
        """
        Get activity records for a specific target.

        suspicious_only=True  — return only suspicious activities.
        suspicious_only=False — return both suspicious and non-suspicious activities,
                                with an extra "type" field on each record.

        Returns a list of dicts with keys: target_name, timestamp, description[, type].
        """
        if suspicious_only:
            rows = self.conn.execute(
                "SELECT * FROM suspicious_activities WHERE target_name = ?",
                (target_name,),
            ).fetchall()
            return [dict(row) for row in rows]

        # Combine both tables, tagging each row with its type
        suspicious = self.conn.execute(
            "SELECT *, 'suspicious' AS type FROM suspicious_activities WHERE target_name = ?",
            (target_name,),
        ).fetchall()

        nonsuspicious = self.conn.execute(
            "SELECT *, 'nonsuspicious' AS type FROM nonsuspicious_activities WHERE target_name = ?",
            (target_name,),
        ).fetchall()

        # Merge and sort chronologically
        combined = [dict(row) for row in suspicious + nonsuspicious]
        combined.sort(key=lambda r: r.get("timestamp", ""))
        return combined

    def get_all_temporal_data(self, target_name: str) -> dict:
        """
        Return all stored temporal data for a target as a single dict.

        Structure mirrors the input format used by load_targets():
            {
                "suspicious_activities":    [...],
                "nonsuspicious_activities": [...],
                "known_whereabouts":        [...],
                "priors":                   [...],
            }
        """
        def fetch(table):
            rows = self.conn.execute(
                f"SELECT * FROM {table} WHERE target_name = ?",
                (target_name,),
            ).fetchall()
            return [dict(row) for row in rows]

        return {
            "suspicious_activities":    fetch("suspicious_activities"),
            "nonsuspicious_activities": fetch("nonsuspicious_activities"),
            "known_whereabouts":        fetch("known_whereabouts"),
            "priors":                   fetch("priors"),
        }
