# PRD — Sistem Deteksi Objek Berbasis LLM (Vision) untuk Bangunan
**Class Practical — Mata Kuliah AI | Fakultas Ilmu Komputer, UNKLAB**
**Kolaborasi:** Tim Informatika × Mahasiswa Arsitek

---

## 1. Background

Tugas kelas AI mewajibkan pembuatan sistem yang menggunakan **LLM dengan vision capability** untuk mendeteksi objek pada gambar, dengan kolaborasi wajib bersama mahasiswa arsitek. Berdasarkan materi lecture (Class Activity #1 & #2), topik project sudah ditentukan dosen:

> **"Pengenalan Object di dalam bangunan"** — deteksi objek pada gambar interior bangunan.

Tugas ini terdiri dari dua tahap:
- **Activity #1** — Demo vision capability LLM untuk Object Detection + analisis manual (Correct/Missed/False Detection, Misclassification).
- **Activity #2** — Perbandingan ML (YOLO) vs LLM Vision pada gambar yang sama, dipresentasikan per kelompok.

## 2. Tujuan (Goals)

Selaras dengan Learning Objectives dari lecture:
1. Mendemonstrasikan kemampuan vision LLM mendeteksi objek pada gambar interior bangunan.
2. Membuat prompt efektif untuk mendapatkan informasi objek (termasuk kondisi, material, pencahayaan) dari sebuah gambar.
3. Melakukan verifikasi manual (ground truth) terhadap hasil deteksi LLM.
4. Menganalisis akurasi, kelemahan, dan limitasi LLM vision.
5. (Activity #2) Membandingkan hasil ML Object Detection vs LLM Vision pada input yang sama.

## 3. Scope

### In Scope
- Input berupa foto/gambar interior bangunan (kampus UNKLAB sebagai sumber data utama).
- Deteksi objek dasar (furnitur, elemen ruangan, dll) via LLM vision.
- **Deteksi tambahan via prompt saja** (bukan sistem terpisah): kondisi/kerusakan objek, material, kualitas pencahayaan.
- Proses verifikasi manual (ground truth) terhadap hasil LLM.
- Logging & tabel hasil deteksi untuk keperluan analisis.
- (Jika waktu memungkinkan / Activity #2) Perbandingan dengan model ML Object Detection (YOLO).

### Out of Scope (untuk versi ini)
- Real-time video detection (fokus pada gambar statis/foto).
- Training model ML custom dari nol (kalau Activity #2 dikerjakan, gunakan model YOLO pre-trained yang tersedia).
- Aplikasi mobile native (cukup web-based demo).

> Catatan tim: fitur "deteksi kerusakan / pencahayaan / material" **tidak menambah kompleksitas arsitektur** — semuanya cukup diatur lewat instruksi prompt ke LLM yang sama, bukan pipeline terpisah.

## 4. Stakeholders & Peran

| Peran | Tanggung Jawab |
|---|---|
| Tim Informatika | Bangun pipeline teknis (integrasi LLM API, backend, UI demo), desain prompt, logging hasil |
| Mahasiswa Arsitek | Definisikan objek/elemen relevan untuk didata, jadi domain expert saat bikin ground truth, validasi hasil deteksi (istilah material/kondisi yang benar secara arsitektural) |
| Dosen/Kelas | Menilai berdasarkan Analysis Questions + Discussion Conclusion (Activity #1) dan format presentasi kelompok (Activity #2) |

## 5. Arsitektur Sistem

```
┌─────────────────┐      ┌───────────────────────┐      ┌─────────────────┐
│ Input            │      │ LLM + Prompt tersetel │      │ Output          │
│ (kamera/gambar)  │─────▶│ (Gemini Vision API)   │─────▶│ (JSON terstruktur)│
└─────────────────┘      └───────────────────────┘      └─────────────────┘
                                                                    │
                                                                    ▼
                                                    ┌───────────────────────────┐
                                                    │ Ground Truth (manual, oleh │
                                                    │ tim + mhs arsitek)         │
                                                    └───────────────────────────┘
                                                                    │
                                                                    ▼
                                                    ┌───────────────────────────┐
                                                    │ Verifikasi & Logging:      │
                                                    │ Correct / Missed / False / │
                                                    │ Misclassification          │
                                                    └───────────────────────────┘
                                                                    │
                                                        (Activity #2, opsional)
                                                                    ▼
                                                    ┌───────────────────────────┐
                                                    │ Model ML (YOLO) — jalur    │
                                                    │ paralel untuk perbandingan │
                                                    └───────────────────────────┘
```

## 6. Functional Requirements

### FR-1: Image Input
- User dapat upload gambar atau ambil foto langsung via kamera (browser-based).
- Format didukung: JPG/PNG.

### FR-2: LLM Object Detection
- Sistem mengirim gambar + prompt ke Gemini Vision API (free tier — Gemini 1.5/2.0 Flash).
- Output berupa daftar objek terstruktur (idealnya JSON), berisi minimal: nama objek, deskripsi singkat.

### FR-3: Prompt tambahan (kondisi, material, pencahayaan)
- Prompt dapat dikonfigurasi untuk sekaligus meminta:
  - Kondisi/kerusakan objek (retak, aus, kotor, dll)
  - Material objek (kayu, beton, kaca, logam, dll)
  - Kualitas pencahayaan ruangan (terang/redup/merata/tidak merata)
- Semua ini satu request ke LLM yang sama — bukan pipeline terpisah (lihat §3 Scope).

### FR-4: Ground Truth Input
- Antarmuka sederhana untuk tim/mhs arsitek mencatat objek yang **sebenarnya ada** di gambar sebelum/sesudah menjalankan LLM (untuk menghindari bias).

### FR-5: Verifikasi Otomatis/Semi-otomatis
- Sistem membandingkan output LLM vs ground truth, mengkategorikan tiap objek ke:
  - Correct Detection
  - Missed Detection
  - False Detection
  - Misclassification

### FR-6: Logging & Riwayat
- Setiap hasil deteksi (gambar, prompt yang dipakai, output LLM, hasil verifikasi) disimpan untuk keperluan analisis dan laporan.

### FR-7 (Activity #2, opsional): Perbandingan ML vs LLM
- Jalankan model ML Object Detection (YOLO) pada gambar yang sama.
- Tampilkan hasil ML berdampingan dengan hasil LLM untuk perbandingan manual.

## 7. Non-Functional Requirements
- **Biaya:** gunakan tier gratis Gemini API (akun Google pribadi, bukan email UNKLAB — status billing "Unavailable" untuk email kampus).
- **Stack:** Node.js/TypeScript (sesuai preferensi tim), menggantikan contoh referensi dosen (PHP/XAMPP).
- **Performa:** tidak butuh real-time; cukup responsif untuk demo per-gambar (beberapa detik per request).
- **Portabilitas:** web-based, bisa dijalankan lokal untuk demo kelas.

## 8. Data Requirements
- Kumpulkan set gambar interior bangunan kampus (variasi: ruang kelas, koridor, lab, dll).
- Siapkan **ground truth** untuk tiap gambar sebelum eksperimen (dibuat manual, divalidasi mhs arsitek).
- Siapkan variasi kualitas gambar (resolusi rendah, blur, pencahayaan buruk) untuk menjawab pertanyaan analisis soal pengaruh kualitas gambar.
- Siapkan minimal 3 variasi prompt untuk gambar yang sama (generik, spesifik domain, terstruktur/JSON) untuk menjawab pertanyaan analisis soal pengaruh prompt.

## 9. Analysis & Evaluation (wajib dari lecture)

**Activity #1 — Analysis Questions:**
1. Berapa banyak objek terdeteksi LLM?
2. Apakah semua objek dalam gambar berhasil dideteksi?
3. Apakah ada Missed Detection?
4. Apakah ada False Detection?
5. Apakah ada Misclassification?
6. Objek apa yang paling mudah dikenali AI? Kenapa?
7. Objek apa yang paling sulit dikenali AI? Kenapa?
8. Bagaimana kualitas gambar memengaruhi hasil deteksi?
9. Bagaimana perubahan prompt memengaruhi hasil LLM?
10. Apa saja limitations of LLM Vision Capability?

**Activity #2 — Perbandingan ML vs LLM** (jika dikerjakan): kemampuan deteksi, pemahaman konteks, akurasi & kesalahan, kecepatan & kebutuhan komputasi — lihat kriteria lengkap di materi lecture.

## 10. Deliverables
- Aplikasi demo (web-based) yang menjalankan pipeline di §5.
- Dataset gambar + ground truth yang dipakai.
- Tabel/log hasil eksperimen (LLM, dan ML jika Activity #2 dikerjakan).
- Jawaban tertulis untuk 10 Analysis Questions + Discussion Conclusion.
- (Activity #2) Slide/presentasi kelompok sesuai format dari lecture (gambar, hasil ML, hasil LLM, perbedaan, kelebihan/keterbatasan, rekomendasi, kesimpulan).

## 11. Milestones (usulan)
1. **Setup** — API key Gemini, skeleton app Node.js/TypeScript, UI upload gambar.
2. **Data & Ground Truth** — kumpulkan gambar interior kampus + buat ground truth bersama mhs arsitek.
3. **Prompt Engineering** — desain & uji minimal 3 varian prompt.
4. **Eksperimen & Verifikasi** — jalankan LLM di semua gambar/prompt, isi tabel verifikasi.
5. **Analisis** — jawab 10 Analysis Questions berdasarkan data eksperimen (bukan asumsi).
6. **(Opsional) Activity #2** — tambahkan jalur ML (YOLO), bandingkan hasil.
7. **Presentasi** — susun laporan/slide sesuai format kelas.

## 12. Open Questions
- Siapa saja anggota tim yang final presentasi (ada indikasi kemungkinan 1 anggota tidak hadir)?
- Berapa banyak gambar/ruangan yang akan dijadikan sample eksperimen?
- Apakah Activity #2 (ML vs LLM) akan dikerjakan penuh, atau fokus dulu ke Activity #1?
