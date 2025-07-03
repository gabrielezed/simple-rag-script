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
            self.mode = embedding_settings.get("mode", "local")

            if self.mode == "local":
                from sentence_transformers import SentenceTransformer
                model_name = embedding_settings.get("local_model")
                if not model_name:
                    raise ValueError("Config error: 'local_model' must be set for 'local' embedding mode.")
                print(f"Mode: 'local'. Loading SentenceTransformer model '{model_name}'...")
                self.embedding_model = SentenceTransformer(model_name)
                print("Model loaded.")
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
            print(f"FATAL: Could not initialize DB Manager. Error: {e}")
            exit(1)
            
        if self.conn:
            self._create_tables()

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
        
        # --- FIX #1: BROADCASTING ERROR ---
        # Questo è il modo corretto e sicuro per normalizzare gli array
        q_norm = np.linalg.norm(question_embedding)
        if q_norm != 0:
            question_embedding /= q_norm

        c_norms = np.linalg.norm(chunk_embeddings, axis=1, keepdims=True)
        # Evita la divisione per zero sostituendo le norme nulle con 1 (non cambia il vettore nullo)
        c_norms[c_norms == 0] = 1
        normalized_chunk_embeddings = chunk_embeddings / c_norms
        # --- FINE FIX #1 ---
        
        similarities = np.dot(normalized_chunk_embeddings, question_embedding)
        top_k_indices = np.argsort(similarities)[-top_k:][::-1]
        
        return [chunk_texts[i] for i in top_k_indices]

    def purge_database(self):
        try:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM chunks;")
            cur.execute("DELETE FROM files;")
            cur.execute("VACUUM;")
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Error purging database: {e}")
            return False

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
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error creating tables: {e}")

    def _get_file_hash(self, content):
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _is_file_indexed_and_unchanged(self, file_path, file_hash):
        # --- FIX #2: FETCHONE() BUG ---
        # Salva il risultato in una variabile prima di usarlo per evitare di consumarlo
        cur = self.conn.cursor()
        cur.execute("SELECT content_hash FROM files WHERE path=?", (file_path,))
        row = cur.fetchone()
        return row is not None and row[0] == file_hash
        # --- FINE FIX #2 ---

    def get_indexed_files_count(self):
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT COUNT(id) FROM files")
            return cur.fetchone()[0]
        except sqlite3.Error:
            return 0
            
    def close(self):
        if self.conn: self.conn.close()