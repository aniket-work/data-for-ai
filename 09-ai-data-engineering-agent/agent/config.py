"""Where the model lives. Any OpenAI-compatible server works: llama.cpp, Ollama, LM Studio, vLLM, oMLX ...

    DATA_AGENT_BASE_URL   default http://localhost:8998/v1
    DATA_AGENT_MODEL      default: the first model the server lists
    DATA_AGENT_API_KEY    default "local" (local servers ignore it)
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)                      # paths below stay relative, so SQL and logs never show your home folder
LAKE = Path("lake")
RAW = LAKE / "raw"
INCOMING = LAKE / "incoming"
QUARANTINE = LAKE / "quarantine"
STATE = Path("state")
DB = LAKE / "warehouse.duckdb"

BASE_URL = os.environ.get("DATA_AGENT_BASE_URL", "http://localhost:8998/v1")
MODEL = os.environ.get("DATA_AGENT_MODEL", "")
API_KEY = os.environ.get("DATA_AGENT_API_KEY", "local")
TEMPERATURE = float(os.environ.get("DATA_AGENT_TEMPERATURE", "0"))
MAX_STEPS = int(os.environ.get("DATA_AGENT_MAX_STEPS", "14"))
