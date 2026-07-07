"""
RAG Pipeline (Retrieval-Augmented Generation)
Indexes knowledge base documents using sentence-transformer embeddings
and FAISS for fast similarity search.
"""

import os
import logging
import pickle
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
    import faiss
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    logger.warning("sentence-transformers or faiss not installed. RAG will use keyword fallback.")


class RAGPipeline:
    """
    Lightweight RAG pipeline:
    1. Loads .txt knowledge base files and splits them into chunks
    2. Encodes chunks with a sentence-transformer model
    3. Builds a FAISS index for fast nearest-neighbour retrieval
    4. Retrieves top-k relevant chunks for a query at inference time
    """

    CACHE_PATH = "data/rag_index.pkl"
    CHUNK_SIZE = 400         # characters per chunk
    CHUNK_OVERLAP = 80       # overlap between adjacent chunks
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # lightweight, fast, 384-dim

    def __init__(self, knowledge_base_dir: str = "knowledge_base"):
        self.kb_dir = Path(knowledge_base_dir)
        self.chunks: list[str] = []
        self.sources: list[str] = []
        self.index = None
        self.model = None
        self._initialized = False

        if RAG_AVAILABLE:
            self._load_or_build_index()
        else:
            self._load_chunks_only()

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    def retrieve(self, query: str, top_k: int = 5) -> list[str]:
        """Return top-k most relevant chunks for the query."""
        if not self.chunks:
            return []
        if RAG_AVAILABLE and self.index is not None and self.model is not None:
            return self._vector_search(query, top_k)
        return self._keyword_search(query, top_k)

    def add_document(self, content: str, source: str = "user_upload") -> int:
        """Add an ad-hoc document (e.g. parsed resume) to the index."""
        new_chunks = self._split_text(content)
        if not new_chunks:
            return 0
        if RAG_AVAILABLE and self.model is not None:
            new_embeddings = self.model.encode(new_chunks, show_progress_bar=False)
            new_embeddings = new_embeddings / (
                np.linalg.norm(new_embeddings, axis=1, keepdims=True) + 1e-10
            )
            if self.index is None:
                dim = new_embeddings.shape[1]
                self.index = faiss.IndexFlatIP(dim)
            self.index.add(new_embeddings.astype("float32"))
        self.chunks.extend(new_chunks)
        self.sources.extend([source] * len(new_chunks))
        return len(new_chunks)

    # ─────────────────────────────────────────────────────────────
    # Index construction
    # ─────────────────────────────────────────────────────────────

    def _load_or_build_index(self):
        cache = Path(self.CACHE_PATH)
        if cache.exists():
            try:
                self._load_cache(cache)
                logger.info("RAG index loaded from cache (%d chunks)", len(self.chunks))
                return
            except Exception as e:
                logger.warning("Cache load failed (%s), rebuilding index.", e)

        self._build_index()
        self._save_cache(cache)

    def _build_index(self):
        logger.info("Building RAG index from %s …", self.kb_dir)
        self.chunks, self.sources = self._load_knowledge_base()
        if not self.chunks:
            logger.warning("No knowledge base chunks found.")
            return
        self.model = SentenceTransformer(self.EMBEDDING_MODEL)
        embeddings = self.model.encode(self.chunks, show_progress_bar=False)
        # L2-normalise for cosine similarity via inner-product
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / (norms + 1e-10)
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings.astype("float32"))
        self._initialized = True
        logger.info("RAG index built: %d chunks, dim=%d", len(self.chunks), dim)

    def _load_chunks_only(self):
        """No vector models available — load chunks for keyword search."""
        self.chunks, self.sources = self._load_knowledge_base()
        logger.info("Keyword-only RAG loaded: %d chunks", len(self.chunks))

    # ─────────────────────────────────────────────────────────────
    # Caching
    # ─────────────────────────────────────────────────────────────

    def _save_cache(self, cache_path: Path):
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "wb") as f:
                pickle.dump({
                    "chunks": self.chunks,
                    "sources": self.sources,
                }, f)
            # FAISS index saved separately
            if self.index is not None:
                faiss.write_index(self.index, str(cache_path) + ".faiss")
            logger.info("RAG cache saved to %s", cache_path)
        except Exception as e:
            logger.warning("Cache save failed: %s", e)

    def _load_cache(self, cache_path: Path):
        with open(cache_path, "rb") as f:
            data = pickle.load(f)
        self.chunks = data["chunks"]
        self.sources = data["sources"]
        faiss_path = str(cache_path) + ".faiss"
        if RAG_AVAILABLE and Path(faiss_path).exists():
            self.index = faiss.read_index(faiss_path)
            self.model = SentenceTransformer(self.EMBEDDING_MODEL)
            self._initialized = True

    # ─────────────────────────────────────────────────────────────
    # Search methods
    # ─────────────────────────────────────────────────────────────

    def _vector_search(self, query: str, top_k: int) -> list[str]:
        query_vec = self.model.encode([query], show_progress_bar=False)
        query_vec = query_vec / (np.linalg.norm(query_vec, axis=1, keepdims=True) + 1e-10)
        k = min(top_k, len(self.chunks))
        scores, indices = self.index.search(query_vec.astype("float32"), k)
        results = []
        for idx in indices[0]:
            if 0 <= idx < len(self.chunks):
                results.append(self.chunks[idx])
        return results

    def _keyword_search(self, query: str, top_k: int) -> list[str]:
        """Simple TF-based keyword search fallback."""
        keywords = set(query.lower().split())
        scored = []
        for chunk in self.chunks:
            lower = chunk.lower()
            score = sum(lower.count(kw) for kw in keywords)
            if score > 0:
                scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    # ─────────────────────────────────────────────────────────────
    # Document loading & chunking
    # ─────────────────────────────────────────────────────────────

    def _load_knowledge_base(self) -> tuple[list[str], list[str]]:
        all_chunks: list[str] = []
        all_sources: list[str] = []
        if not self.kb_dir.exists():
            logger.warning("Knowledge base directory not found: %s", self.kb_dir)
            return [], []
        for txt_file in sorted(self.kb_dir.glob("*.txt")):
            try:
                text = txt_file.read_text(encoding="utf-8")
                chunks = self._split_text(text)
                all_chunks.extend(chunks)
                all_sources.extend([txt_file.name] * len(chunks))
                logger.debug("Loaded %d chunks from %s", len(chunks), txt_file.name)
            except Exception as e:
                logger.warning("Failed to load %s: %s", txt_file, e)
        return all_chunks, all_sources

    def _split_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks."""
        chunks: list[str] = []
        size = self.CHUNK_SIZE
        overlap = self.CHUNK_OVERLAP
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            chunk = text[start:end].strip()
            if len(chunk) > 50:  # skip tiny fragments
                chunks.append(chunk)
            if end == len(text):
                break
            start += size - overlap
        return chunks
