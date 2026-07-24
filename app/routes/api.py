"""
Module 2 — Backend Core & API Routing

Wires together your actual EmbeddingManager, VectorStore, RAGRetriever
(from vectorstore.py), your parsing logic (from parsing.py), and the
three-mode LLM layer (from llm.py) into three endpoints:
    /upload, /analyze, /health
"""

import os
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import StreamingResponse

from app.core.parsing import extract_and_chunk, ExtractionError
from app.core.vectorstore import EmbeddingManager, VectorStore, RAGRetriever
from app.core.llm import stream_response

router = APIRouter()

UPLOAD_DIR = "./data/pdf"
MAX_FILE_SIZE_MB = 20

# Loaded once at startup — loading the embedding model per-request would be slow.
embedding_manager = EmbeddingManager()
vectorstore = VectorStore(persist_directory="./data/vector_store")
rag_retriever = RAGRetriever(vectorstore, embedding_manager)


@router.get("/health")
async def health():
    try:
        if not embedding_manager.model:
            return {"status": "degraded", "reason": "Embedding model not loaded"}
        if vectorstore.collection is None:
            return {"status": "degraded", "reason": "Vector store not initialized"}
        return {"status": "ok", "embedding_model": embedding_manager.model_name}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    """
    Accepts a PDF, extracts + chunks it (parsing.py), embeds it
    (EmbeddingManager), and stores it (VectorStore).
    Returns a file_id the frontend references in /analyze.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({size_mb:.1f}MB). Max is {MAX_FILE_SIZE_MB}MB.",
        )
    if size_mb == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_id = str(uuid.uuid4())
    save_path = os.path.join(UPLOAD_DIR, f"{file_id}.pdf")
    with open(save_path, "wb") as f:
        f.write(contents)

    try:
        chunks = extract_and_chunk(save_path)
    except ExtractionError as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(status_code=422, detail=str(e))

    try:
        texts = [doc.page_content for doc in chunks]
        embeddings = embedding_manager.generate_embeddings(texts)
        vectorstore.add_documents(chunks, embeddings, source_id=file_id)
    except Exception as e:
        if os.path.exists(save_path):
            os.remove(save_path)
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")


    return {
        "file_id": file_id,
        "chunks_created": len(chunks),
        "total_documents_in_store": vectorstore.collection.count(),
    }


@router.post("/analyze")
async def analyze(
    mode: str = Form(...),
    query: str = Form(...),
    top_k: int = Form(5),
):
    """
    mode: "analyze" | "extract" | "rewrite"
    query: the user's question or instruction
    Streams the LLM's response back as it's generated.
    """
    if mode not in ("analyze", "extract", "rewrite"):
        raise HTTPException(
            status_code=400,
            detail="mode must be one of: analyze, extract, rewrite",
        )
    if not query.strip():
        raise HTTPException(status_code=400, detail="query cannot be empty.")

    retrieved = rag_retriever.retrieve(query, top_k=top_k)
    if not retrieved:
        raise HTTPException(
            status_code=404,
            detail="No relevant documents found. Upload a document first.",
        )

    async def event_stream():
        async for token in stream_response(mode, query, retrieved):
            yield token

    return StreamingResponse(event_stream(), media_type="text/plain")
