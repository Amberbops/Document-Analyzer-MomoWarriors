# Document Analyzer

A Retrieval-Augmented Generation (RAG) web app that lets you upload a PDF and interact with its contents through three modes — **Analyze**, **Extract**, and **Rewrite** — with results streamed live from the LLM.

Upload a document, and it's parsed, chunked, and embedded locally. Your instruction is then matched against the most relevant chunks using semantic search, and an LLM generates a response grounded in that context, streamed word-by-word back to the browser.

## How it works

The backend is built with FastAPI. When a PDF is uploaded, it's parsed and split into overlapping text chunks, which are embedded using a local sentence-transformer model and stored in a persistent Chroma vector database. When you ask a question or give an instruction, that query is embedded too, compared against the stored chunks via cosine similarity, and the closest matches are pulled in as context for the LLM — Groq's LLaMA 3.1 model — which streams its response back token by token.

The frontend is a single static HTML file with no build step: drag a PDF in, pick a mode, write an instruction, and watch the result render progressively as it's generated.

## Modes

- **Analyze** — summarizes the document's key themes and implications
- **Extract** — pulls structured facts, entities, and data points
- **Rewrite** — restructures the content for clarity

## Tech stack

FastAPI · PyMuPDF · sentence-transformers · Chroma · Groq (LLaMA 3.1) · vanilla HTML/CSS/JS

## Project structure

```
app/
  main.py            FastAPI entry point
  core/
    parsing.py       PDF loading + chunking
    vectorstore.py   Embeddings, storage, retrieval
    llm.py           Prompts per mode + streaming
  routes/
    api.py           /upload, /analyze, /health
frontend/
  index.html         The UI
data/
  pdf/               Uploaded PDFs
  vector_store/      Chroma's local database
notebook/            Original prototyping notebook
```
