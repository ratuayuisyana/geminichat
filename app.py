
import os
import threading
import webbrowser
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google import genai
from google.genai import types
from werkzeug.utils import secure_filename

from rag import RagStore, ALLOWED_EXTENSIONS


# ==========================================
# KONFIGURASI APLIKASI
# ==========================================

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

KNOWLEDGE_DIR = BASE_DIR / "knowledge"
DATA_DIR = BASE_DIR / "rag_data"

KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)

MAX_UPLOAD_MB = int(os.getenv("RAG_MAX_UPLOAD_MB", "10"))

app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

MODEL_NAME = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
).strip()

client = genai.Client(api_key=API_KEY) if API_KEY else None


# ==========================================
# INSTRUKSI GEMINI
# ==========================================

SYSTEM_INSTRUCTION = """
Kamu adalah asisten AI yang cerdas, ramah,
komunikatif, dan profesional.

Aturan:
1. Jawab menggunakan bahasa pengguna.
2. Pahami maksud pertanyaan sebelum menjawab.
3. Berikan jawaban yang jelas dan terstruktur.
4. Gunakan konteks percakapan sebelumnya jika relevan.
5. Jangan mengarang informasi.
6. Jika tidak mengetahui jawabannya, katakan dengan jujur.
7. Hindari jawaban berulang dan terlalu kaku.
"""

RAG_INSTRUCTION = """
Kamu memiliki akses ke BASIS PENGETAHUAN berupa
dokumen yang diunggah oleh pengguna.

Aturan:
1. Gunakan konteks dokumen sebagai sumber utama.
2. Cantumkan nomor sumber seperti [1] atau [2]
   jika menggunakan informasi dari dokumen.
3. Gabungkan informasi dari beberapa sumber jika diperlukan.
4. Jangan mengarang informasi yang tidak terdapat dalam dokumen.
5. Jika dokumen tidak memuat jawabannya, katakan dengan jujur.
6. Jika pengguna meminta ringkasan, buat ringkasan terstruktur.
7. Jika pengguna meminta penjelasan, gunakan bahasa sederhana.
8. Jangan mengaku membaca informasi yang tidak ditemukan.
"""


# ==========================================
# INISIALISASI RAG
# ==========================================

rag_store = (
    RagStore(
        client=client,
        data_dir=DATA_DIR
    )
    if client
    else None
)


def get_store():
    if rag_store is None:
        raise RuntimeError("API key Gemini belum diatur.")

    return rag_store


# ==========================================
# SINKRONISASI DOKUMEN
# ==========================================

def sync_knowledge():
    if not client or not rag_store:
        print("[RAG] API key belum tersedia.")
        return

    store = get_store()

    existing_documents = set(
        store.stats().get("documents", [])
    )

    for path in KNOWLEDGE_DIR.iterdir():

        if not path.is_file():
            continue

        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue

        # Hindari embedding ulang dokumen
        # yang sudah tersedia dalam indeks.
        if path.name in existing_documents:
            print(f"[RAG] Sudah terindeks: {path.name}")
            continue

        try:
            info = store.add_file(
                path.name,
                path.read_bytes()
            )

            print(
                f"[RAG] Berhasil membaca {path.name}: "
                f"{info['total_chunks']} bagian"
            )

        except Exception as exc:
            print(
                f"[RAG] Gagal membaca {path.name}: {exc!r}"
            )


# ==========================================
# PENANGANAN ERROR
# ==========================================

@app.errorhandler(413)
def file_too_large(error):
    return jsonify({
        "error": (
            f"Ukuran file maksimal {MAX_UPLOAD_MB} MB."
        )
    }), 413


# ==========================================
# HALAMAN UTAMA
# ==========================================

@app.get("/")
def index():
    return render_template("index.html")


# ==========================================
# STATUS SERVER
# ==========================================

@app.get("/api/health")
def health():

    stats = (
        rag_store.stats()
        if rag_store
        else {
            "total_documents": 0,
            "total_chunks": 0,
            "documents": []
        }
    )

    return jsonify({
        "ok": True,
        "configured": bool(client),
        "model": MODEL_NAME,
        "rag": stats
    })


