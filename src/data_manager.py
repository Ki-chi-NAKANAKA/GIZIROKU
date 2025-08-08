import sqlite3
import json
import os
from pathlib import Path


class DataManager:
    """
    Manages the storage and retrieval of meeting minutes.

    Uses an SQLite database for metadata and JSON files for details.
    """

    def __init__(self, base_dir: Path):
        """
        Initializes the DataManager.

        Args:
            base_dir: The base directory for storing data (db and json files).
        """
        self.data_dir = base_dir / "data"
        self.db_path = base_dir / "minutes.db"
        os.makedirs(self.data_dir, exist_ok=True)

    def initialize_database(self):
        """Creates the database and the minutes table if they don't exist."""
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS minutes (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    original_filepath TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            con.commit()
            con.close()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            raise

    def save_minutes(self, original_filepath: str, content_dict: dict) -> int:
        """
        Saves a new minute's metadata to the DB and details to a JSON file.

        Args:
            original_filepath: The path to the original audio file.
            content_dict: A dictionary with summary, decisions, todo, full_text.

        Returns:
            The ID of the newly saved minute.
        """
        title = Path(original_filepath).name
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute(
                "INSERT INTO minutes (title, original_filepath) VALUES (?, ?)",
                (title, original_filepath)
            )
            new_id = cur.lastrowid
            con.commit()
            con.close()

            json_path = self.data_dir / f"{new_id}.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(content_dict, f, ensure_ascii=False, indent=4)
            return new_id
        except sqlite3.Error as e:
            print(f"Database error during save: {e}")
            raise
        except IOError as e:
            print(f"File writing error during save: {e}")
            self.delete_minute(new_id)
            raise

    def load_all_minutes(self) -> list:
        """
        Loads all minute records from the database, ordered by creation date.

        Returns:
            A list of tuples, e.g., [(id, title, created_at), ...].
        """
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute(
                "SELECT id, title, created_at FROM minutes ORDER BY created_at DESC"
            )
            records = cur.fetchall()
            con.close()
            return records
        except sqlite3.Error as e:
            print(f"Database error during load all: {e}")
            return []

    def load_minute_details(self, minute_id: int) -> dict:
        """
        Loads the detailed content of a specific minute from its JSON file.

        Args:
            minute_id: The ID of the minute to load.

        Returns:
            A dictionary with the minute's content, or an empty dict if not found.
        """
        json_path = self.data_dir / f"{minute_id}.json"
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                content = json.load(f)
            return content
        except FileNotFoundError:
            print(f"Details file not found for minute ID: {minute_id}")
            return {}
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error reading details file for minute ID {minute_id}: {e}")
            return {}

    def delete_minute(self, minute_id: int):
        """
        Deletes a minute's record from the DB and its corresponding JSON file.

        Args:
            minute_id: The ID of the minute to delete.
        """
        try:
            con = sqlite3.connect(self.db_path)
            cur = con.cursor()
            cur.execute("DELETE FROM minutes WHERE id = ?", (minute_id,))
            con.commit()
            con.close()

            json_path = self.data_dir / f"{minute_id}.json"
            if os.path.exists(json_path):
                os.remove(json_path)
        except sqlite3.Error as e:
            print(f"Database error during delete: {e}")
            raise
        except IOError as e:
            print(f"File deletion error: {e}")
            raise
