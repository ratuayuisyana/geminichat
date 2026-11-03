
"""
Advanced RAG untuk Gemini Chatbot

Fitur:
- Membaca PDF, TXT, dan Markdown
- Ekstraksi teks PDF per halaman
- Smart chunking berdasarkan paragraf
- Gemini Embedding
- Hybrid Search (Semantic + Keyword)
- Penyimpanan indeks dan vektor
- Pencarian dengan sumber dokumen dan halaman
"""

import hashlib
import io
import json
import re
import threading
from pathlib import Path

import numpy as np
from pypdf import PdfReader
from google.genai import types


# =========================
# KONFIGURASI
# =========================

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSION = 768

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200

DATA_DIR = Path("rag_data")


# =========================
# EKSTRAKSI DOKUMEN
# =========================

def extract_document(filename, data):
    extension = Path(filename).suffix.lower()
    pages = []

    if extension == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(data), strict=False)

            if reader.is_encrypted:
                try:
                    reader.decrypt("")
                except Exception:
                    raise ValueError(
                        "PDF dilindungi password. Gunakan PDF tanpa password."
                    )

            for number, page in enumerate(reader.pages, start=1):
                try:
                    text = page.extract_text() or ""
                except Exception as exc:
                    raise ValueError(
                        f"Gagal membaca halaman PDF {number}: {exc}"
                    )

                if text.strip():
                    pages.append({
                        "page": number,
                        "text": text
                    })

        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(
                f"File PDF tidak dapat dibaca: {exc}"
            )

        if not pages:
            raise ValueError(
                "PDF tidak memiliki teks yang dapat dibaca. "
                "Jika PDF berupa hasil scan atau foto, diperlukan OCR."
            )

    elif extension in {".txt", ".md"}:
        try:
            text = data.decode("utf-8-sig", errors="replace")
        except Exception as exc:
            raise ValueError(
                f"Gagal membaca file teks: {exc}"
            )

        if text.strip():
            pages.append({
                "page": 1,
                "text": text
            })

    else:
        raise ValueError(
            "Format dokumen tidak didukung. Gunakan PDF, TXT, atau MD."
        )

    return pages


# =========================
# PEMBERSIHAN TEKS
# =========================

def clean_text(text):
    text = text.replace("\x00", " ")
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Menghapus spasi berlebihan
    text = re.sub(r"[ \t]+", " ", text)

    # Mengurangi baris kosong berlebihan
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# =========================
# SMART CHUNKING
# =========================

def split_text(
    text,
    size=CHUNK_SIZE,
    overlap=CHUNK_OVERLAP
):
    text = clean_text(text)

    if not text:
        return []

    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]

    chunks = []
    current = ""

    for paragraph in paragraphs:

        # Pecah paragraf yang terlalu panjang
        if len(paragraph) > size:

            if current:
                chunks.append(current)
                current = ""

            start = 0

            while start < len(paragraph):
                end = start + size

                chunks.append(
                    paragraph[start:end].strip()
                )

                if end >= len(paragraph):
                    break

                start = end - overlap

            continue

        candidate = (
            current + "\n\n" + paragraph
            if current
            else paragraph
        )

        if len(candidate) <= size:
            current = candidate

        else:
            if current:
                chunks.append(current)

            current = paragraph

    if current:
        chunks.append(current)

    return [
        chunk.strip()
        for chunk in chunks
        if chunk.strip()
    ]


# =========================
# TEXT PROCESSING
# =========================

def tokenize(text):
    return set(
        re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())
    )


def keyword_score(query, content):
    query_words = tokenize(query)
    content_words = tokenize(content)

    if not query_words:
        return 0.0

    matched = query_words & content_words

    return len(matched) / len(query_words)


# =========================
# VECTOR NORMALIZATION
# =========================

def normalize(vectors):
    vectors = np.asarray(
        vectors,
        dtype=np.float32
    )

    if vectors.size == 0:
        return np.empty(
            (0, EMBEDDING_DIMENSION),
            dtype=np.float32
        )

    norms = np.linalg.norm(
        vectors,
        axis=1,
        keepdims=True
    )

    return vectors / np.maximum(norms, 1e-12)


# =========================
# ADVANCED RAG STORE
# =========================

