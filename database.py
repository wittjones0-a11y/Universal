"""Database management for bot logging and verification."""
import sqlite3
import json
from datetime import datetime
from pathlib import Path

class Database:
    def __init__(self, db_path: str = "data/bot_data.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self):
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initialize the database with required tables."""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Guild settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                verification_channel INTEGER,
                log_channel INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # User verification table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                verified BOOLEAN DEFAULT 0,
                verified_at TIMESTAMP,
                warnings INTEGER DEFAULT 0,
                muted BOOLEAN DEFAULT 0,
                mute_until TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Message logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Moderation actions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS moderation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                reason TEXT,
                moderator_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Warnings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                reason TEXT,
                moderator_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()

    def add_user(self, user_id: int, guild_id: int):
        """Add a new user to tracking."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR IGNORE INTO users (user_id, guild_id) VALUES (?, ?)",
                (user_id, guild_id)
            )
            conn.commit()
        finally:
            conn.close()

    def verify_user(self, user_id: int, guild_id: int):
        """Mark user as verified."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE users SET verified = 1, verified_at = ? WHERE user_id = ? AND guild_id = ?",
                (datetime.utcnow(), user_id, guild_id)
            )
            conn.commit()
        finally:
            conn.close()

    def is_verified(self, user_id: int, guild_id: int) -> bool:
        """Check if user is verified."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT verified FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            result = cursor.fetchone()
            return result[0] if result else False
        finally:
            conn.close()

    def log_message(self, user_id: int, guild_id: int, channel_id: int,
                   message_id: int, content: str):
        """Log a message."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO message_logs 
                   (user_id, guild_id, channel_id, message_id, content)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, guild_id, channel_id, message_id, content)
            )
            conn.commit()
        finally:
            conn.close()

    def log_moderation(self, user_id: int, guild_id: int, action: str,
                      reason: str = None, moderator_id: int = None):
        """Log a moderation action."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO moderation_logs
                   (user_id, guild_id, action, reason, moderator_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, guild_id, action, reason, moderator_id)
            )
            conn.commit()
        finally:
            conn.close()

    def add_warning(self, user_id: int, guild_id: int, reason: str = None,
                   moderator_id: int = None) -> int:
        """Add a warning to a user and return warning count."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO warnings
                   (user_id, guild_id, reason, moderator_id)
                   VALUES (?, ?, ?, ?)""",
                (user_id, guild_id, reason, moderator_id)
            )
            cursor.execute(
                "SELECT COUNT(*) FROM warnings WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            count = cursor.fetchone()[0]
            conn.commit()
            return count
        finally:
            conn.close()

    def get_warnings(self, user_id: int, guild_id: int) -> int:
        """Get warning count for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM warnings WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def get_user_logs(self, user_id: int, guild_id: int, limit: int = 10):
        """Get recent moderation logs for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT action, reason, timestamp FROM moderation_logs
                   WHERE user_id = ? AND guild_id = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (user_id, guild_id, limit)
            )
            return cursor.fetchall()
        finally:
            conn.close()

    def get_message_logs(self, user_id: int, guild_id: int, limit: int = 10):
        """Get recent message logs for a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """SELECT channel_id, content, timestamp FROM message_logs
                   WHERE user_id = ? AND guild_id = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (user_id, guild_id, limit)
            )
            return cursor.fetchall()
        finally:
            conn.close()

    def set_muted(self, user_id: int, guild_id: int, mute_until: datetime = None):
        """Set or remove mute on a user."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if mute_until:
                cursor.execute(
                    "UPDATE users SET muted = 1, mute_until = ? WHERE user_id = ? AND guild_id = ?",
                    (mute_until, user_id, guild_id)
                )
            else:
                cursor.execute(
                    "UPDATE users SET muted = 0, mute_until = NULL WHERE user_id = ? AND guild_id = ?",
                    (user_id, guild_id)
                )
            conn.commit()
        finally:
            conn.close()

    def is_muted(self, user_id: int, guild_id: int) -> bool:
        """Check if user is muted."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT muted, mute_until FROM users WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            result = cursor.fetchone()
            if not result:
                return False
            muted, mute_until = result
            if not muted:
                return False
            if mute_until and datetime.fromisoformat(mute_until) < datetime.utcnow():
                self.set_muted(user_id, guild_id)
                return False
            return True
        finally:
            conn.close()
    def set_verification_channel(self, guild_id: int, channel_id: int):
        """Set the verification channel for a guild."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO guild_settings (guild_id, verification_channel) VALUES (?, ?)",
                (guild_id, channel_id)
            )
            conn.commit()
        finally:
            conn.close()

    def get_verification_channel(self, guild_id: int) -> int:
        """Get the verification channel for a guild."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT verification_channel FROM guild_settings WHERE guild_id = ?",
                (guild_id,)
            )
            result = cursor.fetchone()
            return result[0] if result and result[0] else None
        finally:
            conn.close()

    def set_log_channel(self, guild_id: int, channel_id: int):
        """Set the log channel for a guild."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO guild_settings (guild_id, log_channel) VALUES (?, ?)",
                (guild_id, channel_id)
            )
            conn.commit()
        finally:
            conn.close()

    def get_log_channel(self, guild_id: int) -> int:
        """Get the log channel for a guild."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT log_channel FROM guild_settings WHERE guild_id = ?",
                (guild_id,)
            )
            result = cursor.fetchone()
            return result[0] if result and result[0] else None
        finally:
            conn.close()