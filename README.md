# AI Building Vision Inspector (Class Practical #1)
**Fakultas Ilmu Komputer, Universitas Klabat (UNKLAB)**  
*Mata Kuliah: Artificial Intelligence (AI) | Topik: Pengenalan Objek di Dalam Bangunan*

Aplikasi web modern untuk demonstrasi, evaluasi, dan pelaporan ilmiah kemampuan vision Large Language Model (VLM/LLM) dalam mendeteksi dan menginspeksi elemen interior bangunan kampus UNKLAB, berkolaborasi dengan mahasiswa Arsitektur sebagai *domain expert*.

---

## 🚀 Cara Menjalankan Aplikasi

### 1. Prasyarat
- Python 3.9+ (Sudah teruji di Python 3.11)
- Endpoint LLM Vision aktif (otomatis membaca konfigurasi dari `.env`, default: proxy 9router `http://localhost:20128/v1` dengan model `ag/gemini-3.8-flash-high` atau Google Gemini API).

### 2. Menjalankan Server
Cukup jalankan perintah berikut di root folder `D:\collage\AI\classPractical2`:

```bash
python run.py
```

Buka peramban (browser) di:
- **Dashboard Aplikasi:** [http://localhost:8000](http://localhost:8000)
- **Dokumentasi API Swagger:** [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Menjalankan Automated Test Suite
Untuk memastikan seluruh modul (Verifikasi 4 Kategori, Parsing JSON, API Endpoints) berfungsi valid:

```bash
python -m pytest tests/ -v
```

---

## 🛠️ Alur Kerja Eksperimen (5 Langkah Sesuai Lecture 9)

1. **Input Citra Interior Kampus:**
   - Unggah foto ruang kelas, koridor, lab komputer, atau lobi kampus UNKLAB.
   - Atau gunakan tombol **Live Webcam** untuk mengambil foto langsung dari kamera laptop di dalam ruangan.
   - Tentukan tag kualitas gambar: `Normal`, `Low-Light (Redup)`, `Blur`, atau `Low-Resolution` (menjawab **Pertanyaan Analisis #8**).
2. **Pencatatan Blind Ground Truth (Arsitek):**
   - Sebelum LLM dijalankan, mahasiswa Arsitektur mencatat daftar objek aktual di ruangan beserta material arsitektural (kayu solid, beton, keramik, gypsum) dan kondisi fisiknya (baik, aus, retak, kotor).
   - Pendekatan *blind pre-inspection* ini menjamin objektivitas pengujian tanpa bias konfirmasi.
3. **Eksekusi Vision LLM:**
   - Pilih preset prompt:
     - **Structured JSON (Rekomendasi):** Menghasilkan JSON murni terstruktur.
     - **Architectural Domain:** Meminta estimasi material, kerusakan, dan kualitas pencahayaan.
     - **Generic Prompt:** Menanyakan objek secara umum (menjawab **Pertanyaan Analisis #9**).
   - Klik **"Analisis Gambar dengan Gemini Vision"**.
4. **Verifikasi Human vs AI (4 Kategori):**
   - Sistem secara otomatis mencocokkan prediksi LLM terhadap Ground Truth menggunakan *similarity matching engine* dan mengklasifikasikannya ke dalam:
     - **Correct Detection:** Objek nyata terdeteksi tepat oleh LLM.
     - **Missed Detection:** Objek nyata ada di ruangan tetapi terlewat oleh LLM.
     - **False Detection:** Objek halusinasi (tidak ada di Ground Truth tetapi diklaim LLM).
     - **Misclassification:** Objek terdeteksi tetapi salah label kelas atau material.
   - Status dapat disesuaikan secara manual jika mahasiswa arsitektur ingin mengoreksi.
5. **Dashboard 10 Pertanyaan Analisis & Export:**
   - Buka tab **"10 Analysis Questions & Metrik"**.
   - Sistem secara otomatis merangkum metrik agregat dan menyusun draf jawaban untuk 10 Pertanyaan Analisis wajib dari Lecture 9.
   - Klik **"Export Markdown (.md)"** atau **"Export CSV (.csv)"** untuk langsung melampirkan hasil ke laporan praktikum.

---

## 📂 Struktur Proyek

```
classPractical2/
├── app/
│   ├── main.py              # FastAPI server, REST API, & static route
│   ├── db.py                # Database SQLite WAL mode & schema tables
│   ├── vision_client.py     # Client LLM Vision, prompt presets, & JSON parser
│   ├── verification.py      # Matching engine 4 kategori (Lecture 9)
│   ├── static/
│   │   └── index.html       # Web UI Dashboard modern (Tailwind + Vanilla JS)
│   ├── uploads/             # Direktori penyimpanan citra eksperimen
│   └── exports/             # Direktori laporan ekspor
├── tests/
│   ├── test_api.py          # Unit test FastAPI endpoints
│   ├── test_verification.py # Unit test algoritma 4 kategori evaluasi
│   └── test_vision_client.py# Unit test parser JSON & fallback
├── gemini-demo-vision/      # Script starter desktop dosen (OpenCV Tkinter)
├── .env                     # Konfigurasi model & endpoint API
├── requirements.txt         # Daftar dependensi Python
├── run.py                   # Script eksekusi aplikasi satu langkah
└── README.md                # Dokumentasi petunjuk teknis
```