class RagStore:

    def __init__(self, client, data_dir=DATA_DIR):
        self.client = client
        self.data_dir = Path(data_dir)

        self.index_file = self.data_dir / "index.json"
        self.vector_file = self.data_dir / "vectors.npy"

        self.data_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.lock = threading.RLock()

        self.chunks = []

        self.vectors = np.empty(
            (0, EMBEDDING_DIMENSION),
            dtype=np.float32
        )

        self.load()

    # =====================
    # GEMINI EMBEDDING
    # =====================

    def embed(self, texts, task_type):

        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return np.empty(
                (0, EMBEDDING_DIMENSION),
                dtype=np.float32
            )

        results = []

        # Memproses embedding secara bertahap
        for start in range(0, len(texts), 20):

            batch = texts[start:start + 20]

            response = self.client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=EMBEDDING_DIMENSION
                )
            )

            if not response.embeddings:
                raise RuntimeError(
                    "Gemini tidak menghasilkan embedding."
                )

            for item in response.embeddings:
                results.append(item.values)

        embeddings = normalize(results)

        if len(embeddings) != len(texts):
            raise RuntimeError(
                "Jumlah embedding tidak sesuai dengan jumlah teks."
            )

        return embeddings

    # =====================
    # SIMPAN INDEX
    # =====================

    def save(self):

        with self.lock:

            temp_index = self.index_file.with_suffix(".tmp")
            temp_vector = self.vector_file.with_suffix(".tmp.npy")

            temp_index.write_text(
                json.dumps(
                    self.chunks,
                    ensure_ascii=False,
                    indent=2
                ),
                encoding="utf-8"
            )

            np.save(
                temp_vector,
                self.vectors
            )

            temp_index.replace(self.index_file)
            temp_vector.replace(self.vector_file)

    # =====================
    # LOAD INDEX
    # =====================

    def load(self):

        with self.lock:

            if not self.index_file.exists():
                return

            if not self.vector_file.exists():
                return

            try:

                chunks = json.loads(
                    self.index_file.read_text(
                        encoding="utf-8"
                    )
                )

                vectors = np.load(
                    self.vector_file
                )

                if len(chunks) != len(vectors):
                    raise ValueError(
                        "Jumlah data indeks dan vektor tidak sama."
                    )

                if vectors.ndim != 2:
                    raise ValueError(
                        "Format vektor tidak valid."
                    )

                if vectors.shape[1] != EMBEDDING_DIMENSION:
                    raise ValueError(
                        "Dimensi embedding tidak sesuai."
                    )

                self.chunks = chunks

                self.vectors = vectors.astype(
                    np.float32
                )

            except (
                OSError,
                ValueError,
                json.JSONDecodeError,
                EOFError
            ) as exc:

                print("[RAG LOAD ERROR]", repr(exc))

                self.chunks = []

                self.vectors = np.empty(
                    (0, EMBEDDING_DIMENSION),
                    dtype=np.float32
                )

    # =====================
    # TAMBAH DOKUMEN
    # =====================

    def add_file(self, filename, data):

        extension = Path(filename).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise ValueError(
                "Gunakan PDF, TXT, atau MD."
            )

        if not data:
            raise ValueError(
                "File kosong."
            )

        document_hash = hashlib.sha256(
            data
        ).hexdigest()

        # Ekstraksi dokumen
        pages = extract_document(
            filename,
            data
        )

        new_chunks = []

        for page in pages:

            parts = split_text(
                page["text"]
            )

            for number, content in enumerate(parts, start=1):

                chunk_id = hashlib.sha256(
                    f"{document_hash}-{page['page']}-{number}".encode()
                ).hexdigest()

                new_chunks.append({
                    "id": chunk_id,
                    "filename": Path(filename).name,
                    "document_hash": document_hash,
                    "page": page["page"],
                    "chunk": number,
                    "text": content
                })

        if not new_chunks:
            raise ValueError(
                "Tidak ditemukan teks dalam dokumen."
            )

        # Membuat embedding
        embeddings = self.embed(
            [item["text"] for item in new_chunks],
            "RETRIEVAL_DOCUMENT"
        )

        with self.lock:

            # Mengganti dokumen lama dengan nama yang sama
            self.delete_document(
                Path(filename).name
            )

            self.chunks.extend(
                new_chunks
            )

            if len(self.vectors) == 0:

                self.vectors = embeddings

            else:

                self.vectors = np.vstack([
                    self.vectors,
                    embeddings
                ])

            self.save()

        return {
            "filename": Path(filename).name,
            "total_chunks": len(new_chunks),
            "status": "success"
        }

    # =====================
    # HAPUS DOKUMEN
    # =====================

    def delete_document(self, filename):

        with self.lock:

            keep = [
                i
                for i, item in enumerate(self.chunks)
                if item["filename"] != filename
            ]

            self.chunks = [
                self.chunks[i]
                for i in keep
            ]

            if keep:

                self.vectors = self.vectors[keep]

            else:

                self.vectors = np.empty(
                    (0, EMBEDDING_DIMENSION),
                    dtype=np.float32
                )

            self.save()

    # =====================
    # HYBRID SEARCH
    # =====================

    def search(self, query, top_k=5):

        query = query.strip()

        if not query:
            return []

        with self.lock:

            if not self.chunks:
                return []

            query_vector = self.embed(
                query,
                "RETRIEVAL_QUERY"
            )[0]

            semantic_scores = (
                self.vectors @ query_vector
            )

            results = []

            for index, item in enumerate(self.chunks):

                semantic = float(
                    semantic_scores[index]
                )

                keyword = keyword_score(
                    query,
                    item["text"]
                )

                # Gabungan semantic dan keyword
                final_score = (
                    0.80 * semantic +
                    0.20 * keyword
                )

                results.append({
                    **item,
                    "semantic_score": round(semantic, 4),
                    "keyword_score": round(keyword, 4),
                    "score": round(final_score, 4)
                })

            results.sort(
                key=lambda item: item["score"],
                reverse=True
            )

            return results[:top_k]

    # =====================
    # STATISTIK
    # =====================

    def stats(self):

        with self.lock:

            filenames = list(dict.fromkeys(
                item["filename"]
                for item in self.chunks
            ))

            return {
                "total_documents": len(filenames),
                "total_chunks": len(self.chunks),
                "documents": filenames
            }
