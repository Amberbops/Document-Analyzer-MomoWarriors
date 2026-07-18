"""
Module 4 (retrieval half) — Embeddings, vector storage, and retrieval.

These are YOUR actual classes from the notebook (EmbeddingManager,
VectorStore, RAGRetriever), moved here as-is with three small fixes:

1. persist_directory default changed from "../data/vector_store" to
   "./data/vector_store" — your notebook path was relative to the
   notebook/ subfolder; the app runs from the project root, so the
   path needs one fewer "..".
2. get_sentence_embedding_dimension() -> get_embedding_dimension()
   (fixes the FutureWarning you saw).
3. collection.add() -> collection.upsert() in add_documents(), using
   deterministic ids instead of random uuid4 ids. This fixes the
   "Total documents in collection: 2" duplicate-growth issue —
   re-uploading the same file/chunk no longer creates a new row
   every time the app restarts or you re-run a cell.
"""

import os
import uuid
from typing import Any, List, Dict

import numpy as np
import chromadb
from sentence_transformers import SentenceTransformer


class EmbeddingManager:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            print(f"Loading Embedding Model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            # was get_sentence_embedding_dimension() — deprecated, fixed here
            print(f"Model Loaded Successfully. Embedding dimension: {self.model.get_embedding_dimension()}")
        except Exception as e:
            print(f"Error loading model {self.model_name}: {e}")
            raise

    def generate_embeddings(self, texts: List[str]) -> np.ndarray:
        if not self.model:
            raise ValueError("Model not loaded")
        print(f"Generating Embeddings for {len(texts)} texts...")
        embeddings = self.model.encode(texts, show_progress_bar=True)
        print(f"Generated Embeddings with shape: {embeddings.shape}")
        return embeddings


class VectorStore:
    def __init__(
        self,
        collection_name: str = "pdf_documents",
        persist_directory: str = "./data/vector_store",
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.client = None
        self.collection = None
        self._initialize_store()

    def _initialize_store(self):
        try:
            os.makedirs(self.persist_directory, exist_ok=True)
            self.client = chromadb.PersistentClient(path=self.persist_directory)
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "description": "PDF document embeddings for RAG",
                    "hnsw:space": "cosine",  # without this, Chroma defaults to
                    # squared L2 distance, which breaks the 1 - distance
                    # similarity formula used in retrieve() below — scores
                    # go negative and everything gets filtered out.
                },
            )
            print(f"Vector store initialized. Collection: {self.collection_name}")
            print(f"Existing documents in collection: {self.collection.count()}")
        except Exception as e:
            print(f"Error initializing vector store: {e}")
            raise

    def add_documents(self, documents: List[Any], embeddings: np.ndarray, source_id: str = None):
        """
        source_id: pass the uploaded file's id (e.g. file_id from the API)
        so ids are deterministic per-document-per-chunk. Re-uploading the
        same file will overwrite its old chunks instead of duplicating them.
        Falls back to a random id (your original behavior) if not given.
        """
        if len(documents) != len(embeddings):
            raise ValueError("Number of documents must match number of embeddings")

        print(f"Adding {len(documents)} documents to vector store")
        ids = []
        metadatas = []
        documents_text = []
        embeddings_list = []

        for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
            if source_id:
                doc_id = f"{source_id}_{i}"
            else:
                doc_id = f"doc_{uuid.uuid4().hex[:8]}_{i}"
            ids.append(doc_id)
            metadata = dict(doc.metadata)
            metadata["doc_index"] = i
            metadata["content_length"] = len(doc.page_content)
            metadatas.append(metadata)
            documents_text.append(doc.page_content)
            embeddings_list.append(embedding.tolist())

        try:
            # was .add() — switched to .upsert() so re-adding the same
            # deterministic ids updates in place instead of duplicating
            self.collection.upsert(
                ids=ids,
                embeddings=embeddings_list,
                metadatas=metadatas,
                documents=documents_text,
            )
            print(f"Successfully added {len(documents)} documents to vector store")
            print(f"Total documents in collection: {self.collection.count()}")
        except Exception as e:
            print(f"Error adding documents to vector store: {e}")
            raise


class RAGRetriever:
    def __init__(self, vector_store: VectorStore, embedding_manager: EmbeddingManager):
        self.vector_store = vector_store
        self.embedding_manager = embedding_manager

    def retrieve(self, query: str, top_k: int = 5, score_threshold: float = -1.0) -> List[Dict[str, Any]]:
        # score_threshold defaults to -1.0 (accept everything) rather than 0.0.
        # With small collections (a handful of chunks from one document),
        # an instructional query like "generate questions about this" can
        # legitimately score below 0.0 in cosine similarity against a
        # factual chunk, even when it's still the best available match.
        # Filtering those out means top_k chunks silently return nothing
        # useful. Pass a real threshold (e.g. 0.2) only when you actually
        # want to exclude weak matches in a larger corpus.
        print(f"Retrieving documents for query: '{query}'")
        print(f"Top K: {top_k}, Score threshold: {score_threshold}")
        query_embeddings = self.embedding_manager.generate_embeddings([query])[0]
        try:
            results = self.vector_store.collection.query(
                query_embeddings=[query_embeddings.tolist()],
                n_results=top_k,
            )
            retrieved_docs = []
            if results["documents"] and results["documents"][0]:
                documents = results["documents"][0]
                metadatas = results["metadatas"][0]
                distances = results["distances"][0]
                ids = results["ids"][0]
                for i, (doc_id, document, metadata, distance) in enumerate(
                    zip(ids, documents, metadatas, distances)
                ):
                    similarity_score = 1 - distance
                    if similarity_score >= score_threshold:
                        retrieved_docs.append({
                            "id": doc_id,
                            "content": document,
                            "metadata": metadata,
                            "similarity_score": similarity_score,
                            "distance": distance,
                            "rank": i + 1,
                        })
                print(f"Retrieved {len(retrieved_docs)} documents (after filtering)")
            else:
                print("No documents found")
            return retrieved_docs
        except Exception as e:
            print(f"Error during retrieval: {e}")
            return []
