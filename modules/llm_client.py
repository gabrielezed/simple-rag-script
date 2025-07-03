# modules/llm_client.py

import json
import requests

def ask_local_llm(history, rag_context, question, session_settings, config_path='config.json'):
    """
    Invia una domanda, il contesto RAG e la cronologia al server LLM locale
    e restituisce la risposta come un generatore di token (streaming).
    Applica le impostazioni di sessione che hanno la precedenza su config.json.
    """
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        llm_config = config.get("llm_settings", {})
        
        # --- LOGICA DI OVERRIDE ---
        # Le impostazioni di sessione hanno la precedenza su quelle del file di configurazione.
        temperature = session_settings.get("temperature", llm_config.get("temperature", 0.7))
        system_prompt = session_settings.get("system_prompt", llm_config.get("system_prompt", "You are a helpful assistant."))
        master_template = session_settings.get("master_prompt_template", llm_config.get("master_prompt_template", "{context}\n\n{question}"))
        
        # Impostazioni che non vengono modificate a runtime
        url = llm_config.get("server_url")
        model_name = llm_config.get("chat_model_name")

        if not url:
            raise ValueError("Config error: 'server_url' is missing in llm_settings.")
        
        if not url.endswith('/chat/completions'):
            url = f"{url.rstrip('/')}/chat/completions"

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        yield f"Error processing configuration file: {e}"
        return

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
        "temperature": float(temperature), # Assicura che la temperatura sia un float
        "stream": True
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data), timeout=(5, 300), stream=True)
        response.raise_for_status()

        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data: '):
                    json_str = decoded_line[len('data: '):]
                    if json_str.strip() == '[DONE]':
                        break
                    
                    try:
                        chunk = json.loads(json_str)
                        token = chunk.get('choices', [{}])[0].get('delta', {}).get('content', '')
                        if token:
                            yield token
                    except json.JSONDecodeError:
                        continue

    except requests.exceptions.Timeout:
        yield "Connection to LLM server timed out."
    except requests.exceptions.RequestException as e:
        yield f"Connection error to LLM server: {e}"