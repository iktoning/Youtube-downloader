import customtkinter as ctk
import tkinter as tk
import threading
import yt_dlp
import os
import re
import subprocess
import glob
import shutil
import json
import time
from tkinter import filedialog, messagebox
from datetime import datetime

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

def clean_ansi(text: str) -> str:
    ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)

class ModernDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YouTube Downloader by Ramapuspa_")
        self.geometry("750x710")

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
        self.download_button.pack(pady=10)
        self.download_path = None
        
        # Cancel button
        self.cancel_flag = False
        self.ffmpeg_process = None
        self.ydl_instance = None
        self.cancel_button = ctk.CTkButton(
            self.frame, text="Cancel", height=42,
            font=("Segoe UI", 16, "bold"), fg_color="red", command=self.cancel_download
        )
        self.cancel_button.pack(pady=10)
        self.cancel_button.configure(state="disabled")
        
        # History button
        self.history_button = ctk.CTkButton(
            self.frame, text="Lihat History", height=42, 
            font=("Segoe UI", 16, "bold"), command=self.open_history_window
        )
        self.history_button.pack(pady=10)

    def log(self, msg):
        clean = clean_ansi(str(msg))
        try:
            self.log_panel.insert("end", clean + "\n")
            self.log_panel.see("end")
        except Exception:
            print(clean)
    
    def cancel_download(self):
        self.cancel_flag = True
        self.log("Membatalkan download...")
        # Abort yt-dlp if available
        try:
            if getattr(self, "ydl_instance", None):
                try:
                    self.ydl_instance._abort_download = True
                except Exception:
                    pass
        except Exception:
            pass
        # Terminate ffmpeg process if running
        try:
            if getattr(self, "ffmpeg_process", None):
                try:
                    self.ffmpeg_process.terminate()
                    self.ffmpeg_process.wait(timeout=2)
                except Exception:
                    try:
                        self.ffmpeg_process.kill()
                    except Exception:
                        pass
        except Exception:
            pass

        # Reset UI
        self.progress.set(0)
        self.progress_label.configure(text="Dibatalkan")
        self.download_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
    
    def save_history(self, title, url, resolution, size, output_path):
        history_file = "download_history.json"
        entry = {
            "title": title,
            "resolution": resolution,
            "size": size,
            "output_path": output_path,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        data = []
        # Baca file history
        if os.path.exists(history_file):
            try:
                with open(history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    data = [data]
                elif not isinstance(data, list):
                    # Backup file yang rusak atau reset
                    shutil.copy(history_file, history_file + ".bak")
                    data = []
            except Exception:
                # backup file corrupt lalu reset
                try:
                    shutil.copy(history_file, history_file + ".bak")
                except Exception:
                    pass
                data = []
                
        data.append(entry)
        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            self.log("History berhasil disimpan")
        except Exception as e:
            self.log(f"Gagal menyimpan history: {e}")
    
    def open_history_window(self):
        history_file = "download_history.json"
        win = ctk.CTkToplevel(self)
        win.title("Riwayat Download")
        win.geometry("700x520")
        
        win.transient(self)
        win.lift()
        win.focus()
        win.attributes("-topmost", True)
        win.after(300, lambda: win.attributes("-topmost", False))
        win.grab_set()
        
        title = ctk.CTkLabel(win, text="History Download", font=("Segoe UI", 25, "bold"))
        title.pack(pady=10)

        textbox = ctk.CTkTextbox(win, width=660, height=440)
        textbox.pack(padx=10, pady=6, fill="both", expand=True)

        if not os.path.exists(history_file):
            textbox.insert("end", "Belum ada history.")
            return

        try:
            with open(history_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Toleransi: jika data berupa dict -> ubah jadi list
            if isinstance(data, dict):
                data = [data]
            if not isinstance(data, list):
                textbox.insert("end", "Format history tidak valid. File di-backup dan di-reset.")
                try:
                    shutil.copy(history_file, history_file + ".bak")
                    with open(history_file, "w", encoding="utf-8") as f:
                        json.dump([], f)
                except Exception as e:
                    textbox.insert("end", f"\nGagal backup/reset file: {e}")
                return

            if len(data) == 0:
                textbox.insert("end", "Belum ada history.")
                return

            for item in reversed(data):  # tampilkan yang terbaru dulu
                # item mungkin tidak lengkap -> gunakan .get()
                textbox.insert("end", f"Judul        : {item.get('title','-')}\n")
                textbox.insert("end", f"Resolusi   : {item.get('resolution','-')}\n")
                textbox.insert("end", f"Ukuran     : {item.get('size','-')}\n")
                textbox.insert("end", f"Direktory  : {item.get('output_path','-')}\n")
                textbox.insert("end", f"Tanggal   : {item.get('date','-')}\n")
                textbox.insert("end", "-"*70 + "\n\n")

        except Exception as e:
            textbox.insert("end", f"Error membaca history: {e}")
            # backup file korup untuk diperiksa user
            try:
                shutil.copy(history_file, history_file + ".bak")
                self.log("File history korup, backup dibuat: " + history_file + ".bak")
            except Exception:
                pass

    def schedule_resolution_fetch(self, event=None):
        if self.fetch_timer:
            self.after_cancel(self.fetch_timer)
            self.fetch_timer = None
        # Fast call
        self.fetch_timer = self.after(200, self.fetch_resolutions)

    def fetch_resolutions(self):
        url = self.url_entry.get().strip()
        if not url:
            return

        self.log("Mengambil daftar resolusi...")

        try:
            ydl_opts = {"quiet": True, "nocheckcertificate": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
            resolution_map = {}
            for f in info["formats"]:
                height = f.get("height")
                if not height:
                    continue
                if height < 360:
                    continue

                size = f.get("filesize") or f.get("filesize_approx")
                if not size:
                    continue

                # Hanya pilih format MP4 atau jika tidak ada, pilih yg terbesar
                ext = f.get("ext")
                key = f"{height}p"

                if key not in resolution_map:
                    resolution_map[key] = (size, ext)
                else:
                    # Jika ada format MP4 → Prioritaskan
                    old_size, old_ext = resolution_map[key]

                    if ext == "mp4" and old_ext != "mp4":
                        resolution_map[key] = (size, ext)
                    else:
                        # Ambil ukuran paling besar
                        if size > old_size:
                            resolution_map[key] = (size, ext)

            result_list = []
            for res, (size, ext) in resolution_map.items():
                size_mb = size / (1024 * 1024)
                result_list.append((int(res.replace("p", "")), f"{res} (~{size_mb:.1f} MB)"))

            # Sort berdasarkan angka resolusi
            result_list.sort(key=lambda x: x[0])
            display_list = [x[1] for x in result_list]
            
            self.resolution.configure(values=["Otomatis"] + display_list)
            self.log("Menampilkan resolusi video")

        except Exception as e:
            self.log(f"Gagal mengambil resolusi! ({e})")

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.download_path = folder
            self.path_label.configure(text=folder, text_color="white")

    def progress_hook(self, d):
        try:
            # Jika user menekan cancel → hentikan dengan exception
            if getattr(self, "cancel_flag", False):
                raise Exception("Download dibatalkan oleh pengguna")

            if d.get("status") == "downloading":
                downloaded = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate")

                if total:
                    percent = downloaded / total
                    percent = max(0.0, min(1.0, percent))
                    # update UI di main thread 
                    self.progress.set(percent)
                    self.progress_label.configure(text=f"{percent*100:.1f}%")

            elif d.get("status") == "finished":
                self.progress.set(1)
                self.progress_label.configure(text="100%")
        except Exception as ex:
            # Biarkan exception naik sehingga yt-dlp menghentikan proses
            raise

    def start_download(self):
        self.cancel_flag = False
        self.ydl_instance = None
        self.ffmpeg_process = None
        self.download_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        threading.Thread(target=self.download_video, daemon=True).start()

    def download_video(self):
        video_path = None
        audio_path = None
        final_path = None
        err = None
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
            # 1. Format video + audio
            # ---------------------
            if quality != "Otomatis":
                h = re.findall(r"(\d+)p", quality)[0]
                video_format = f"bestvideo[height<={h}]"
            else:
                video_format = "bestvideo"

            audio_format = "140" 
            video_path = os.path.join(self.download_path, "__temp_video__.mp4") 
            audio_path = os.path.join(self.download_path, "__temp_audio__.m4a")
            
            # -------------------------------
            # 2. Download video (tanpa audio)
            # -------------------------------
            self.log("Mengunduh video...")

            ydl_video_opts = {
                "format": video_format,
                "outtmpl": video_path,
                "quiet": True,
                "nocheckcertificate": True,
                "progress_hooks" : [self.progress_hook],
            }

            with yt_dlp.YoutubeDL(ydl_video_opts) as ydl:
                self.ydl_instance = ydl
                try:
                    ydl.download([url])
                finally:
                    self.ydl_instance = None
            
            if self.cancel_flag:
                self.log("Download video dibatalkan.")
                return

            # ----------------------
            # 3. Download audio M4A
            # ----------------------
            self.log("Mengunduh audio...")

            ydl_audio_opts = {
                "format": audio_format,
                "outtmpl": audio_path,
                "quiet": True,
                "nocheckcertificate": True,
                "progress_hooks" : [self.progress_hook],
            }

            with yt_dlp.YoutubeDL(ydl_audio_opts) as ydl:
                self.ydl_instance = ydl
                try:
                    ydl.download([url])
                finally:
                    self.ydl_instance = None

            if self.cancel_flag:
                self.log("Download audio dibatalkan.")
                return

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

            self.ffmpeg_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # monitoring loop — cek cancel_flag
            while True:
                if self.ffmpeg_process.poll() is not None:
                    break
                if self.cancel_flag:
                    try:
                        self.ffmpeg_process.terminate()
                        self.ffmpeg_process.wait(timeout=2)
                    except Exception:
                        try: self.ffmpeg_process.kill()
                        except Exception: pass
                    self.log("Merge dihentikan.")
                    # cleanup
                    if final_path and os.path.exists(final_path):
                        try: os.remove(final_path)
                        except: pass
                    return
                
            time.sleep(0.2)
            self.ffmpeg_process = None

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
                self.log("Audio belum masuk! Mencoba perbaikan...")
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
                # monitor proc_fix agar bisa di-cancel juga
                while True:
                    if proc_fix.poll() is not None:
                        break
                    if self.cancel_flag:
                        try:
                            proc_fix.terminate()
                            proc_fix.wait(timeout=2)
                        except Exception:
                            try: proc_fix.kill()
                            except: pass
                        self.log("Perbaikan audio dibatalkan.")
                        if os.path.exists(fallback):
                            try: os.remove(fallback)
                            except: pass
                        return
                    time.sleep(0.2)
                
                try:
                    os.remove(final_path)
                    os.rename(fallback, final_path)
                    self.log("Perbaikan selesai. Audio berhasil ditambahkan.")
                except Exception as e:
                    self.log(f"Gagal mengganti file final: {e}")

            # ------------------------
            # 7. Hapus file sementara
            # ------------------------
            try:
                if video_path and os.path.exists(video_path):
                    os.remove(video_path)
            except Exception:
                pass
            try:
                if audio_path and os.path.exists(audio_path):
                    os.remove(audio_path)
            except Exception:
                pass
            
            # Simpan history
            try:
                file_size = os.path.getsize(final_path) / (1024*1024)
                size_str = f"{file_size:.1f} MB"
            except Exception:
                size_str = "-"

            self.save_history(
                title=title,
                url=url,
                resolution=quality,
                size=size_str,
                output_path=final_path
            )

            self.progress.set(1)
            self.progress_label.configure(text="100%")
            self.log("Download selesai ✔")
        
        except Exception as e:
            err = e
            # jika exception berasal dari cancel di progress_hook, sudah tercatat di log sebelumnya
            if self.cancel_flag:
                self.log("Download dibatalkan.")
            else:
                self.log(f"ERROR: {e}")
                try:
                    messagebox.showerror("Error", str(e))
                except Exception:
                    pass
        finally:
            # Cleanup file sementara jika ada (cek None dahulu)
            try:
                for p in (video_path, audio_path):
                    if p and os.path.exists(p):
                        try: os.remove(p)
                        except: pass
            except Exception:
                pass
            # Reset state proses dan UI
            try:
                self.ydl_instance = None
                if getattr(self, "ffmpeg_process", None):
                    try:
                        self.ffmpeg_process.terminate()
                    except Exception:
                        try: self.ffmpeg_process.kill()
                        except Exception: pass
                self.ffmpeg_process = None
            except Exception:
                pass
            # Reset tombol (pastikan selalu dijalankan)
            try:
                self.download_button.configure(state="normal")
                self.cancel_button.configure(state="disabled")
            except Exception:
                pass
            
if __name__ == "__main__":
    app = ModernDownloader()
    app.mainloop()