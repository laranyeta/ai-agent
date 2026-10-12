# Job Hunting AI Agent

A personal assistant that answers questions about my CV and the job offers I am
tracking. The CV is retrieved with **RAG**; the offers are reached through an
**MCP server** that the model calls as tools.

Built with the Claude API, ChromaDB, LlamaIndex, LangChain, MCP and FastAPI.

---

## Architecture

```
                   ┌──────────────────────────────┐
  browser  ───────▶│  FastAPI  (app.py)           │
  or CLI           │  chat UI + /api/chat         │
                   └───────────────┬──────────────┘
                                   │
                   ┌───────────────▼──────────────┐
                   │  Agent  (agent.py)           │
                   │  RAG + tool-calling loop     │
                   └───┬───────────────────────┬──┘
                       │                       │
         retrieval ◀───┘                       └───▶ tool calls
                       │                       │
          ┌────────────▼──────────┐   ┌────────▼─────────────┐
          │  ChromaDB             │   │  MCP server          │
          │  CV chunks (index.py) │   │  (server.py, stdio)  │
          └───────────────────────┘   │  get_offers          │
                                      │  get_keyword         │
                                      │  count_keyword       │
                                      └────────┬─────────────┘
                                               │
                                      ┌────────▼─────────┐
                                      │  jobs.xlsx       │
                                      └──────────────────┘
```

**One question, end to end:**

1. The question is embedded and the closest CV chunks come back from Chroma.
2. Claude receives the question, the CV context and the MCP tool schemas.
3. If the question touches the offers, Claude calls one or more tools. The
   agent runs them through the MCP server and sends the results back.
4. Claude answers from the CV context and the tool results.

The offers are **not** stuffed into the prompt. They are fetched on demand, so
the prompt stays the same size whether the spreadsheet holds 5 offers or 5,000.

---

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then add your ANTHROPIC_API_KEY
```

Put your documents in `docs/`:

- `docs/cv.txt` — the CV (any `.txt` or `.md` file in the folder is indexed)
- `docs/jobs.xlsx` — the offers, with columns **Puesto | Empresa | Descripción**

Index the CV once (re-run it whenever the documents change):

```bash
python index.py
```

## Run

```bash
python app.py       # web chat at http://localhost:8000
python chat.py      # the same agent, in the terminal
```

With Docker:

```bash
docker compose up --build
```

## API

| Method | Path          | Purpose                                      |
| ------ | ------------- | -------------------------------------------- |
| GET    | `/`           | chat interface                               |
| GET    | `/health`     | liveness probe and loaded tools              |
| GET    | `/api/tools`  | the MCP tool schemas currently in use        |
| POST   | `/api/chat`   | `{"message": "...", "session_id": "..."}`    |
| POST   | `/api/reset`  | `{"session_id": "..."}` clears a conversation |

```bash
curl -X POST localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"message": "Which offers need GraphQL?"}'
```

## Using the MCP server from another client

`server.py` is a standard MCP server, so any MCP client can use it. For Claude
Desktop, add this to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "job-offers": {
      "command": "python",
      "args": ["/absolute/path/to/server.py"]
    }
  }
}
```

That is the point of using MCP rather than plain functions: the same server
works unchanged in this agent, in Claude Desktop, or in any other host.

---

## Files

| File            | Role                                                       |
| --------------- | ---------------------------------------------------------- |
| `config.py`     | every path, model name and constant, overridable via env    |
| `index.py`      | LlamaIndex pipeline: load, split into overlapping chunks, store in Chroma |
| `server.py`     | MCP server over the offers spreadsheet                      |
| `agent.py`      | RAG retrieval + the Claude tool-calling loop                |
| `app.py`        | FastAPI: chat API and static interface                      |
| `chat.py`       | terminal chat                                               |
| `static/`       | the chat interface (one HTML file, no build step)           |
| `rag.py`        | retrieval-only baseline as a LangChain (LCEL) chain         |
| `api_script.py` | REST consumption example with retries and backoff           |
| `main.py`       | smoke test for the API key and model                        |

## Configuration

Everything in `.env` (see `.env.example`). The ones worth knowing:

| Variable        | Default            | Notes                                         |
| --------------- | ------------------ | --------------------------------------------- |
| `MODEL`         | `claude-haiku-5-5` | any Claude model id                           |
| `CHUNK_SIZE`    | `250`              | tokens per chunk                              |
| `CHUNK_OVERLAP` | `50`               | tokens shared between consecutive chunks      |
| `N_RESULTS`     | `3`                | CV chunks retrieved per question               |
| `CHROMA_HOST`   | unset              | set it to use a Chroma server instead of disk |

## Design notes

- **Chunk overlap.** A CV bullet that straddles a chunk boundary would be
  unretrievable without it, and a single bullet often carries the whole answer.
- **LlamaIndex and embeddings.** `index.py` wraps Chroma's default embedding
  function as a LlamaIndex embed model, so documents and the agent's queries
  share one vector space. Chunk ids are stable, so re-indexing overwrites.
- **Embeddings.** Chroma's default model, which is enough for a handful of
  short documents. A larger corpus would want an explicit model and reranking.
- **Tools over context stuffing.** See the architecture note above.
- **History.** Kept in memory per session and trimmed to the last
  `MAX_HISTORY_MESSAGES`, never splitting a `tool_use` from its `tool_result`.
  A real deployment would move this to Redis or Postgres.
- **stdio and stdout.** The MCP server logs through `logging` (stderr) only.
  Anything printed to stdout would corrupt the JSON-RPC stream.

## Known limits

- Sessions are in-process, so they are lost on restart and not shared between
  replicas.
- Answers are not evaluated automatically. The next step is a small set of
  questions with expected answers, to catch retrieval regressions.
- Keyword search in `get_keyword` is a literal substring match, not semantic,
  so "k8s" will not find "Kubernetes".
