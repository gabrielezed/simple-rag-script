# modules/command_handler.py

import os
import time
from . import file_processor

# --- Costanti ---
CODEBASE_DIR = 'codebase'
IGNORE_FILE = '.ragignore'

def handle_help():
    """Stampa il messaggio di aiuto con i comandi disponibili."""
    print("\n--- RAG Console Help ---")
    print("Commands:")
    print("  !reindex          - Force re-indexing of all files in the codebase.")
    print("  !reindex-file <p> - Force re-indexing of a single file. <p> is the path.")
    print("  !status           - Show the number of currently indexed files.")
    print("  !purge            - Clear all data from the embedding database.")
    print("  !help             - Show this help message.")
    print("  !quit             - Exit the application.")
    print("\nTo ask a question, simply type it and press Enter.")
    print("------------------------\n")

def handle_status(db_manager):
    """Mostra lo stato del database."""
    count = db_manager.get_indexed_files_count()
    print(f"\n[Status] Currently {count} files are indexed in the database.\n")

def handle_purge(db_manager):
    """Gestisce la pulizia completa del database con conferma."""
    print("\nWARNING: This will permanently delete all indexed data from the database.")
    confirm = input("Are you sure you want to continue? (Y/N): ").strip().lower()
    if confirm in ['y', 'yes']:
        print("Purging database...")
        success = db_manager.purge_database()
        if success:
            print("Database has been successfully cleared.\n")
        else:
            print("An error occurred while purging the database.\n")
    else:
        print("Purge operation cancelled.\n")

def handle_reindex(db_manager):
    """Gestisce la re-indicizzazione forzata di tutta la codebase."""
    print("\nForcing re-indexing of the entire codebase...")
    start_time = time.time()

    project_root = os.getcwd()
    codebase_path = os.path.join(project_root, CODEBASE_DIR)

    if not os.path.isdir(codebase_path):
        print(f"Error: The '{CODEBASE_DIR}' directory was not found in '{project_root}'.\n")
        return

    ignore_spec = file_processor.get_ignore_patterns(IGNORE_FILE, project_root)
    files_to_process = list(file_processor.load_files_to_index(codebase_path, ignore_spec))
    total_files = len(files_to_process)

    if total_files == 0:
        print(f"No files found to index in the '{CODEBASE_DIR}' directory.\n")
        return

    print(f"Found {total_files} files to re-index.")
    processed_count = 0
    for i, file_path in enumerate(files_to_process):
        print(f"  [{i+1}/{total_files}] Indexing: {os.path.basename(file_path)}...")
        was_indexed = db_manager.index_file(file_path, force=True)
        if was_indexed:
            processed_count += 1

    duration = time.time() - start_time
    print(f"\nRe-indexing completed. {processed_count} files processed in {duration:.2f} seconds.\n")

def handle_reindex_file(db_manager, file_path):
    """Gestisce la re-indicizzazione forzata di un singolo file."""
    if not file_path:
        print("\nError: Missing file path. Usage: !reindex-file <path_to_file>\n")
        return

    if not os.path.exists(file_path):
        print(f"\nError: The file '{file_path}' does not exist.\n")
        return

    print(f"\nForcing re-indexing of file: {file_path}...")
    start_time = time.time()
    was_indexed = db_manager.index_file(file_path, force=True)
    duration = time.time() - start_time

    if was_indexed:
        print(f"File successfully re-indexed in {duration:.2f} seconds.\n")
    else:
        print(f"Could not re-index the file. Check for errors above.\n")