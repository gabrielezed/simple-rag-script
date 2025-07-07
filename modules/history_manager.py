# modules/history_manager.py

import sqlite3

class ChatHistoryManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = self._create_connection()
        if self.conn:
            self._create_table()

    def add_message_to_context(self, context_name, role, content):
        """Adds a message to a context's history."""
        try:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO chat_history (context_name, role, content) VALUES (?, ?, ?)",
                (context_name, role, content)
            )
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error adding message to context '{context_name}': {e}")

    def get_context_history(self, context_name, limit=None):
        """Retrieves the conversation history for a context, optionally limited."""
        try:
            cur = self.conn.cursor()
            query = "SELECT role, content FROM chat_history WHERE context_name = ? ORDER BY timestamp DESC"
            params = [context_name]
            
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)

            cur.execute(query, params)
            messages = cur.fetchall()
            # Reverse the list to restore chronological order for the LLM
            return [dict(zip(['role', 'content'], row)) for row in reversed(messages)]
        except sqlite3.Error as e:
            print(f"Error retrieving context history for '{context_name}': {e}")
            return []

    def list_contexts(self):
        """Returns a list of all unique context names."""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT DISTINCT context_name FROM chat_history ORDER BY context_name")
            contexts = [row[0] for row in cur.fetchall()]
            return contexts
        except sqlite3.Error as e:
            print(f"Error listing contexts: {e}")
            return []

    def delete_context(self, context_name):
        """Deletes an entire conversation context from the database."""
        try:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM chat_history WHERE context_name = ?", (context_name,))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error deleting context '{context_name}': {e}")
            return False
            
    def context_exists(self, context_name):
        """Checks if a context with the given name has any messages."""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT 1 FROM chat_history WHERE context_name = ? LIMIT 1", (context_name,))
            return cur.fetchone() is not None
        except sqlite3.Error:
            return False

    def purge_history(self):
        """Deletes all chat history from the database."""
        try:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM chat_history;")
            self.conn.commit()
            self.conn.execute("VACUUM;")
            return True
        except sqlite3.Error as e:
            print(f"Error purging chat history: {e}")
            return False

    def _create_connection(self):
        try:
            # This can be a separate connection from the embedding manager
            return sqlite3.connect(self.db_path, check_same_thread=False)
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            return None

    def _create_table(self):
        """Creates the chat_history table if it doesn't exist."""
        try:
            cur = self.conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY,
                    context_name TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error creating chat_history table: {e}")

    def close(self):
        if self.conn:
            self.conn.close()