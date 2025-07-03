# rag_script.py

import json
# Prova a importare readline, ma non bloccare l'esecuzione se non è disponibile (es. su Windows)
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

def main():
    """Punto di ingresso principale per la console RAG."""
    
    # Inizializza il gestore del database, che leggerà la sua configurazione
    db_manager = VectorDB(DB_PATH, CONFIG_FILE)

    print("\n--- RAG Interactive Console ---")
    print("Type your question and press Enter. For a list of commands, type !help.")
    print("-----------------------------\n")

    # Loop principale della console
    while True:
        try:
            user_input = input("(RAG) > ").strip()

            if not user_input:
                continue

            # Gestione dei comandi speciali
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
                    file_path = args[0] if args else None
                    command_handler.handle_reindex_file(db_manager, file_path)
                else:
                    print(f"Unknown command: '{command}'. Type !help for available commands.")
            
            # Se non è un comando, è una domanda per l'LLM
            else:
                question = user_input
                print("\nSearching for relevant context in the database...")
                
                context_chunks = db_manager.find_relevant_chunks(question)
                
                if not context_chunks:
                    print("Could not find relevant context for your question. The LLM will answer without it.\n")
                    context_str = "No context found."
                else:
                    context_str = "\n---\n".join(context_chunks)
                    print("Context found. Sending to LLM...\n")
                
                answer = ask_local_llm(question, context_str, CONFIG_FILE)
                
                print("--- Answer from LLM ---")
                print(answer)
                print("-----------------------\n")

        except (KeyboardInterrupt, EOFError):
            break
        except Exception as e:
            print(f"\nAn unexpected error occurred: {e}\n")

    print("\nShutting down. Goodbye!")
    db_manager.close()

if __name__ == '__main__':
    main()