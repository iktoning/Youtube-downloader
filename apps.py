import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
import threading
import yt_dlp
import os
import re
import subprocess
import glob
import shutil

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

def clean_ansi(text: str) -> str:
    ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)

class ModernDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YouTube Downloader by Ramapuspa_")
        self.geometry("750x680")

        self.frame = ctk.CTkFrame(self, corner_radius=20)
        self.frame.pack(pady=20, padx=20, fill="both", expand=True)

        self.label_title = ctk.CTkLabel(self.frame, text="Youtube Downloader", font=("Segoe UI", 28, "bold"))
        self.label_title.pack(pady=15)

        # URL 
        self.url_entry = ctk.CTkEntry(self.frame, placeholder_text="Masukkan URL YouTube...", height=40, width=500)
        self.url_entry.pack(pady=10)
        self.url_entry.bind("<KeyRelease>", self.schedule_resolution_fetch)
        self.fetch_timer = None

        # Resolution selection
        self.resolution = ctk.CTkOptionMenu(self.frame, values=["Otomatis"], width=200)
        self.resolution.pack(pady=10)

        # Folder Selection
        self.path_label = ctk.CTkLabel(self.frame, text="Folder belum dipilih", text_color="gray80")
        self.path_label.pack(pady=5)
        self.folder_button = ctk.CTkButton(self.frame, text="Pilih Folder", command=self.choose_folder)
        self.folder_button.pack(pady=5)

        # Show progress box
        self.progress_enabled = ctk.CTkCheckBox(self.frame, text="Tampilkan Progress")
        self.progress_enabled.select()
        self.progress_enabled.pack(pady=5)

        # Progress bar
        self.progress = ctk.CTkProgressBar(self.frame, width=420)
        self.progress.set(0)
        self.progress.pack(pady=5)

        # Progress percentage label
        self.progress_label = ctk.CTkLabel(self.frame, font=("Segoe UI", 10), text="0%")
        self.progress_label.pack(pady=(0, 10))

        # Log panel
        self.log_panel = ctk.CTkTextbox(self.frame, width=500, height=200)
        self.log_panel.pack(pady=10)

        # Download button
        self.download_button = ctk.CTkButton(
            self.frame, text="Download", height=42,
            font=("Segoe UI", 16, "bold"), command=self.start_download
        )
        self.download_button.pack(pady=15)

        self.download_path = None

    def log(self, msg):
        clean = clean_ansi(str(msg))
        try:
            self.log_panel.insert("end", clean + "\n")
            self.log_panel.see("end")
        except Exception:
            print(clean)

    def schedule_resolution_fetch(self, event=None):
        if self.fetch_timer:
            self.after_cancel(self.fetch_timer)
            self.fetch_timer = None
        # call quickly 
        self.fetch_timer = self.after(10, self.fetch_resolutions)

    def fetch_resolutions(self):
        url = self.url_entry.get().strip()
        if not url:
            return

        self.log("Mengambil daftar resolusi...")

        try:
            ydl_opts = {"quiet": True, "nocheckcertificate": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            resolutions = set()
            for f in info["formats"]:
                h = f.get("height")
                if h and h >= 360:
                    resolutions.add(f"{h}p")

            resolutions = sorted(resolutions, key=lambda x: int(x.replace("p", "")))
            self.resolution.configure(values=["Otomatis"] + list(resolutions))

            self.log("Resolusi berhasil diperbarui.")
        except Exception as e:
            self.log(f"Gagal mengambil resolusi! ({e})")

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.download_path = folder
            self.path_label.configure(text=folder, text_color="white")

    def progress_hook(self, d):
        try:
            if d.get("status") == "downloading":
                downloaded = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate")

                if total:
                    percent = downloaded / total
                    percent = max(0.0, min(1.0, percent))
                    self.progress.set(percent)
                    self.progress_label.configure(text=f"{percent*100:.1f}%")

            elif d.get("status") == "finished":
                self.progress.set(1)
                self.progress_label.configure(text="100%")
        except Exception as ex:
            self.log(f"Progress hook error: {ex}")

    def start_download(self):
        threading.Thread(target=self.download_video, daemon=True).start()

    def download_video(self):
        url = self.url_entry.get().strip()
        quality = self.resolution.get()

        if not url:
            messagebox.showerror("Error", "URL tidak boleh kosong!")
            return

        if not self.download_path:
            messagebox.showerror("Error", "Pilih folder penyimpanan!")
            return

        self.log("Memulai proses download...")
        self.progress.set(0)
        self.progress_label.configure(text="0%")

        try:
            # ---------------------
            # Format video + audio
            # ---------------------
            if quality != "Otomatis":
                h = quality.replace("p", "")
                video_format = f"bestvideo[height<={h}]"
            else:
                video_format = "bestvideo"

            audio_format = "140"  

            # -------------------------------
            # 2. Download video (tanpa audio)
            # -------------------------------
            self.log("Mengunduh video...")
            video_path = os.path.join(self.download_path, "__temp_video__.mp4")

            ydl_video_opts = {
                "format": video_format,
                "outtmpl": video_path,
                "quiet": True,
                "nocheckcertificate": True,
            }

            if self.progress_enabled.get() == 1:
                ydl_video_opts["progress_hooks"] = [self.progress_hook]

            with yt_dlp.YoutubeDL(ydl_video_opts) as ydl:
                ydl.download([url])

            # ----------------------
            # 3. Download audio M4A
            # ----------------------
            self.log("Mengunduh audio...")
            audio_path = os.path.join(self.download_path, "__temp_audio__.m4a")

            ydl_audio_opts = {
                "format": audio_format,
                "outtmpl": audio_path,
                "quiet": True,
                "nocheckcertificate": True,
            }

            with yt_dlp.YoutubeDL(ydl_audio_opts) as ydl:
                ydl.download([url])

            # -----------------------------------------------
            # 4. Tentukan output file final berdasarkan judul
            # -----------------------------------------------
            self.log("Mengambil metadata judul video...")
            meta = yt_dlp.YoutubeDL({"quiet": True}).extract_info(url, download=False)
            title = re.sub(r'[\\/*?:"<>|]', "", meta["title"])
            final_path = os.path.join(self.download_path, f"{title}.mp4")

            # --------------------------------
            # 5. Gabungkan video + audio (AAC)
            # --------------------------------
            self.log("Menggabungkan video + audio...")

            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-b:a", "192k",
                final_path
            ]

            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # ----------------------------------
            # 6. Cek apakah final memiliki audio
            # ----------------------------------
            cmd_probe = [
                "ffprobe",
                "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                final_path
            ]
            probe = subprocess.run(cmd_probe, capture_output=True, text=True)
            has_audio = bool(probe.stdout.strip())

            if not has_audio:
                self.log("⚠ Audio belum masuk! Mencoba perbaikan...")
                # Fallback → Encode ulang audio
                fallback = final_path.replace(".mp4", "_fix.mp4")
                cmd_fix = [
                    "ffmpeg", "-y",
                    "-i", video_path,
                    "-i", audio_path,
                    "-c:v", "copy",
                    "-c:a", "aac",
                    fallback
                ]
                subprocess.run(cmd_fix, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                os.remove(final_path)
                os.rename(fallback, final_path)

                self.log("Perbaikan selesai ✔ Audio berhasil ditambahkan.")

            # ------------------------
            # 7. Hapus file sementara
            # ------------------------
            os.remove(video_path)
            os.remove(audio_path)

            self.progress.set(1)
            self.progress_label.configure(text="100%")
            self.log("Download selesai ✔")

        except Exception as e:
            self.log(f"ERROR: {e}")
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    app = ModernDownloader()
    app.mainloop()