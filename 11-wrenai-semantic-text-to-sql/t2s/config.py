"""Paths and the T2S_* settings. Any OpenAI-compatible server works (llama.cpp, Ollama, LM Studio, vLLM)."""
import json, os, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
WAREHOUSE = Path(os.environ.get("T2S_WAREHOUSE", HERE.parent / "10-metricflow-banking-metrics" / "warehouse" / "bank.duckdb"))
WREN_PROJECT = HERE / "wren_bank"
EVAL = HERE / "eval"
BASE_URL = os.environ.get("T2S_BASE_URL", "http://127.0.0.1:8999/v1")
API_KEY = os.environ.get("T2S_API_KEY", "local")
MAX_REQUESTS = int(os.environ.get("T2S_MAX_REQUESTS", "10"))
# Shared by EVERY arm: the one fact any analyst is told on day one.
DATA_NOTE = "The data runs from 2025-01-01 to 2026-10-31; treat 'now' as 2026-10-31."
# Shared by EVERY arm: answer the question that was asked, then stop.
FINISH_NOTE = ("Answer only the question asked; never invent follow-up questions. Always execute your final SQL "
               "and take every number in your answer from its result. As soon as a query returns the numbers "
               "that answer the question, stop and reply with the answer.")


def model_name() -> str:
    name = os.environ.get("T2S_MODEL")
    if name:
        return name
    with urllib.request.urlopen(BASE_URL.rstrip("/") + "/models", timeout=10) as r:
        return json.load(r)["data"][0]["id"]


def llm():
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
    from pydantic_ai.settings import ModelSettings
    return OpenAIChatModel(model_name(), provider=OpenAIProvider(base_url=BASE_URL, api_key=API_KEY),
                           settings=ModelSettings(temperature=0, max_tokens=700))
