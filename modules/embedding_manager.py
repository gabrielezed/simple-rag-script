# modules/embedding_manager.py

import sqlite3
import os
import hashlib
import numpy as np
import json
import requests
import time

class EmbeddingManager:
    def __init__(self, db_path, config):
        self.db_path = db_path
        self.config = config
        self.conn = self._create_connection()
        self._initialize_model()

        if self.conn:
            self._create_tables()

    def _initialize_model(self):
        """Initializes the embedding model based on the configuration."""
        embedding_settings = self.config.get("embedding_settings", {})
        self.mode = embedding_settings.get("mode", "api")

        if self.mode == "local":
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                print("\n--- FATAL ERROR: Missing Dependency ---")
                print("The 'local' embedding mode requires the 'sentence-transformers' package, which was not found.")
                print("Please install it from your terminal with the command:")
                print("\n    pip install sentence-transformers\n")
                exit(1)

            model_name = embedding_settings.get("local_model")
            if not model_name:
                raise ValueError("Config error: 'local_model' must be set for 'local' embedding mode.")
            
            trust_mode = embedding_settings.get("trust_remote_code", False)
            print(f"Mode: 'local'. Loading SentenceTransformer model '{model_name}'...")
            
            try:
                self.embedding_model = SentenceTransformer(model_name, trust_remote_code=trust_mode)
            except ValueError as e:
                if "requires the following packages" in str(e):
                    package_name = str(e).split("environment: ")[-1].strip()
                    print("\n--- FATAL ERROR: Missing Model Dependency ---")
                    print(f"The model '{model_name}' requires the package '{package_name}', which was not found.")
                    print("To use this model, please install the dependency from your terminal:")
                    print(f"\n    pip install {package_name}\n")
                    exit(1)
                else:
                    raise
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

    def get_embedding(self, text_input):
        """Generates embeddings for the given text input."""
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
        """Indexes a single file, splitting it into chunks and storing their embeddings."""
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
            if not chunks: 
                self.conn.commit()
                return True

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
            self.conn.rollback()
            return False

    def find_relevant_chunks(self, question):
        """Finds the most relevant chunks in the DB for a given question."""
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

    def get_indexed_files_count(self):
        """Returns the number of files currently indexed."""
        try:
            cur = self.conn.cursor()
            cur.execute("SELECT COUNT(id) FROM files")
            return cur.fetchone()[0]
        except sqlite3.Error:
            return 0

    def purge_embeddings(self):
        """Deletes all embedding and file data from the database."""
        try:
            cur = self.conn.cursor()
            cur.execute("DELETE FROM chunks;")
            cur.execute("DELETE FROM files;")
            self.conn.commit()
            self.conn.execute("VACUUM;")
            return True
        except sqlite3.Error as e:
            print(f"Error purging embedding tables: {e}")
            return False

    def _create_connection(self):
        try:
            return sqlite3.connect(self.db_path, check_same_thread=False)
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            return None

    def _create_tables(self):
        """Creates the necessary tables for embeddings if they don't exist."""
        try:
            cur = self.conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY, path TEXT NOT NULL UNIQUE, content_hash TEXT NOT NULL);")
            cur.execute("CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL, chunk_text TEXT NOT NULL, embedding BLOB NOT NULL, FOREIGN KEY (file_id) REFERENCES files (id) ON DELETE CASCADE);")
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error creating embedding tables: {e}")

    def _get_file_hash(self, content):
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def _is_file_indexed_and_unchanged(self, file_path, file_hash):
        cur = self.conn.cursor()
        cur.execute("SELECT content_hash FROM files WHERE path=?", (file_path,))
        row = cur.fetchone()
        return row is not None and row[0] == file_hash
            
    def close(self):
        if self.conn:
            self.conn.close()