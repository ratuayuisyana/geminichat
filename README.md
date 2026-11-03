# Gemini Chatbot Website

Chatbot AI umum berbasis website menggunakan Flask (Python) dan Google Gemini API.

## 1. Persiapan
- Python 3.10 atau lebih baru
- Koneksi internet
- API key dari Google AI Studio: https://aistudio.google.com/app/apikey

**Keamanan:** API key yang sebelumnya pernah dibagikan sebaiknya dicabut/revoke. Buat key baru dan simpan hanya di file `.env`. Jangan mengirim file `.env` ke orang lain atau mengunggahnya ke GitHub.

## 2. Buka proyek di VS Code
Ekstrak ZIP, lalu buka folder `gemini-chatbot-website` melalui VS Code.

## 3. Buat virtual environment
Buka Terminal di VS Code, lalu jalankan:

### Windows
```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

Jika PowerShell menolak aktivasi, gunakan Command Prompt:
```cmd
.venv\Scripts\activate.bat
```

## 4. Instal library
```bash
python -m pip install -r requirements.txt
```

## 5. Atur API key
Salin `.env.example` menjadi `.env`.

Windows PowerShell:
```powershell
Copy-Item .env.example .env
```

Buka file `.env`, lalu isi:
```env
GEMINI_API_KEY=API_KEY_BARU_ANDA
GEMINI_MODEL=gemini-2.5-flash
```
Jangan beri tanda kutip dan jangan menulis `GEMINI_API_KEY=` dua kali. Jika model tersebut tidak tersedia pada akun/region Anda, ganti `GEMINI_MODEL` dengan nama model Gemini yang tersedia di Google AI Studio.

## 6. Jalankan website
```bash
python app.py
```
Buka browser ke:
http://127.0.0.1:5000

Biarkan terminal tetap berjalan selama website digunakan. Tekan `Ctrl+C` di terminal untuk menghentikan server.

## 7. Struktur folder
```text
gemini-chatbot-website/
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── templates/
│   └── index.html
└── static/
    ├── app.js
    └── style.css
```

## 8. Jika terjadi error
- `API key belum diatur`: pastikan nama file tepat `.env` (bukan `.env.txt`) dan key sudah diisi.
- `API key invalid`: buat key baru di Google AI Studio dan periksa penyalinannya.
- `quota` / `429`: batas penggunaan API tercapai; periksa kuota dan billing pada akun Google AI Studio/Cloud.
- Model tidak ditemukan: periksa nama model yang tersedia dan ubah `GEMINI_MODEL` di `.env`.
- `ModuleNotFoundError`: aktifkan virtual environment lalu jalankan `python -m pip install -r requirements.txt` lagi.

## Catatan
Ini adalah starter project lokal untuk pembelajaran. Sebelum dipublikasikan ke internet, tambahkan autentikasi, pembatasan penggunaan (rate limiting), proteksi abuse, logging yang aman, dan konfigurasi deployment production. Jangan gunakan Flask debug server untuk production.
