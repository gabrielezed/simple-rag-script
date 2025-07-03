# modules/llm_client.py

import json
import requests

def ask_local_llm(history, rag_context, question, config_path='config.json'):
    """
    Invia una domanda, il contesto RAG e la cronologia della conversazione
    al server LLM locale.
    """
    # Carica l'intera sezione di configurazione dell'LLM
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        settings = config.get("llm_settings", {})
        url = settings.get("server_url")
        model_name = settings.get("chat_model_name")
        temperature = settings.get("temperature", 0.7)
        system_prompt = settings.get("system_prompt", "You are a helpful assistant.")
        master_template = settings.get("master_prompt_template", "{context}\n\n{question}")

        if not url:
            raise ValueError("Config error: 'server_url' is missing in llm_settings.")
        
        if not url.endswith('/chat/completions'):
            url = f"{url.rstrip('/')}/chat/completions"

    except Exception as e:
        return f"Error processing configuration file: {e}"

    headers = { "Content-Type": "application/json" }

    final_user_prompt = master_template.replace("{context}", rag_context).replace("{question}", question)

    messages_payload = [
        {"role": "system", "content": system_prompt}
    ]
    messages_payload.extend(history)
    messages_payload.append({"role": "user", "content": final_user_prompt})

    data = {
        "model": model_name,
        "messages": messages_payload,
        "temperature": temperature,
    }

    try:
        # --- FIX APPLICATO: Aggiunto timeout alla richiesta ---
        # 5 secondi per la connessione, 300 secondi (5 min) per la risposta
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=(5, 300))
        response.raise_for_status()
        response_json = response.json()
        return response_json['choices'][0]['message']['content']

    except requests.exceptions.Timeout:
        return "Connection to LLM server timed out. The server might be busy or unresponsive."
    except requests.exceptions.RequestException as e:
        return f"Connection error to LLM server at {url}: {e}\nEnsure the server is running."
    except (KeyError, IndexError) as e:
        return f"Unexpected response format from LLM server: {response.text}"