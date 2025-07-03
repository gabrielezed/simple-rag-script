# simple-rag-script

An interactive console to chat with your local codebase using local LLMs.

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
  * **Modular Architecture:** Core logic is separated into specialized modules for easy maintenance and extension.
  * **Fully Configurable:** Centralized `config.json` file to manage all important parameters, including prompts, temperature, and embedding settings.
  * **Dual Embedding Modes:** Choose between a fast, local `sentence-transformers` model or using your LM Studio server's embedding endpoint.
  * **Powerful Commands:** Includes commands like `!reindex`, `!purge`, and `!status` for full control over the knowledge base.

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
```

### 3\. Configure your Local LLM

1.  Open **LM Studio**.
2.  Download a model of your choice from the **Discover** tab. An instruction-tuned model is recommended.
3.  Go to the **Local Server** tab (`<->` icon).
4.  Select your downloaded model at the top.
5.  Click **Start Server**.

### 4\. Configure the Script

Edit the `config.json` file to match your setup and preferences. See the section below for a detailed explanation of all parameters.

### 5\. First Run

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

The `config.json` file is the control center for the application. It allows you to change a wide range of parameters without modifying the Python code.

```json
{
  "embedding_settings": {
    "mode": "api",
    "local_model": "all-MiniLM-L6-v2",
    "top_k_chunks": 7
  },
  "llm_settings": {
    "server_url": "http://localhost:1234/v1",
    "chat_model_name": "local-model",
    "temperature": 0.4,
    "system_prompt": "You are a senior C software architect. Your answers must be in English, be comprehensive, and explain the 'why' behind the code.",
    "master_prompt_template": "As a senior software architect, analyze the following CODE SNIPPETS to answer the user's QUESTION. Synthesize information from all snippets to form a complete, high-level answer. If the snippets seem incomplete, infer the overall purpose based on function names, comments, and file structure. Provide the best possible architectural explanation based on the available evidence.\n\nCODE SNIPPETS:\n---\n{context}\n---\n\nQUESTION: {question}"
  }
}
```

### `embedding_settings`

This section controls how the script generates vector embeddings.

  * `"mode"`: Sets the embedding method.
      * `"api"`: (Default) Uses the embedding endpoint of your LM Studio server. This ensures **no external internet connection** is ever made, but it is **slower** during indexing.
      * `"local"`: Uses a dedicated, highly-optimized `sentence-transformers` model. This is **much faster** for indexing but requires a **one-time download** of the model from Hugging Face.
  * `"local_model"`: The name of the `sentence-transformers` model to use when `mode` is set to `"local"`.
  * `"top_k_chunks"`: The number of relevant text chunks to retrieve from the database and use as context for the LLM.

### `llm_settings`

This section controls the interaction with the Large Language Model.

  * `"server_url"`: The address of your LM Studio server.
  * `"chat_model_name"`: A name passed to the API. For LM Studio, this is not critical as the model is selected in the UI.
  * `"temperature"`: Controls the randomness of the LLM's response. Lower values (e.g., `0.2`) produce more deterministic and focused answers. Higher values (e.g., `0.8`) produce more creative ones.
  * `"system_prompt"`: The core instruction that defines the LLM's persona and overall goal (e.g., "You are an expert C code assistant").
  * `"master_prompt_template"`: The most powerful setting. This is the template used to construct the final prompt sent to the LLM. The script will replace `{context}` with the retrieved code snippets and `{question}` with the user's question. You can modify this to change how the LLM is instructed to reason and answer.

-----

## Console Commands

The application is controlled via a series of special commands that begin with `!`. Here is a complete list of their functions.

| Command          | Arguments | Description                                                                                                                 |
| :--------------- | :-------- | :-------------------------------------------------------------------------------------------------------------------------- |
| **`!help`** | *None* | Displays the help message with a list of all available commands.                                                            |
| **`!reindex`** | *None* | Starts a full, forced re-indexing of all files within the `codebase` directory, ignoring any files specified in `.ragignore`. |
| **`!reindex-file`**| `<path>`  | Forces the re-indexing of a single specified file. The path should be relative to the project root (e.g., `codebase/vss.c`).  |
| **`!status`** | *None* | Shows a quick status, indicating how many files are currently indexed in the database.                                        |
| **`!purge`** | *None* | **Destructive action.** Permanently deletes all data from the embedding database. It will ask for a `(Y/N)` confirmation before proceeding. |
| **`!quit`** | *None* | Exits the application cleanly.                                                                                              |

Any input that does not start with `!` is interpreted as a question to be asked to the codebase.
