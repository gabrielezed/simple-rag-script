# rag_script.py

import json
import os
import argparse

# Prova a importare readline per la cronologia dei comandi nella console
try:
    import readline
except ImportError:
    print("Info: 'readline' module not available. Command history will not be saved.")

# --- Importazioni dei nuovi manager e moduli ---
from modules.embedding_manager import EmbeddingManager
from modules.history_manager import ChatHistoryManager
from modules.llm_client import ask_local_llm
from modules import command_handler
from modules.terminal_colors import Colors

# --- Costanti di Configurazione ---
CONFIG_FILE = 'config.json'
DB_PATH = 'rag_database.db'

def load_config(config_file):
    """Loads the configuration file and handles potential errors."""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"{Colors.RED}FATAL: Configuration file '{config_file}' not found.{Colors.RESET}")
        exit(1)
    except json.JSONDecodeError:
        print(f"{Colors.RED}FATAL: Error decoding JSON from '{config_file}'.{Colors.RESET}")
        exit(1)

def main():
    """Main entry point for the RAG console."""
    
    config = load_config(CONFIG_FILE)
    
    # --- Inizializzazione dei nuovi manager ---
    try:
        embedding_manager = EmbeddingManager(DB_PATH, config)
        history_manager = ChatHistoryManager(DB_PATH)
    except Exception as e:
        print(f"{Colors.RED}FATAL: Could not initialize managers. Error: {e}{Colors.RESET}")
        exit(1)

    # --- Inizializzazione dello Stato ---
    context_settings = config.get("context_settings", {})
    is_context_enabled = context_settings.get("context_enabled_by_default", True)
    current_context = "default"
    session_settings = {} # Dizionario per le impostazioni di sessione

    print(f"\n{Colors.GREEN}--- RAG Interactive Console ---{Colors.RESET}")
    print("Type your question and press Enter. For a list of commands, type !help.")
    print(f"{Colors.GREEN}-----------------------------{Colors.RESET}\n")

    # Loop principale della console
    while True:
        try:
            prompt_tag = f"{Colors.BLUE}(RAG: {current_context}){Colors.RESET}"
            if not is_context_enabled:
                prompt_tag = f"{Colors.YELLOW}(RAG: {current_context} [no-context]){Colors.RESET}"
            
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
                    command_handler.handle_status(embedding_manager)
                elif command == '!reindex':
                    command_handler.handle_reindex(embedding_manager)
                elif command == '!purge':
                    command_handler.handle_purge(embedding_manager, history_manager)
                elif command == '!reindex-file':
                    file_path = " ".join(args) if args else None
                    command_handler.handle_reindex_file(embedding_manager, file_path)
                elif command == '!context-on':
                    is_context_enabled = command_handler.handle_context_on()
                elif command == '!context-off':
                    is_context_enabled = command_handler.handle_context_off()
                elif command == '!context-list':
                    command_handler.handle_context_list(history_manager)
                elif command == '!context-new':
                    new_ctx = command_handler.handle_context_new(history_manager, args[0] if args else None)
                    if new_ctx: current_context = new_ctx
                elif command == '!context-switch':
                    new_ctx = command_handler.handle_context_switch(history_manager, args[0] if args else None)
                    if new_ctx: current_context = new_ctx
                elif command == '!context-clear':
                    command_handler.handle_context_clear(history_manager, current_context)
                elif command == '!context-delete':
                    command_handler.handle_context_delete(history_manager, args[0] if args else None, current_context)
                elif command == '!settings':
                    command_handler.handle_setting_set(session_settings, args)
                else:
                    print(f"{Colors.RED}Unknown command: '{command}'. Type !help for available commands.{Colors.RESET}")
            
            # Se non è un comando, è una domanda per l'LLM
            else:
                question = user_input
                print(f"\n{Colors.BLUE}Searching for relevant context in the database...{Colors.RESET}")
                
                rag_chunks = embedding_manager.find_relevant_chunks(question)
                rag_context_str = "\n---\n".join(rag_chunks) if rag_chunks else "No relevant code snippets found in the database."
                
                history = []
                if is_context_enabled:
                    print(f"{Colors.BLUE}Context history is ENABLED. Retrieving conversation...{Colors.RESET}")
                    max_len = context_settings.get("max_history_length", 10)
                    history = history_manager.get_context_history(current_context, limit=max_len)
                else:
                    print(f"{Colors.YELLOW}Context history is DISABLED. This will be a one-shot question.{Colors.RESET}")

                print(f"{Colors.BLUE}Context found. Sending to LLM...{Colors.RESET}\n")
                
                full_response = []
                print(f"{Colors.GREEN}--- Answer from LLM ---{Colors.RESET}")
                
                token_generator = ask_local_llm(history, rag_context_str, question, session_settings, CONFIG_FILE)
                
                for token in token_generator:
                    print(token, end='', flush=True)
                    full_response.append(token)
                
                final_answer = "".join(full_response)
                print(f"\n{Colors.GREEN}-----------------------\n{Colors.RESET}")

                if is_context_enabled:
                    history_manager.add_message_to_context(current_context, 'user', question)
                    history_manager.add_message_to_context(current_context, 'assistant', final_answer)

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            print(f"\n{Colors.RED}An unexpected error occurred: {e}{Colors.RESET}\n")

    print("\nShutting down. Goodbye!")
    embedding_manager.close()
    history_manager.close()

if __name__ == '__main__':
    main()