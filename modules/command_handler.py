# modules/command_handler.py

import os
import time
from . import file_processor
from .terminal_colors import Colors # Importa i colori

CODEBASE_DIR = 'codebase'
IGNORE_FILE = '.ragignore'

def handle_help():
    """Prints the help message with available commands."""
    print(f"\n{Colors.GREEN}--- RAG Console Help ---{Colors.RESET}")
    print("Commands:")
    print("  !reindex          - Force re-indexing of all files in the codebase.")
    print("  !reindex-file <p> - Force re-indexing of a single file. <p> is the path.")
    print("  !status           - Show the number of currently indexed files.")
    print(f"  !purge            - {Colors.YELLOW}Destructive.{Colors.RESET} Clear all data from the database.")
    print("  !help             - Show this help message.")
    print("  !quit             - Exit the application.")
    print(f"\n{Colors.MAGENTA}Context Management:{Colors.RESET}")
    print("  !context-on       - Enable conversation history for subsequent questions.")
    print("  !context-off      - Disable conversation history (one-shot questions).")
    print("  !context-list     - Show a list of all saved conversation contexts.")
    print("  !context-switch <n> - Switch to an existing conversation context named <n>.")
    print("  !context-new <n>  - Create and switch to a new, empty context named <n>.")
    print(f"  !context-clear    - {Colors.YELLOW}Destructive.{Colors.RESET} Clear the history of the current context.")
    print(f"  !context-delete <n> - {Colors.YELLOW}Destructive.{Colors.RESET} Permanently delete a context named <n>.")
    print(f"\n{Colors.MAGENTA}Session Settings:{Colors.RESET}")
    print("  !settings <param> <value> - Change a setting for the current session only.")
    print("    - available params: 'temperature'")
    print("\nTo ask a question, simply type it and press Enter.")
    print(f"{Colors.GREEN}------------------------{Colors.RESET}\n")

def handle_status(embedding_manager):
    """Shows the database status."""
    count = embedding_manager.get_indexed_files_count()
    print(f"\n[Status] Currently {Colors.GREEN}{count}{Colors.RESET} files are indexed in the database.\n")

def handle_purge(embedding_manager, history_manager):
    """Handles the complete purging of the database with confirmation."""
    print(f"\n{Colors.YELLOW}WARNING: This will permanently delete ALL indexed data and ALL conversation history.{Colors.RESET}")
    confirm = input("Are you sure you want to continue? (Y/N): ").strip().lower()
    if confirm in ['y', 'yes']:
        print("Purging database...")
        e_success = embedding_manager.purge_embeddings()
        h_success = history_manager.purge_history()
        if e_success and h_success:
            print(f"{Colors.GREEN}Database has been successfully cleared.{Colors.RESET}\n")
        else:
            print(f"{Colors.RED}An error occurred while purging the database.{Colors.RESET}\n")
    else:
        print("Purge operation cancelled.\n")

def handle_reindex(embedding_manager):
    """Handles the forced re-indexing of the entire codebase."""
    print("\nForcing re-indexing of the entire codebase...")
    start_time = time.time()
    project_root = os.getcwd()
    codebase_path = os.path.join(project_root, CODEBASE_DIR)
    if not os.path.isdir(codebase_path):
        print(f"{Colors.RED}Error: The '{CODEBASE_DIR}' directory was not found in '{project_root}'.{Colors.RESET}\n")
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
        was_indexed = embedding_manager.index_file(file_path, force=True)
        if was_indexed:
            processed_count += 1
    duration = time.time() - start_time
    print(f"\n{Colors.GREEN}Re-indexing completed. {processed_count} files processed in {duration:.2f} seconds.{Colors.RESET}\n")

def handle_reindex_file(embedding_manager, file_path):
    """Handles the forced re-indexing of a single file."""
    if not file_path:
        print(f"\n{Colors.RED}Error: Missing file path. Usage: !reindex-file <path_to_file>{Colors.RESET}\n")
        return
    if not os.path.exists(file_path):
        print(f"\n{Colors.RED}Error: The file '{file_path}' does not exist.{Colors.RESET}\n")
        return
    print(f"\nForcing re-indexing of file: {file_path}...")
    start_time = time.time()
    was_indexed = embedding_manager.index_file(file_path, force=True)
    duration = time.time() - start_time
    if was_indexed:
        print(f"File successfully re-indexed in {duration:.2f} seconds.\n")
    else:
        print(f"{Colors.RED}Could not re-index the file. Check for errors above.{Colors.RESET}\n")

