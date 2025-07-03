# simple-rag-script

An interactive "console" to chat with your local codebase using local LLMs.

## Table of Contents
- [About The Project](#about-the-project)
- [Features](#features)
- [Getting Started](#getting-started)
- [Configuration (`config.json`)](#configuration-configjson)
- [Console Commands](#console-commands)

-----

## About The Project

This project provides an interactive console application that leverages a Retrieval-Augmented Generation (RAG) architecture to answer questions about a local codebase. It uses a vector database to store embeddings of the source code and queries a local Large Language Model (like one running in LM Studio) to generate intelligent, context-aware answers.

-----

## Features

  * **Interactive Console:** A user-friendly command-line interface for asking questions and managing the database.
  * **Persistent Conversational Context:** Remembers your conversation history in named sessions, allowing for multi-turn dialogue and follow-up questions.
  * **Modular Architecture:** Core logic is separated into specialized modules for easy maintenance and extension.
  * **Fully Configurable:** Centralized `config.json` file to manage all important parameters, including prompts, temperature, and embedding settings.
  * **Dual Embedding Modes:** Choose between a fast, local `sentence-transformers` model or using your LM Studio server's embedding endpoint.
  * **Control Commands:** Includes commands like `!reindex`, `!purge`, and `!status` for full control over the knowledge base.

-----

## Getting Started

To get a local copy up and running, follow these simple steps.

### 1\. Prerequisites

  * **Python 3.8+** installed on your system.
  * **LM Studio:** Download and install from [lmstudio.ai](https://lmstudio.ai/).

### 2\. Installation & Setup

```sh
# 1. Clone the repo
git clone https://github.com/gabrielezed/simple-rag-script.git
cd simple-rag-script

# 2. Create and activate a virtual environment
python -m venv .venv
source venv/bin/activate  # On Windows: .\.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
````

### 3\. Add Your Codebase

Place all the source code files you want to chat with inside the `codebase` directory at the root of the project. If this directory doesn't exist, create it. The script will recursively scan this folder to build its knowledge base.

### 4\. Configure your Local LLM

For the script to function correctly, especially with `embedding_settings.mode` set to `"api"`, you need to load two types of models in LM Studio:

* **A Chat Model:** This is the main model that generates answers and converses with you (e.g., *Qwen*, *Llama 3 Instruct*, *Mistral Instruct*).
* **An Embedding Model:** This model specializes in converting text into numerical vectors. It's essential for the script to find relevant code snippets. A popular choice is *nomic-embed-text*.

**To set them up:**

1.  Open **LM Studio** and go to the **Local Server** tab (`>_` icon).
2.  In the **Select a model to load** dropdown at the top, choose your preferred **Chat Model**.
3.  In the **Select an embedding model** dropdown (usually located on the right panel), choose your **Embedding Model**.
4.  Click **Start Server**.

### 5\. Configure the Script

Edit the `config.json` file to match your setup and preferences. See the section below for a detailed explanation of all parameters.

### 6\. First Run

1.  Run the console application:
    ```sh
    python rag_script.py
    ```
2.  The first time you run it, you must index your codebase. Type the following command and press Enter:
    ```
    !reindex
    ```
3.  Once indexing is complete, you can start asking questions about your code\!

-----

## Configuration (`config.json`)

The `config.json` file is the control center for the application.

```json
{
  "embedding_settings": {
    "mode": "api",
    "local_model": "all-MiniLM-L6-v2",
    "top_k_chunks": 5
  },
  "llm_settings": {
    "server_url": "http://localhost:1234/v1",
    "chat_model_name": "local-model",
    "temperature": 0.4,
    "system_prompt": "You are a senior C software architect...",
    "master_prompt_template": "As a senior software architect, analyze..."
  },
  "context_settings": {
    "max_history_length": 10,
    "context_enabled_by_default": true
  }
}
```

### `embedding_settings`

This section controls how the script generates vector embeddings.

  * `"mode"`: Sets the embedding method.
      * `"api"`: (Default) Uses the embedding endpoint of your LM Studio server. This is slower but ensures no external internet connection is ever made.
      * `"local"`: Uses a dedicated, highly-optimized `sentence-transformers` model. This is much faster for indexing but requires a one-time download of the model from Hugging Face.
  * `"local_model"`: The name of the `sentence-transformers` model to use when `mode` is set to `"local"`.
  * `"top_k_chunks"`: The number of relevant text chunks to retrieve from the database and use as context for the LLM.

### `llm_settings`

This section controls the interaction with the Large Language Model.

  * `"server_url"`: The address of your LM Studio server.
  * `"chat_model_name"`: A name passed to the API.
  * `"temperature"`: Controls the randomness of the LLM's response. Lower values (e.g., `0.2`) are more deterministic; higher values (e.g., `0.8`) are more creative.
  * `"system_prompt"`: The core instruction that defines the LLM's persona and overall goal.
  * `"master_prompt_template"`: The template used to construct the final prompt sent to the LLM. The script will replace `{context}` with the retrieved code snippets and `{question}` with the user's question.

### `context_settings`

This section controls the new conversational memory feature.

  * `"max_history_length"`: The maximum number of messages (user questions + assistant answers) to keep in the conversation history. This creates a "sliding window" of memory.
  * `"context_enabled_by_default"`: Set to `true` if you want conversation history to be active by default when the script starts, or `false` for it to be off by default.

-----

## Console Commands

The application is controlled via a series of special commands that begin with `!`.

### Database and Indexing Commands

| Command          | Arguments | Description                                                                                                                 |
| :--------------- | :-------- | :-------------------------------------------------------------------------------------------------------------------------- |
| **`!help`** | *None* | Displays the help message with a list of all available commands.                                                            |
| **`!reindex`** | *None* | Starts a full, forced re-indexing of all files within the `codebase` directory. |
| **`!reindex-file`**| `<path>`  | Forces the re-indexing of a single specified file. Handles paths with spaces.  |
| **`!status`** | *None* | Shows how many files are currently indexed in the database.                                        |
| **`!purge`** | *None* | **Destructive.** Permanently deletes all indexed data and all conversation history. Asks for confirmation. |
| **`!quit`** | *None* | Exits the application cleanly.                                                                                              |

### Context Management Commands

These commands allow you to control the conversational memory.

| Command | Arguments | Description |
| :--- | :--- | :--- |
| **`!context-on`** | *None* | Enables conversation history. The LLM will remember previous turns. |
| **`!context-off`**| *None* | Disables conversation history. Each question is treated as a one-shot query. |
| **`!context-list`**| *None* | Shows a list of all saved conversation contexts. |
| **`!context-new`**| `<name>` | Creates and switches to a new, empty conversation context. |
| **`!context-switch`**| `<name>` | Switches to a previously created conversation context. |
| **`!context-delete`**| `<name>` | **Destructive.** Permanently deletes a conversation context and its entire history. Asks for confirmation. |

Any input that does not start with `!` is interpreted as a question to be asked to the codebase.
