# rag_script.py

import json
import os

# Prova a importare readline per la cronologia dei comandi nella console
try:
    import readline
except ImportError:
    print("Info: 'readline' module not available. Command history will not be saved.")

from modules.db_manager import VectorDB
from modules.llm_client import ask_local_llm
from modules import command_handler

# --- Costanti di Configurazione ---
CONFIG_FILE = 'config.json'
DB_PATH = 'rag_database.db'

def load_config(config_file):
    """Carica il file di configurazione e gestisce eventuali errori."""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"FATAL: Configuration file '{config_file}' not found.")
        exit(1)
    except json.JSONDecodeError:
        print(f"FATAL: Error decoding JSON from '{config_file}'.")
        exit(1)

def main():
    """Punto di ingresso principale per la console RAG."""
    
    config = load_config(CONFIG_FILE)
    db_manager = VectorDB(DB_PATH, CONFIG_FILE)

    # --- Inizializzazione dello Stato ---
    context_settings = config.get("context_settings", {})
    is_context_enabled = context_settings.get("context_enabled_by_default", True)
    current_context = "default"
    session_settings = {} # Dizionario per le impostazioni di sessione

    print("\n--- RAG Interactive Console ---")
    print("Type your question and press Enter. For a list of commands, type !help.")
    print("-----------------------------\n")

    # Loop principale della console
    while True:
        try:
            prompt_tag = f"(RAG: {current_context})"
            if not is_context_enabled:
                prompt_tag = f"(RAG: {current_context} [no-context])"
            
            user_input = input(f"{prompt_tag} > ").strip()

            if not user_input:
                continue

            if user_input.startswith('!'):
                parts = user_input.split()
                command = parts[0]
                args = parts[1:]

                if command == '!quit':
                    break
                elif command == '!help':
                    command_handler.handle_help()
                elif command == '!status':
                    command_handler.handle_status(db_manager)
                elif command == '!reindex':
                    command_handler.handle_reindex(db_manager)
                elif command == '!purge':
                    command_handler.handle_purge(db_manager)
                elif command == '!reindex-file':
                    file_path = " ".join(args) if args else None
                    command_handler.handle_reindex_file(db_manager, file_path)
                elif command == '!context-on':
                    is_context_enabled = command_handler.handle_context_on()
                elif command == '!context-off':
                    is_context_enabled = command_handler.handle_context_off()
                elif command == '!context-list':
                    command_handler.handle_context_list(db_manager)
                elif command == '!context-new':
                    new_ctx = command_handler.handle_context_new(db_manager, args[0] if args else None)
                    if new_ctx: current_context = new_ctx
                elif command == '!context-switch':
                    new_ctx = command_handler.handle_context_switch(db_manager, args[0] if args else None)
                    if new_ctx: current_context = new_ctx
                elif command == '!context-delete':
                    command_handler.handle_context_delete(db_manager, args[0] if args else None, current_context)
                # --- NUOVO COMANDO ---
                elif command == '!settings':
                    command_handler.handle_setting_set(session_settings, args)
                else:
                    print(f"Unknown command: '{command}'. Type !help for available commands.")
            
            # Se non è un comando, è una domanda per l'LLM
            else:
                question = user_input
                print("\nSearching for relevant context in the database...")
                
                rag_chunks = db_manager.find_relevant_chunks(question)
                rag_context_str = "\n---\n".join(rag_chunks) if rag_chunks else "No relevant code snippets found in the database."
                
                history = []
                if is_context_enabled:
                    print("Context history is ENABLED. Retrieving conversation...")
                    max_len = context_settings.get("max_history_length", 10)
                    history = db_manager.get_context_history(current_context, limit=max_len)
                else:
                    print("Context history is DISABLED. This will be a one-shot question.")

                print("Context found. Sending to LLM...\n")
                
                # --- LOGICA DI STREAMING APPLICATA ---
                full_response = []
                print("--- Answer from LLM ---")
                
                # Passa anche session_settings al client LLM
                token_generator = ask_local_llm(history, rag_context_str, question, session_settings, CONFIG_FILE)
                
                for token in token_generator:
                    print(token, end='', flush=True)
                    full_response.append(token)
                
                final_answer = "".join(full_response)
                print("\n-----------------------\n")

                if is_context_enabled:
                    db_manager.add_message_to_context(current_context, 'user', question)
                    db_manager.add_message_to_context(current_context, 'assistant', final_answer)

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}\n")

    print("\nShutting down. Goodbye!")
    db_manager.close()

if __name__ == '__main__':
    main()