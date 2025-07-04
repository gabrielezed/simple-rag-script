# modules/db_manager.py

import sqlite3
import os
import hashlib
import numpy as np
import json
import requests
import time

class VectorDB:
    def __init__(self, db_path, config_path='config.json'):
        self.db_path = db_path
        self.conn = self._create_connection()
        self.config_path = config_path
        
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            
            embedding_settings = self.config.get("embedding_settings", {})
            self.mode = embedding_settings.get("mode", "api")

            if self.mode == "local":
                # --- MODIFICATIONS START HERE ---
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError as e:
                    print("\n--- FATAL ERROR: Missing Dependency ---")
                    print(f"The 'local' embedding mode requires the 'sentence-transformers' package, which was not found.")
                    print(f"Please install it from your terminal with the command:")
                    print(f"\n    pip install sentence-transformers\n")
                    exit(1)

                model_name = embedding_settings.get("local_model")
                if not model_name:
                    raise ValueError("Config error: 'local_model' must be set for 'local' embedding mode.")
                
                # Read the trust_remote_code setting from config, defaulting to False for security
                trust_mode = embedding_settings.get("trust_remote_code", False)

                print(f"Mode: 'local'. Loading SentenceTransformer model '{model_name}'...")
                
                try:
                    self.embedding_model = SentenceTransformer(model_name, trust_remote_code=trust_mode)
                except ValueError as e:
                    # Catch and guide the user for missing model-specific dependencies
                    if "requires the following packages" in str(e):
                        package_name = str(e).split("environment: ")[-1].strip()
                        print("\n--- FATAL ERROR: Missing Model Dependency ---")
                        print(f"The model '{model_name}' requires the package '{package_name}', which was not found.")
                        print("To use this model, please install the dependency from your terminal:")
                        print(f"\n    pip install {package_name}\n")
                        exit(1)
                    else:
                        raise # Re-raise other ValueErrors

                print("Model loaded.")
                # --- MODIFICATIONS END HERE ---

            elif self.mode == "api":
                llm_settings = self.config.get("llm_settings", {})
                url = llm_settings.get("server_url")
                if not url:
                    raise ValueError("Config error: 'server_url' must be set for 'api' embedding mode.")
                self.embedding_url = f"{url.rstrip('/')}/embeddings"
                print(f"Mode: 'api'. Using embedding endpoint at {self.embedding_url}")
            else:
                raise ValueError(f"Invalid embedding_mode: '{self.mode}'. Choose 'local' or 'api'.")

        except Exception as e:
            print(f"\nFATAL: Could not initialize DB Manager. Error: {e}")
            exit(1)
            
        if self.conn:
            self._create_tables()

    # --- Metodi per Embedding e Indicizzazione ---

    def get_embedding(self, text_input):
        if self.mode == 'local':
            return self.embedding_model.encode(text_input, show_progress_bar=False)
        else:
            return self._get_embedding_from_api(text_input)

    def _get_embedding_from_api(self, text_chunk):
        headers = {"Content-Type": "application/json"}
        data = {"input": text_chunk, "model": "local-model"}

        try:
            response = requests.post(self.embedding_url, headers=headers, data=json.dumps(data))
            response.raise_for_status()
            embedding = response.json()["data"][0]["embedding"]
            return np.array(embedding, dtype=np.float32)
        except requests.exceptions.RequestException as e:
            print(f"\nAPI Error during embedding: {e}")
            return None
        except (KeyError, IndexError):
            print(f"\nUnexpected API response format: {response.text}")
            return None

    def index_file(self, file_path, force=False):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            file_hash = self._get_file_hash(content)
            if not force and self._is_file_indexed_and_unchanged(file_path, file_hash):
                return False

            cur = self.conn.cursor()
            cur.execute("DELETE FROM files WHERE path=?", (file_path,))
            cur.execute("INSERT INTO files (path, content_hash) VALUES (?, ?)", (file_path, file_hash))
            file_id = cur.lastrowid
            chunks = [chunk for chunk in content.split('\n\n') if chunk.strip()]
            if not chunks: return True

            if self.mode == 'local':
                embeddings = self.get_embedding(chunks)
                chunk_data = [(file_id, chunk, emb.tobytes()) for chunk, emb in zip(chunks, embeddings)]
                cur.executemany("INSERT INTO chunks (file_id, chunk_text, embedding) VALUES (?, ?, ?)", chunk_data)
            else:
                print(f"  > Indexing {len(chunks)} chunks for {os.path.basename(file_path)} via API...")
                start_time = time.time()
                for chunk in chunks:
                    embedding = self.get_embedding(chunk)
                    if embedding is not None:
                        cur.execute("INSERT INTO chunks (file_id, chunk_text, embedding) VALUES (?, ?, ?)",
                                    (file_id, chunk, embedding.tobytes()))
                print(f"  > Finished in {time.time() - start_time:.2f}s")
            
            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error indexing {file_path}: {e}")
            return False

    def find_relevant_chunks(self, question):
        embedding_settings = self.config.get("embedding_settings", {})
        top_k = embedding_settings.get("top_k_chunks", 5)
        
        question_embedding = self.get_embedding(question)
        if question_embedding is None: return []

        cur = self.conn.cursor()
        cur.execute("SELECT chunk_text, embedding FROM chunks")
        all_chunks = cur.fetchall()
        if not all_chunks: return []

        chunk_texts, embeddings_blob = zip(*all_chunks)
        chunk_embeddings = np.array([np.frombuffer(blob, dtype=np.float32) for blob in embeddings_blob])
        
        q_norm = np.linalg.norm(question_embedding)
        if q_norm == 0: return []
        question_embedding /= q_norm

        c_norms = np.linalg.norm(chunk_embeddings, axis=1)
        valid_indices = np.where(c_norms > 0)[0]
        if len(valid_indices) == 0: return []

        valid_embeddings = chunk_embeddings[valid_indices]
        valid_texts = [chunk_texts[i] for i in valid_indices]
        valid_norms = c_norms[valid_indices]

        normalized_chunk_embeddings = valid_embeddings / valid_norms[:, np.newaxis]
        
        similarities = np.dot(normalized_chunk_embeddings, question_embedding)
        
        actual_top_k = min(top_k, len(valid_indices))
        top_k_indices_in_valid = np.argsort(similarities)[-actual_top_k:][::-1]
        
        return [valid_texts[i] for i in top_k_indices_in_valid]

    def purge_database(self):
        try:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM chunks;")
            cur.execute("DELETE FROM files;")
            cur.execute("DELETE FROM chat_history;")
            self.conn.commit()
            
            self.conn.execute("VACUUM;")
            
            return True
        except sqlite3.Error as e:
            print(f"Error purging database: {e}")
            return False

    # --- Metodi per la Gestione del Contesto ---

    def add_message_to_context(self, context_name, role, content):
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
        try:
            cur = self.conn.cursor()
            query = "SELECT role, content FROM chat_history WHERE context_name = ? ORDER BY timestamp DESC"
            params = [context_name]
            
            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)

            cur.execute(query, params)
            messages = cur.fetchall()
            return [dict(zip(['role', 'content'], row)) for row in reversed(messages)]
        except sqlite3.Error as e:
            print(f"Error retrieving context history for '{context_name}': {e}")
            return []

    def list_contexts(self):
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT DISTINCT context_name FROM chat_history ORDER BY context_name")
            contexts = [row[0] for row in cur.fetchall()]
            return contexts
        except sqlite3.Error as e:
            print(f"Error listing contexts: {e}")
            return []

    def delete_context(self, context_name):
        try:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM chat_history WHERE context_name = ?", (context_name,))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error deleting context '{context_name}': {e}")
            return False
            
    def context_exists(self, context_name):
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT 1 FROM chat_history WHERE context_name = ? LIMIT 1", (context_name,))
            return cur.fetchone() is not None
        except sqlite3.Error:
            return False

    # --- Metodi Interni e di Utilità ---

    def _create_connection(self):
        try:
            return sqlite3.connect(self.db_path, check_same_thread=False)
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            return None

    def _create_tables(self):
        try:
            c = self.conn.cursor()
            c.execute("CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY, path TEXT NOT NULL UNIQUE, content_hash TEXT NOT NULL);")
            c.execute("CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL, chunk_text TEXT NOT NULL, embedding BLOB NOT NULL, FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE);")
            c.execute("""
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
            print(f"Error creating tables: {e}")

    def _get_file_hash(self, content):
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _is_file_indexed_and_unchanged(self, file_path, file_hash):
        cur = self.conn.cursor()
        cur.execute("SELECT content_hash FROM files WHERE path=?", (file_path,))
        row = cur.fetchone()
        return row is not None and row[0] == file_hash

    def get_indexed_files_count(self):
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT COUNT(id) FROM files")
            return cur.fetchone()[0]
        except sqlite3.Error:
            return 0
            
    def close(self):
        if self.conn:
            self.conn.close()