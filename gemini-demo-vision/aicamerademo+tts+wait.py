import os
import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap import Style
from PIL import Image, ImageTk
import cv2
import base64
import json
import requests
import threading
import tempfile
import time
import pygame
from gtts import gTTS

# 9router API Key — loaded from environment, never hardcoded.
# Set via:  $env:VISION_API_KEY="sk-..."  (PowerShell)
# or export VISION_API_KEY="sk-..."       (bash/WSL)
# Optionally copy project .env pattern: VISION_API_KEY, VISION_MODEL, VISION_BASE_URL
API_KEY = os.environ.get("VISION_API_KEY", "")

# 9router OpenAI-compatible endpoint
MODEL_NAME = os.environ.get("VISION_MODEL", "ag/gemini-3.8-flash-high")
OPENROUTER_URL = os.environ.get("VISION_BASE_URL", "http://localhost:20128/v1") + "/chat/completions"

class AICameraAnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Camera Analyzer")
        self.root.geometry("1180x720")
        self.root.resizable(False, False)  # Disable maximize window
        self.style = Style("darkly")
        self.cap = None
        self.current_frame = None
        self.auto_mode = False

        self.build_ui()

    def build_ui(self):
        container = ttk.Frame(self.root, padding=10)
        container.pack(fill="both", expand=True)

        self.left_panel = ttk.Frame(container)
        self.left_panel.pack(side="left", padx=10, pady=10)

        self.right_panel = ttk.Frame(container)
        self.right_panel.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        # Camera Display
        self.video_label = ttk.Label(
            self.left_panel,
            text="Camera is not active\nClick the camera button to start",
            anchor="center",
            bootstyle="inverse-secondary"
        )
        self.video_label.pack(pady=(10, 5))

        self.status_label = ttk.Label(self.left_panel, text="● Camera Inactive", bootstyle="danger")
        self.status_label.pack()

        button_frame = ttk.Frame(self.left_panel)
        button_frame.pack(pady=10)

        self.start_button = tk.Button(
            button_frame,
            text="📷 Start Camera",
            font=("Segoe UI", 11, "bold"),
            bg="#1f9d55",
            fg="white",
            activebackground="#38d39f",
            activeforeground="white",
            relief="solid",
            bd=2,
            padx=15,
            pady=8,
            command=self.start_camera,
            cursor="hand2"
        )
        self.start_button.pack(side="left", padx=5)

        self.analyze_button = tk.Button(
            button_frame,
            text="⚡ Analyze",
            font=("Segoe UI", 11, "bold"),
            bg="#343a40",
            fg="white",
            activebackground="#495057",
            activeforeground="white",
            relief="solid",
            bd=2,
            padx=15,
            pady=8,
            command=self.capture_and_analyze,
            cursor="hand2"
        )
        self.analyze_button.pack(side="left", padx=5)

        # Prompt & Response
        ttk.Label(self.right_panel, text="Instruction:", bootstyle="info").pack(anchor="w")
        self.prompt_text = tk.Text(self.right_panel, height=4, font=("Segoe UI", 14))
        self.prompt_text.insert("1.0", "Apa yang kamu lihat sekarang?")
        self.prompt_text.pack(fill="x", pady=(0, 10))

        ttk.Label(self.right_panel, text="Response:", bootstyle="info").pack(anchor="w")
        self.response_text = tk.Text(
            self.right_panel,
            height=12,
            bg="#1e1e2f",
            fg="#00ffaa",
            insertbackground="white",
            font=("Consolas", 13)
        )
        self.response_text.insert("1.0", "Analysis results will appear here...")
        self.response_text.pack(fill="both", expand=True, pady=(0, 10))

        interval_frame = ttk.Frame(self.right_panel)
        interval_frame.pack(anchor="w", pady=5)

        ttk.Label(interval_frame, text="Interval between 2 requests:").pack(side="left")
        self.interval_spin = ttk.Spinbox(interval_frame, from_=1, to=60, width=5)
        self.interval_spin.set(5)
        self.interval_spin.pack(side="left", padx=5)

        self.auto_button = ttk.Button(interval_frame, text="Start Auto", bootstyle="success", command=self.toggle_auto)
        self.auto_button.pack(side="left", padx=5)

    def start_camera(self):
        if self.cap and self.cap.isOpened():
            return

        try:
            self.cap = cv2.VideoCapture(0, cv2.CAP_MSMF)
        except Exception as error:
            self.cap = None
            self.status_label.config(text="● Camera Error", bootstyle="danger")
            self.video_label.configure(image="", text=f"Camera error:\n{error}")
            return

        if not self.cap.isOpened():
            self.cap.release()
            self.cap = None
            self.status_label.config(text="● Camera Failed", bootstyle="danger")
            self.video_label.configure(
                image="",
                text="Camera tidak dapat dibuka.\nTutup aplikasi lain yang memakai kamera."
            )
            return

        self.status_label.config(text="● Camera Active", bootstyle="success")
        self.update_frame()

    def update_frame(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                self.current_frame = frame
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(rgb)
                imgtk = ImageTk.PhotoImage(image=img.resize((800, 560)))  # Enlarged camera frame
                self.video_label.imgtk = imgtk
                self.video_label.configure(image=imgtk, text="")
            else:
                self.status_label.config(text="● Camera Read Failed", bootstyle="danger")
                self.video_label.configure(
                    image="",
                    text="Camera terbuka, tetapi frame tidak terbaca.\nPeriksa izin kamera Windows."
                )
                self.cap.release()
                self.cap = None
        if self.cap and self.cap.isOpened():
            self.root.after(10, self.update_frame)

    def capture_and_analyze(self):
        prompt = self.prompt_text.get("1.0", "end").strip()
        if self.current_frame is None:
            self.response_text.insert("1.0", "No camera frame found.")
            return

        frame = self.current_frame.copy()
        self.analyze_button.config(state="disabled")
        threading.Thread(target=self.analyze_image, args=(prompt, frame), daemon=True).start()

    def analyze_image(self, prompt, frame):
        _, buffer = cv2.imencode('.jpg', frame)
        image_bytes = buffer.tobytes()
        base64_img = base64.b64encode(image_bytes).decode()

        payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Short response. " + prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_img}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 500,
            "stream": False
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}"
        }
        try:
            res = requests.post(
                OPENROUTER_URL,
                headers=headers,
                json=payload,
                timeout=60
            )
            res.raise_for_status()
            try:
                response_data = res.json()
            except requests.exceptions.JSONDecodeError:
                if res.headers.get("Content-Type", "").startswith("text/event-stream"):
                    response_parts = []
                    for line in res.text.splitlines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            continue
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            response_parts.append(delta.get("content", ""))
                        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                            continue

                    result = "".join(response_parts).strip()
                    if not result:
                        result = "[API Error] SSE response tidak berisi content."
                else:
                    body = res.text.strip()
                    result = (
                        f"[API Error] Server returned non-JSON response "
                        f"(HTTP {res.status_code}, {res.headers.get('Content-Type', 'unknown')}).\n"
                        f"{body[:500] or '[empty response]'}"
                    )
            else:
                result = response_data["choices"][0]["message"]["content"]
        except Exception as e:
            result = f"[Error] {str(e)}"

        # Tampilkan hasil di UI
        self.response_text.delete("1.0", "end")
        self.response_text.insert("1.0", result)
        self.analyze_button.config(state="normal")

        # TTS pakai thread
        threading.Thread(target=self.play_tts_and_continue, args=(result,), daemon=True).start()

    def play_tts_and_continue(self, text):
        try:
            tts = gTTS(text=text, lang='id')
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                temp_file = fp.name
                tts.save(temp_file)

            pygame.mixer.init()
            pygame.mixer.music.load(temp_file)
            pygame.mixer.music.play()

            # tunggu sampai selesai bicara
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)

            pygame.mixer.music.stop()
            time.sleep(0.3)

        except Exception as e:
            print("TTS Error:", e)

        # lanjut auto loop
        if self.auto_mode:
            delay = int(self.interval_spin.get()) * 1000
            self.root.after(delay, self.run_auto_loop)

    def toggle_auto(self):
        self.auto_mode = not self.auto_mode
        if self.auto_mode:
            self.auto_button.config(text="Stop Auto", bootstyle="danger")
            self.run_auto_loop()
        else:
            self.auto_button.config(text="Start Auto", bootstyle="success")

    def run_auto_loop(self):
        if self.auto_mode:
            self.capture_and_analyze()

    def __del__(self):
        if self.cap and self.cap.isOpened():
            self.cap.release()


if __name__ == "__main__":
    root = tk.Tk()
    app = AICameraAnalyzerApp(root)
    root.mainloop()
