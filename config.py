"""Central configuration for the Job Hunting AI Agent.

Every path, model name and tuning constant lives here so the rest of the
codebase never hardcodes them. Values can be overridden with environment
variables (see .env.example).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --- Paths -----------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = Path(os.getenv("DOCS_DIR", BASE_DIR / "docs"))
OFFERS_FILE = Path(os.getenv("OFFERS_FILE", DOCS_DIR / "jobs.xlsx"))
SERVER_SCRIPT = BASE_DIR / "server.py"
STATIC_DIR = BASE_DIR / "static"

# --- Vector store ----------------------------------------------------------

CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "my_docs")
CHROMA_PATH = Path(os.getenv("CHROMA_PATH", BASE_DIR / "chroma_db"))
# When CHROMA_HOST is set (docker-compose, k8s) the client talks to a Chroma
# server instead of using the embedded on-disk store.
CHROMA_HOST = os.getenv("CHROMA_HOST")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))

# --- Retrieval -------------------------------------------------------------

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "250"))  # words per chunk
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))  # words shared between chunks
N_RESULTS = int(os.getenv("N_RESULTS", "3"))  # chunks retrieved per query

# --- Model ---------------------------------------------------------------

MODEL = os.getenv("MODEL", "claude-haiku-5-5")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))
MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", "5"))
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))

SYSTEM_PROMPT = """You are a job hunting assistant for a single user.

You have two sources of information:
1. Context from the user's CV and personal documents, retrieved automatically
   and included in the user's message under "CV context".
2. Tools that read the user's saved job offers from a spreadsheet. Call them
   whenever the question touches job offers, companies or roles.

Rules:
- Answer only from the CV context and the tool results. If the information is
  not there, say so plainly instead of guessing.
- When you compare the user's profile against an offer, be specific: name the
  skills that match and the ones that are missing.
- Be concise and practical. The user is preparing real job applications.
- Answer in the language the user writes in.
"""


def get_collection():
    """Return the Chroma collection, embedded or remote depending on config.

    Imported lazily so that the MCP server (which never touches the vector
    store) does not pay the chromadb import cost.
    """
    import chromadb

    if CHROMA_HOST:
        client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    else:
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    return client.get_or_create_collection(name=CHROMA_COLLECTION)
