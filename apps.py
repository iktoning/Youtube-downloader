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

# ---------- module-level helper ----------
def clean_ansi(text: str) -> str:
    ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)

class ModernDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YouTube Downloader by Ramapuspa_")
        self.geometry("750x650")
        self.resizable(False, False)

        self.frame = ctk.CTkFrame(self, corner_radius=20)
        self.frame.pack(pady=20, padx=20, fill="both", expand=True)

        self.label_title = ctk.CTkLabel(self.frame, text="Youtube Downloader", font=("Segoe UI", 28, "bold"))
        self.label_title.pack(pady=15)

        # URL entry
        self.url_entry = ctk.CTkEntry(self.frame, placeholder_text="Masukkan URL YouTube...", height=40, width=500)
        self.url_entry.pack(pady=10)
        self.url_entry.bind("<KeyRelease>", self.schedule_resolution_fetch)
        self.fetch_timer = None

        # Resolution dropdown
        self.resolution = ctk.CTkOptionMenu(self.frame, values=["Otomatis"], width=200)
        self.resolution.pack(pady=10)

        # Path info
        self.path_label = ctk.CTkLabel(self.frame, text="Folder belum dipilih", text_color="gray80")
        self.path_label.pack(pady=5)

        self.folder_button = ctk.CTkButton(self.frame, text="Pilih Folder", command=self.choose_folder)
        self.folder_button.pack(pady=5)

        # Show progress?
        self.progress_enabled = ctk.CTkCheckBox(self.frame, text="Tampilkan Progress")
        self.progress_enabled.select()
        self.progress_enabled.pack(pady=5)

        # Progress bar
        self.progress = ctk.CTkProgressBar(self.frame, width=420)
        self.progress.set(0)
        self.progress.pack(pady=5)

        # Progress percentage label
        self.progress_label = tk.Label(self.frame, bg="#1e1e1e", fg="white", font=("Segoe UI", 10), text="0%")
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

    # ---------------------------------------
    def log(self, msg):
        # use module-level cleaner to avoid attribute errors when called from different contexts
        clean = clean_ansi(str(msg))
        try:
            self.log_panel.insert("end", clean + "\n")
            self.log_panel.see("end")
        except Exception:
            # if log_panel isn't available for some reason, fallback to printing
            print(clean)

    # ---------------------------------------
    def schedule_resolution_fetch(self, event=None):
        # you previously used a tiny after delay (10ms) — keep that but avoid overlapping calls
        if self.fetch_timer:
            self.after_cancel(self.fetch_timer)
            self.fetch_timer = None
        # call quickly (near-instant)
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
            # show actual exception in log to help debugging
            self.log(f"Gagal mengambil resolusi! ({e})")

    # ---------------------------------------
    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.download_path = folder
            self.path_label.configure(text=folder, text_color="white")

    # ---------------------------------------
    def progress_hook(self, d):
        try:
            if d.get("status") == "downloading":
                downloaded = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate")

                if total:
                    percent = downloaded / total
                    # clamp percent to [0,1]
                    percent = max(0.0, min(1.0, percent))
                    self.progress.set(percent)
                    self.progress_label.config(text=f"{percent*100:.1f}%")

            elif d.get("status") == "finished":
                self.progress.set(1)
                self.progress_label.config(text="100%")
                self.log("Menggabungkan audio + video...")
        except Exception as ex:
            # never let progress hook crash the downloader
            self.log(f"Progress hook error: {ex}")

    # ---------------------------------------
    def start_download(self):
        threading.Thread(target=self.download_video, daemon=True).start()

    # ---------------------------------------
    def download_video(self):
        url = self.url_entry.get().strip()
        quality = self.resolution.get()

        if not self.download_path:
            messagebox.showerror("Error", "Pilih folder terlebih dahulu!")
            return

        self.progress.set(0)
        self.progress_label.config(text="0%")
        self.log("Mengambil metadata video...")

        # safe output template (use folder)
        outtmpl = os.path.join(self.download_path, "%(title)s.%(ext)s")

        # -----------------------------
        # FORMAT FIX — AUDIO ALWAYS WORK
        # -----------------------------
        if quality != "Otomatis":
            h = quality.replace("p", "")
            video_format = (
                f"bv*[ext=mp4][height<={h}]/"
                f"bv*[height<={h}]"
            )
        else:
            video_format = "bv*[ext=mp4]/bv*"

        audio_format = "bestaudio[ext=m4a]/bestaudio"

        ydl_opts = {
            "format": f"{video_format}+{audio_format}/best",
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
            "nocheckcertificate": True,
        }

        if self.progress_enabled.get() == 1:
            ydl_opts["progress_hooks"] = [self.progress_hook]

        try:
            self.log("Memulai download...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

            # Ambil nama file yang dihasilkan
            out_file = None
            try:
                out_file = info.get("requested_downloads", [{}])[0].get("filepath")
            except Exception:
                out_file = None

            if not out_file:
                matches = sorted(
                    glob.glob(os.path.join(self.download_path, "*.mp4")),
                    key=os.path.getmtime,
                    reverse=True
                )
                if matches:
                    out_file = matches[0]

            has_audio = True
            if out_file and shutil.which("ffprobe"):
                try:
                    cmd = [
                        "ffprobe", "-v", "error", "-select_streams", "a",
                        "-show_entries", "stream=codec_name",
                        "-of", "default=noprint_wrappers=1:nokey=1",
                        out_file
                    ]
                    p = subprocess.run(cmd, capture_output=True, text=True)
                    has_audio = bool(p.stdout.strip())
                except Exception:
                    has_audio = True

            # -----------------------------
            # FALLBACK JIKA MP4 TIDAK ADA AUDIO
            # -----------------------------
            if not has_audio:
                self.log("Tidak ada audio — melakukan konversi OPUS → AAC...")

                tmp_audio = os.path.join(self.download_path, "__tmp_audio__.webm")
                tmp_aac = os.path.join(self.download_path, "__tmp_audio__.aac")

                # Download audio asli (OPUS)
                ydl_audio_opts = {"format": "bestaudio", "outtmpl": tmp_audio}
                with yt_dlp.YoutubeDL(ydl_audio_opts) as ydl:
                    ydl.download([url])

                # Convert OPUS → AAC
                cmd_convert = [
                    "ffmpeg", "-y",
                    "-i", tmp_audio,
                    "-c:a", "aac",
                    "-b:a", "192k",
                    tmp_aac
                ]
                subprocess.run(cmd_convert, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                # Merge video + AAC (pasti supported)
                merged = out_file.replace(".mp4", "_merged.mp4")
                cmd_merge = [
                    "ffmpeg", "-y",
                    "-i", out_file,
                    "-i", tmp_aac,
                    "-c:v", "copy",
                    "-c:a", "aac",
                    merged
                ]
                subprocess.run(cmd_merge, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

                # Replace output file
                try:
                    os.remove(out_file)
                except Exception:
                    pass
                try:
                    os.remove(tmp_audio)
                except Exception:
                    pass
                try:
                    os.remove(tmp_aac)
                except Exception:
                    pass
                try:
                    os.replace(merged, out_file)
                except Exception:
                    pass

                self.log("Audio OPUS berhasil dikonversi → AAC")
                self.log("Fallback merge selesai.")

            self.progress.set(1)
            self.progress_label.config(text="100%")
            self.log("Download selesai ✔")

        except Exception as e:
            self.log(f"ERROR: {e}")
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    app = ModernDownloader()
    app.mainloop()