"""
Module 4 (generation half) — LLM Integration & Prompt Engineering

Built on your actual setup: langchain_groq.ChatGroq with
llama-3.1-8b-instant. Extended from your single rag_simple() function
into three distinct modes (Analyze / Extract / Rewrite) as required
by the brief, each with its own system prompt and temperature.

The API key is loaded ONLY from the environment now — never hardcode
it here or in the notebook. Set GROQ_API_KEY in your .env file.
"""

import os
from typing import List, Dict, AsyncGenerator

from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY not found in environment. "
        "Add it to your .env file — never hardcode it in source."
    )

# --- Prompt registry ---------------------------------------------------
# Document each version/change here for your Module 6 report.

PROMPTS = {
    "extract": {
        "system": (
            "You are a precise information extraction assistant. Extract key "
            "facts, entities, and data points from the provided context as a "
            "clean structured list. Do not add commentary, opinions, or "
            "information not present in the context."
        ),
        "temperature": 0.0,
    },
    "analyze": {
        "system": (
            "You are a document analysis assistant. Read the provided context "
            "and produce a clear summary of its key themes, arguments, and "
            "implications, in your own words rather than copying text verbatim."
        ),
        "temperature": 0.1,  # matches your original rag_simple() setting
    },
    "rewrite": {
        "system": (
            "You are a skilled editor. Rewrite the provided context to be "
            "clearer, more engaging, and well-structured, while preserving "
            "its original meaning and factual content."
        ),
        "temperature": 0.7,
    },
}

# One LLM client per mode, so temperature differs correctly per request
_llm_cache: Dict[str, ChatGroq] = {}


def get_llm(mode: str) -> ChatGroq:
    if mode not in _llm_cache:
        config = PROMPTS[mode]
        _llm_cache[mode] = ChatGroq(
            groq_api_key=GROQ_API_KEY,
            model="llama-3.1-8b-instant",
            temperature=config["temperature"],
            max_tokens=1024,
        )
    return _llm_cache[mode]


def build_context(retrieved_chunks: List[Dict]) -> str:
    """Join retrieved chunks into a single context block, same shape as rag_simple()."""
    return "\n\n".join(doc["content"] for doc in retrieved_chunks)


def build_prompt(mode: str, query: str, context: str) -> str:
    system = PROMPTS[mode]["system"]
    return f"""{system}

context:
{context}

Question: {query}

Answer:"""


async def stream_response(
    mode: str,
    query: str,
    retrieved_chunks: List[Dict],
) -> AsyncGenerator[str, None]:
    """
    Streams the LLM's response token-by-token for Module 1's frontend
    to render progressively.
    """
    if mode not in PROMPTS:
        raise ValueError(f"Unknown mode '{mode}'. Must be one of: {list(PROMPTS)}")

    context = build_context(retrieved_chunks)
    if not context:
        yield "No relevant context found to answer the question."
        return

    prompt = build_prompt(mode, query, context)
    llm = get_llm(mode)

    async for chunk in llm.astream(prompt):
        if chunk.content:
            yield chunk.content


async def generate_response(
    mode: str,
    query: str,
    retrieved_chunks: List[Dict],
) -> str:
    """Non-streaming version — same shape as your original rag_simple()."""
    parts = []
    async for token in stream_response(mode, query, retrieved_chunks):
        parts.append(token)
    return "".join(parts)
