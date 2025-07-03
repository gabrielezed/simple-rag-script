# modules/llm_client.py

import json
import requests

def ask_local_llm(question, context, config_path='config.json'):
    """
    Invia una domanda e il contesto al server LLM locale, usando i parametri
    avanzati specificati nel file di configurazione.
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
        
        # Aggiunge /chat/completions se non presente per compatibilità
        if not url.endswith('/chat/completions'):
            url = f"{url.rstrip('/')}/chat/completions"

    except Exception as e:
        return f"Error processing configuration file: {e}"

    headers = { "Content-Type": "application/json" }

    # Costruisci il prompt finale usando il template dal file di configurazione
    final_prompt = master_template.replace("{context}", context).replace("{question}", question)

    data = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": final_prompt}
        ],
        "temperature": temperature,
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        response_json = response.json()
        return response_json['choices'][0]['message']['content']

    except requests.exceptions.RequestException as e:
        return f"Connection error to LLM server at {url}: {e}\nEnsure the server is running."
    except (KeyError, IndexError) as e:
        return f"Unexpected response format from LLM server: {response.text}"