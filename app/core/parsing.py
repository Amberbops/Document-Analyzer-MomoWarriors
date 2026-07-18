"""
Module 3 — Document Parsing & Extraction

This mirrors your notebook's actual logic:
  DirectoryLoader/PyMuPDFLoader -> split_documents()
but wrapped as callable functions instead of top-level notebook cells,
and operating on a single uploaded file rather than a whole directory.

Returns langchain Document objects (not plain strings) so metadata
(source, page number, etc.) survives into the vector store, exactly
like your original split_documents() did.
"""

import os
from typing import List

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


class ExtractionError(Exception):
    """Raised when a file can't be parsed as a valid document."""
    pass


def load_pdf(file_path: str) -> List[Document]:
    """
    Load a single PDF into a list of langchain Documents (one per page).

    Raises ExtractionError with a clean message instead of leaking a raw
    pymupdf FzErrorFormat/FileDataError traceback to the API caller —
    this is the exact bug you hit with the mislabeled .pdf file.
    """
    if not os.path.exists(file_path):
        raise ExtractionError(f"File not found: {file_path}")

    try:
        loader = PyMuPDFLoader(file_path)
        docs = loader.load()
    except Exception as e:
        raise ExtractionError(
            f"Could not read '{os.path.basename(file_path)}' as a PDF. "
            f"The file may be corrupted or not a real PDF. Details: {e}"
        )

    if not docs:
        raise ExtractionError(f"No extractable text found in '{file_path}'.")

    return docs


def split_documents(
    documents: List[Document],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[Document]:
    """
    Identical logic to your notebook's split_documents(), just moved
    into this module so both the notebook and the API can import it.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )
    split_docs = text_splitter.split_documents(documents)
    print(f"Split {len(documents)} documents into {len(split_docs)} chunks")

    if split_docs:
        print("\nExample chunk:")
        print(f"Content: {split_docs[0].page_content[:200]}...")
        print(f"Metadata: {split_docs[0].metadata}")

    return split_docs


def extract_and_chunk(
    file_path: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> List[Document]:
    """
    Convenience function combining load + split.
    This is the single function Module 2's /upload route calls.
    """
    docs = load_pdf(file_path)
    return split_documents(docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
