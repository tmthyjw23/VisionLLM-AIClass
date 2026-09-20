import os
import sqlite3
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# Vercel serverless has read-only filesystem except /tmp
if os.environ.get("VERCEL"):
    DB_PATH = Path("/tmp/vision_experiments.db")
else:
    DB_PATH = Path(__file__).resolve().parent.parent / "vision_experiments.db"

def get_connection() -> sqlite3.Connection:
    # Ensure parent dir exists for /tmp case
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass  # /tmp on Vercel may not support WAL
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_name TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        experiment_id INTEGER,
        filename TEXT NOT NULL,
        original_name TEXT NOT NULL,
        quality_tag TEXT NOT NULL DEFAULT 'normal',
        room_type TEXT DEFAULT 'Ruang Kelas',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS ground_truths (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_id INTEGER NOT NULL,
        object_name TEXT NOT NULL,
        category TEXT DEFAULT 'furnitur',
        material TEXT DEFAULT 'tidak diketahui',
        condition TEXT DEFAULT 'baik',
        location_note TEXT DEFAULT '',
        FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        image_id INTEGER NOT NULL,
        prompt_preset TEXT NOT NULL,
        prompt_text TEXT NOT NULL,
        raw_response TEXT,
        parsed_json TEXT,
        lighting_assessment TEXT,
        detected_objects_count INTEGER DEFAULT 0,
        model_name TEXT,
        duration_seconds REAL DEFAULT 0.0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        detection_id INTEGER NOT NULL,
        image_id INTEGER NOT NULL,
        ground_truth_id INTEGER,
        ground_truth_name TEXT,
        detected_name TEXT,
        status TEXT NOT NULL, -- 'correct', 'missed', 'false_detection', 'misclassified'
        similarity_score REAL DEFAULT 0.0,
        notes TEXT DEFAULT '',
        manually_edited INTEGER DEFAULT 0,
        FOREIGN KEY (detection_id) REFERENCES detections(id) ON DELETE CASCADE,
        FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
        FOREIGN KEY (ground_truth_id) REFERENCES ground_truths(id) ON DELETE SET NULL
    );
    """)
    conn.commit()
    conn.close()

def execute_query(query: str, params: tuple = ()) -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    rows = cursor.fetchall()
    result = [dict(row) for row in rows]
    conn.close()
    return result

def execute_insert(query: str, params: tuple = ()) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    last_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return last_id

def execute_update(query: str, params: tuple = ()) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    rowcount = cursor.rowcount
    conn.commit()
    conn.close()
    return rowcount
