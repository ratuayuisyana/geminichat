import os
import threading
import webbrowser

from pathlib import Path
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Membaca file .env berdasarkan lokasi app.py
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()

client = genai.Client(api_key=API_KEY) if API_KEY else None

SYSTEM_INSTRUCTION = """
Kamu adalah asisten AI umum yang ramah, jelas, dan membantu.
Jawab dalam bahasa yang digunakan pengguna. Jika pengguna menggunakan bahasa Indonesia,
jawab dalam bahasa Indonesia. Berikan jawaban terstruktur dan jangan mengarang fakta.
Jika tidak yakin, katakan dengan jujur.
"""

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/health")
def health():
    return jsonify({"ok": True, "configured": bool(client), "model": MODEL_NAME})

@app.post("/api/chat")
def chat():
    if not client:
        return jsonify({
            "error": "API key belum diatur. Isi GEMINI_API_KEY di file .env lalu jalankan ulang aplikasi."
        }), 503

    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    history = data.get("history", [])

    if not message:
        return jsonify({"error": "Pesan tidak boleh kosong."}), 400
    if len(message) > 10000:
        return jsonify({"error": "Pesan terlalu panjang (maksimal 10.000 karakter)."}), 400
    if not isinstance(history, list):
        return jsonify({"error": "Format riwayat percakapan tidak valid."}), 400

    # Batasi riwayat agar permintaan tetap ringan. Hanya kirim role dan teks.
    contents = []
    for item in history[-20:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        text = item.get("text")
        if role in ("user", "model") and isinstance(text, str) and text.strip():
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=text[:10000])]
            ))

    contents.append(types.Content(
        role="user",
        parts=[types.Part.from_text(text=message)]
    ))

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.7,
                max_output_tokens=2048,
            ),
        )
        answer = (response.text or "").strip()
        if not answer:
            answer = "Maaf, AI belum menghasilkan jawaban. Silakan coba lagi."
        return jsonify({"reply": answer})
    except Exception as exc:
        # Jangan kirim detail internal/API key ke browser.
        print("Gemini API error:", repr(exc))
        return jsonify({
            "error": "Gagal menghubungi Gemini. Periksa API key, kuota, koneksi internet, dan nama model."
        }), 502

if __name__ == "__main__":
    url = "http://127.0.0.1:5000"

    # Membuka browser secara otomatis
    threading.Timer(
        1.5,
        lambda: webbrowser.open_new(url)
    ).start()

    # Menjalankan server
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=False
    )