# ==========================================
# DAFTAR DOKUMEN
# ==========================================

@app.get("/api/rag/documents")
def list_documents():

    if not rag_store:
        return jsonify({
            "documents": [],
            "error": "API key Gemini belum diatur."
        }), 503

    documents = {}

    for chunk in rag_store.chunks:

        filename = chunk["filename"]

        if filename not in documents:
            documents[filename] = {
                "id": filename,
                "name": filename,
                "chunks": 0
            }

        documents[filename]["chunks"] += 1

    return jsonify({
        "documents": list(documents.values()),
        "stats": rag_store.stats()
    })


# ==========================================
# UPLOAD DOKUMEN
# ==========================================

@app.post("/api/rag/upload")
def upload_document():

    if not rag_store:
        return jsonify({
            "error": "API key Gemini belum diatur."
        }), 503

    file = request.files.get("file")

    if not file or not file.filename:
        return jsonify({
            "error": "Pilih dokumen terlebih dahulu."
        }), 400

    filename = secure_filename(file.filename)

    if not filename:
        return jsonify({
            "error": "Nama file tidak valid."
        }), 400

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        return jsonify({
            "error": "Gunakan format PDF, TXT, atau MD."
        }), 400

    data = file.read()

    if not data:
        return jsonify({
            "error": "File kosong."
        }), 400

    target = KNOWLEDGE_DIR / filename

    try:

        # Memproses dokumen:
        # ekstraksi teks, chunking, embedding,
        # dan penyimpanan indeks RAG.
        info = rag_store.add_file(
            filename,
            data
        )

        # Menyimpan dokumen asli.
        target.write_bytes(data)

        print(
            f"[RAG UPLOAD] Berhasil: {filename}"
        )

        print(
            f"[RAG UPLOAD] Total bagian: "
            f"{info['total_chunks']}"
        )

        return jsonify({
            "success": True,
            "message": "Dokumen berhasil diproses.",
            "document": {
                "id": filename,
                "name": filename,
                "chunks": info["total_chunks"]
            }
        }), 200

    except ValueError as exc:

        return jsonify({
            "error": str(exc)
        }), 400

    except Exception as exc:

        print("[RAG UPLOAD ERROR]", repr(exc))

        return jsonify({
            "error": (
                "Gagal memproses dokumen. "
                "Periksa terminal Flask."
            )
        }), 500


# ==========================================
# HAPUS DOKUMEN
# ==========================================

@app.delete("/api/rag/documents/<path:doc_id>")
def delete_document(doc_id):

    if not rag_store:
        return jsonify({
            "error": "RAG belum tersedia."
        }), 503

    filename = secure_filename(doc_id)

    if not filename:
        return jsonify({
            "error": "Nama dokumen tidak valid."
        }), 400

    try:

        rag_store.delete_document(filename)

        target = KNOWLEDGE_DIR / filename

        if target.is_file():
            target.unlink()

        print(
            f"[RAG DELETE] Dokumen dihapus: {filename}"
        )

        return jsonify({
            "success": True,
            "deleted": filename
        })

    except Exception as exc:

        print("[RAG DELETE ERROR]", repr(exc))

        return jsonify({
            "error": "Gagal menghapus dokumen."
        }), 500


# ==========================================
# CHAT GEMINI DENGAN RAG
# ==========================================