def handle_context_on():
    print(f"\n{Colors.GREEN}Context history ENABLED.{Colors.RESET}\n")
    return True

def handle_context_off():
    print(f"\n{Colors.YELLOW}Context history DISABLED.{Colors.RESET}\n")
    return False

def handle_context_list(history_manager):
    contexts = history_manager.list_contexts()
    if not contexts:
        print("\nNo conversation contexts found.\n")
        return
    print("\nAvailable contexts:")
    for name in contexts:
        print(f"  - {Colors.MAGENTA}{name}{Colors.RESET}")
    print()

def handle_context_switch(history_manager, new_context):
    if not new_context:
        print(f"\n{Colors.RED}Error: Missing context name. Usage: !context-switch <name>{Colors.RESET}\n")
        return None
    if new_context == 'default' or history_manager.context_exists(new_context):
        print(f"\nSwitched to context: '{Colors.MAGENTA}{new_context}{Colors.RESET}'.\n")
        return new_context
    else:
        print(f"\n{Colors.RED}Error: Context '{new_context}' not found.{Colors.RESET}\n")
        return None

def handle_context_new(history_manager, new_context):
    if not new_context:
        print(f"\n{Colors.RED}Error: Missing context name. Usage: !context-new <name>{Colors.RESET}\n")
        return None
    if history_manager.context_exists(new_context):
        print(f"\n{Colors.RED}Error: Context '{new_context}' already exists. Use !context-switch to activate it.{Colors.RESET}\n")
        return None
    print(f"\nCreated and switched to new context: '{Colors.MAGENTA}{new_context}{Colors.RESET}'.")
    print("This context will be saved permanently after the first message.\n")
    return new_context

def handle_context_clear(history_manager, active_context):
    """Clears the history of the currently active context."""
    print(f"\n{Colors.YELLOW}WARNING: This will permanently delete the conversation history for the active context ('{active_context}').{Colors.RESET}")
    confirm = input("Are you sure you want to continue? (Y/N): ").strip().lower()
    if confirm in ['y', 'yes']:
        if history_manager.delete_context(active_context):
            print(f"Successfully cleared history for context: '{Colors.MAGENTA}{active_context}{Colors.RESET}'.\n")
        else:
            print(f"{Colors.RED}An error occurred while clearing the context history.{Colors.RESET}\n")
    else:
        print("Operation cancelled.\n")

def handle_context_delete(history_manager, context_to_delete, active_context):
    if not context_to_delete:
        print(f"\n{Colors.RED}Error: Missing context name. Usage: !context-delete <name>{Colors.RESET}\n")
        return
    if context_to_delete == active_context:
        print(f"\n{Colors.RED}Error: Cannot delete the currently active context ('{active_context}'). Switch to another context first.{Colors.RESET}\n")
        return
    if not history_manager.context_exists(context_to_delete):
        print(f"\n{Colors.RED}Error: Context '{context_to_delete}' not found.{Colors.RESET}\n")
        return
    print(f"\n{Colors.YELLOW}WARNING: This will permanently delete the entire conversation history for '{context_to_delete}'.{Colors.RESET}")
    confirm = input("Are you sure? (Y/N): ").strip().lower()
    if confirm in ['y', 'yes']:
        if history_manager.delete_context(context_to_delete):
            print(f"Successfully deleted context: '{Colors.MAGENTA}{context_to_delete}{Colors.RESET}'.\n")
        else:
            print(f"{Colors.RED}An error occurred while deleting context '{context_to_delete}'.{Colors.RESET}\n")
    else:
        print("Delete operation cancelled.\n")

def handle_setting_set(session_settings, args):
    """Sets a configuration parameter for the current session only."""
    if len(args) < 2:
        print(f"\n{Colors.RED}Error: Missing parameter and value. Usage: !settings <param> <value>{Colors.RESET}\n")
        return

    param = args[0].lower()
    value = " ".join(args[1:])
    allowed_params = {'temperature': float}

    if param not in allowed_params:
        print(f"\n{Colors.RED}Error: Unknown parameter '{param}'. Allowed parameters are: {', '.join(allowed_params.keys())}{Colors.RESET}\n")
        return

    try:
        converted_value = allowed_params[param](value)
    except ValueError:
        print(f"\n{Colors.RED}Error: Invalid value for '{param}'. Expected a {allowed_params[param].__name__}.{Colors.RESET}\n")
        return

    session_settings[param] = converted_value
    print(f"\nSession setting updated: '{param}' is now {converted_value}.\n{Colors.YELLOW}This change is temporary and will be lost on exit.{Colors.RESET}\n")