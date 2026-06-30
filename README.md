# LangChain MCP Sample (Hugging Face + GitHub Models + Ollama)

A minimal Python sample project that includes:
- A LangChain app with provider switch (`huggingface`, `github`, or `ollama`)
- A sample MCP server with two tools
- A local RAG pipeline (sensitive file -> Chroma vector DB -> top-k retrieval)
- Tests and VS Code tasks/launch configs

## 1) Prerequisites

- Python 3.11+
- VS Code + Python extension
- Optional for local model: Ollama installed and running
- Optional for cloud model: Hugging Face token

## 2) Setup

### Windows PowerShell

```powershell
cd C:\Users\amitesh.kumar.singh\Documents\VSSWorkspace\langchain-mcp-sample
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
Copy-Item .env.example .env
```

### WSL / Linux

```bash
cd ~/.../langchain-mcp-sample
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .[dev]
cp .env.example .env
```

## 3) Configure LLM Provider

Edit `.env`:

- Hugging Face mode
  - `LLM_PROVIDER=huggingface`
  - `HF_API_KEY=<your token>`
  - `HF_MODEL=<model id>`
- GitHub Models mode
  - `LLM_PROVIDER=github`
  - `GITHUB_TOKEN=<your token>`
  - `GITHUB_BASE_URL=https://models.github.ai/inference`
  - `GITHUB_MODEL=meta/Llama-4-Scout-17B-16E-Instruct`
- Ollama mode
  - `LLM_PROVIDER=ollama`
  - `OLLAMA_MODEL=qwen2.5:3b-instruct`

## 4) Run

### Build RAG index from sensitive file

1. Put your sensitive content in `data/sensitive.txt` (or set `RAG_SOURCE_FILE` in `.env`).
2. Build the vector DB index:

```bash
cd /mnt/c/Users/amitesh.kumar.singh/Documents/VSSWorkspace/langchain-mcp-sample
source .venv/bin/activate
PYTHONPATH=src python -m app.index_rag
```

This writes embeddings to `RAG_DB_DIR` (default: `data/vector_db`).

### Run tests

```powershell
$env:PYTHONPATH='src'; python -m pytest -q
```

### Run LangChain demo

```powershell
$env:PYTHONPATH='src'; python -m app.main
```

`app.main` now runs this chain:
1. Calls MCP tool `explain_text_tool` with input text (default: `Hello World`).
2. Uses MCP output as the RAG query.
3. Retrieves top-k relevant chunks from the vector DB.
4. Sends only the question + retrieved chunks to the LLM.

### Run LangChain demo in WSL with live terminal logs

Use unbuffered output so logs appear directly on the terminal screen:

```bash
cd /mnt/c/Users/amitesh.kumar.singh/Documents/VSSWorkspace/langchain-mcp-sample
source .venv/bin/activate
export PYTHONPATH=src
export PYTHONUNBUFFERED=1
stdbuf -oL -eL python -u -m app.main
```

Optional safety timeout:

```bash
timeout 180s stdbuf -oL -eL python -u -m app.main; echo EXIT_CODE:$?
```

If `stdbuf` is unavailable:

```bash
python -u -m app.main
```

Correct quoting for quick one-liners in WSL:

```bash
python -c 'from app.config import load_settings; s=load_settings(); print(s.provider)'
```

### Run MCP server (streamable HTTP)

```bash
cd /mnt/c/Users/amitesh.kumar.singh/Documents/VSSWorkspace/langchain-mcp-sample
source .venv/bin/activate
PYTHONPATH=src python -m mcp_server.server
```

When the server starts, it will expose the MCP endpoint at `http://127.0.0.1:8000/mcp`.

If you want the sample client and agent to connect to this standalone server, set:

```bash
export MCP_SERVER_URL=http://127.0.0.1:8000/mcp
```

### Run MCP client demo (end-to-end tool calls)

```bash
cd /mnt/c/Users/amitesh.kumar.singh/Documents/VSSWorkspace/langchain-mcp-sample
source .venv/bin/activate
PYTHONPATH=src python -m app.mcp_client_demo
```

### Run LangChain + MCP agent demo (single-command orchestration)

```bash
cd /mnt/c/Users/amitesh.kumar.singh/Documents/VSSWorkspace/langchain-mcp-sample
source .venv/bin/activate
PYTHONPATH=src python -m app.agent_mcp_demo --question "What time is it in UTC, and what is 14.5 + 10.5?"
```

If you use Hugging Face, set `HF_API_KEY` in `.env` first.

If you use Ollama, ensure it is running and model is available:

```bash
ollama serve
ollama pull qwen2.5:3b-instruct
```

## 5) Connect MCP to VS Code / Copilot Chat

This workspace includes `.vscode/mcp.json` with a sample stdio MCP server registration.
After opening this folder in VS Code, MCP-capable clients can discover tool endpoints from that file.

## 6) Notes

- Free Hugging Face usage is quota-limited.
- Ollama is fully local and free, but model quality/speed depends on hardware.
- Start with smaller models for this machine profile.