@app.post("/api/chat")
def chat():

    if not client:
        return jsonify({
            "error": (
                "API key belum diatur. "
                "Periksa file .env."
            )
        }), 503

    data = request.get_json(silent=True) or {}

    message = str(
        data.get("message", "")
    ).strip()

    history = data.get("history", [])

    use_rag = bool(
        data.get("use_rag", True)
    )

    if not message:
        return jsonify({
            "error": "Pesan kosong."
        }), 400

    if len(message) > 10000:
        return jsonify({
            "error": "Pesan terlalu panjang."
        }), 400

    if not isinstance(history, list):
        return jsonify({
            "error": "Riwayat percakapan tidak valid."
        }), 400

    # --------------------------------------
    # MEMBANGUN RIWAYAT PERCAKAPAN
    # --------------------------------------

    contents = []

    for item in history[-20:]:

        if not isinstance(item, dict):
            continue

        role = item.get("role")
        text = item.get("text")

        if (
            role in ("user", "model")
            and isinstance(text, str)
            and text.strip()
        ):

            contents.append(
                types.Content(
                    role=role,
                    parts=[
                        types.Part.from_text(
                            text=text[:10000]
                        )
                    ]
                )
            )

    # --------------------------------------
    # PENCARIAN DOKUMEN RAG
    # --------------------------------------

    hits = []

    if use_rag and rag_store:

        try:

            hits = rag_store.search(
                message,
                top_k=5
            )

            print(
                f"[RAG SEARCH] "
                f"Ditemukan {len(hits)} bagian dokumen."
            )

        except Exception as exc:

            print(
                "[RAG SEARCH ERROR]",
                repr(exc)
            )

            return jsonify({
                "error": (
                    "Pencarian dokumen gagal. "
                    "Periksa terminal Flask."
                )
            }), 500

    # --------------------------------------
    # MENYIAPKAN KONTEKS DOKUMEN
    # --------------------------------------

    system_instruction = SYSTEM_INSTRUCTION

    user_message = message

    if use_rag:
        system_instruction += "\n" + RAG_INSTRUCTION

    if hits:

        context_parts = []

        for number, hit in enumerate(
            hits,
            start=1
        ):

            source = hit.get(
                "filename",
                "Dokumen"
            )

            page = hit.get(
                "page",
                "-"
            )

            text = hit.get(
                "text",
                ""
            )

            context_parts.append(
                f"[{number}] "
                f"Sumber: {source}, halaman {page}\n"
                f"{text}"
            )

        context = "\n\n".join(context_parts)

        user_message = (
            "Gunakan informasi dari dokumen berikut "
            "untuk menjawab pertanyaan pengguna.\n\n"

            "KONTEKS DOKUMEN:\n"
            f"{context}\n\n"

            "PERTANYAAN PENGGUNA:\n"
            f"{message}"
        )

    elif use_rag:

        system_instruction += """

        Pencarian dokumen tidak menemukan bagian yang relevan.

        Jangan mengarang isi dokumen dan jangan mengaku telah
        menemukan jawabannya.

        Jelaskan kepada pengguna bahwa informasi yang diminta
        belum ditemukan dalam hasil pencarian dokumen.
        """

    # --------------------------------------
    # MENGIRIM PERTANYAAN KE GEMINI
    # --------------------------------------

    contents.append(
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(
                    text=user_message
                )
            ]
        )
    )

    try:

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.5,
                max_output_tokens=2048
            )
        )

        answer = (
            response.text or ""
        ).strip()

        if not answer:
            answer = (
                "Maaf, belum ada jawaban yang dihasilkan."
            )

        # ----------------------------------
        # MENYIAPKAN SUMBER JAWABAN
        # ----------------------------------

        sources = []

        for number, hit in enumerate(
            hits,
            start=1
        ):

            sources.append({
                "index": number,
                "source": hit.get(
                    "filename",
                    "Dokumen"
                ),
                "page": hit.get(
                    "page",
                    None
                ),
                "score": hit.get(
                    "score",
                    0
                ),
                "snippet": hit.get(
                    "text",
                    ""
                )[:300]
            })

        print(
            "[CHAT] RAG digunakan:",
            bool(hits)
        )

        return jsonify({
            "reply": answer,
            "sources": sources,
            "rag_used": bool(hits)
        })

    except Exception as exc:

        print(
            "[GEMINI ERROR]",
            repr(exc)
        )

        return jsonify({
            "error": (
                "Gagal menghubungi Gemini. "
                "Periksa API key, koneksi, dan terminal Flask."
            )
        }), 502


# ==========================================
# MENJALANKAN APLIKASI
# ==========================================

if __name__ == "__main__":

    sync_knowledge()

    url = "http://127.0.0.1:5001"

    threading.Timer(
        1.5,
        lambda: webbrowser.open_new(url)
    ).start()

    app.run(
        host="127.0.0.1",
        port=5001,
        debug=True,
        use_reloader=False
    )
