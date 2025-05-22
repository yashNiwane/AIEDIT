import tkinter as tk
from tkinter import filedialog, messagebox
import os
from moviepy.editor import (
    VideoFileClip, vfx, TextClip, CompositeVideoClip,
    ImageClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips
)
from moviepy.audio.fx.all import audio_normalize
import google.generativeai as genai
import json
import re
from PIL import Image, ImageTk
import shutil
import cv2
import threading
import time

# --- UI Color Scheme ---
BG_COLOR = "#2E2E2E"
FG_COLOR_LIGHT = "#E0E0E0"
BUTTON_BG_COLOR = "#4A4A4A"
BUTTON_FG_COLOR = "#FFFFFF"
ACCENT_COLOR = "#007ACC"
STATUS_BG_COLOR = "#3B3B3B"
PREVIEW_BG_COLOR = "#1C1C1C"
ERROR_FG_COLOR = "#FF6B6B"
SUCCESS_FG_COLOR = "#76FF03"
WARNING_FG_COLOR = "#FFD700"
TIMELINE_BG = "#3C3C3C"
TIMELINE_TROUGH = "#5A5A5A"


def format_time(seconds):
    """Formats seconds into MM:SS or HH:MM:SS string."""
    if seconds is None: return "00:00"
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    else:
        return f"{m:02d}:{s:02d}"


class VideoEditorApp:
    def __init__(self, master):
        self.master = master
        master.title("Prompt-Based Video Editor")
        master.geometry("1000x800") # Increased height for timeline
        master.configure(bg=BG_COLOR)

        self.current_video_path = None
        self.original_video_path = None
        self.edit_count = 0
        self.undo_stack = []
        self.redo_stack = []

        self.preview_cap = None
        self.is_preview_playing = False
        self.preview_thread = None
        self.preview_fps = 30
        self.video_total_duration_sec = 0
        self.preview_label_width = 640 # Cache for performance
        self.preview_label_height = 480

        self.is_scrubbing = False # Flag for timeline interaction

        self.api_key = os.environ.get('GOOGLE_API_KEY')

        self._setup_ui()

        if not self.api_key:
            self.status_label.config(text="Warning: GOOGLE_API_KEY not found. AI features disabled.", fg=WARNING_FG_COLOR)
            print("Warning: GOOGLE_API_KEY environment variable not found. AI features disabled.")
        self.update_undo_redo_buttons()


    def _setup_ui(self):
        # --- Top Frame ---
        top_controls_frame = tk.Frame(self.master, bg=BG_COLOR, pady=10, padx=10)
        top_controls_frame.pack(fill=tk.X)
        # ... (Load, Path, Undo, Redo buttons as before) ...
        self.load_button = tk.Button(top_controls_frame, text="Load Video", command=self.load_video,
                                     bg=BUTTON_BG_COLOR, fg=BUTTON_FG_COLOR, relief=tk.FLAT, activebackground=ACCENT_COLOR)
        self.load_button.pack(side=tk.LEFT, padx=(0,5))
        self.video_path_label = tk.Label(top_controls_frame, text="No video loaded", relief=tk.SUNKEN, anchor=tk.W, padx=5,
                                         bg=BG_COLOR, fg=FG_COLOR_LIGHT, width=40)
        self.video_path_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.undo_button = tk.Button(top_controls_frame, text="Undo", command=self.undo_action,
                                     bg=BUTTON_BG_COLOR, fg=BUTTON_FG_COLOR, relief=tk.FLAT, activebackground=ACCENT_COLOR)
        self.undo_button.pack(side=tk.LEFT, padx=5)
        self.redo_button = tk.Button(top_controls_frame, text="Redo", command=self.redo_action,
                                     bg=BUTTON_BG_COLOR, fg=BUTTON_FG_COLOR, relief=tk.FLAT, activebackground=ACCENT_COLOR)
        self.redo_button.pack(side=tk.LEFT, padx=5)

        # --- Middle Frame ---
        middle_frame = tk.Frame(self.master, bg=BG_COLOR, padx=5, pady=5)
        middle_frame.pack(fill=tk.BOTH, expand=True)

        # Left Sub-Frame (Editing Controls)
        edit_controls_frame = tk.Frame(middle_frame, bg=BG_COLOR, padx=10)
        edit_controls_frame.pack(side=tk.LEFT, fill=tk.Y, anchor=tk.N)
        tk.Label(edit_controls_frame, text="Enter Editing Command:", bg=BG_COLOR, fg=FG_COLOR_LIGHT).pack(anchor=tk.W, pady=(0,2))
        self.edit_entry = tk.Entry(edit_controls_frame, width=40, bg=FG_COLOR_LIGHT, fg=BG_COLOR, insertbackground=BG_COLOR)
        self.edit_entry.pack(pady=5, fill=tk.X)
        self.apply_button = tk.Button(edit_controls_frame, text="Apply Edit", command=self.apply_edit,
                                      bg=ACCENT_COLOR, fg=BUTTON_FG_COLOR, relief=tk.FLAT, padx=10, activebackground="#005f9e")
        self.apply_button.pack(pady=10, fill=tk.X)
        self.export_button = tk.Button(edit_controls_frame, text="Export Video As...", command=self.export_video,
                                       bg=BUTTON_BG_COLOR, fg=BUTTON_FG_COLOR, relief=tk.FLAT, padx=10, activebackground=ACCENT_COLOR)
        self.export_button.pack(pady=10, fill=tk.X)


        # Right Sub-Frame (Preview Area)
        preview_area_frame = tk.Frame(middle_frame, bg=BG_COLOR)
        preview_area_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        tk.Label(preview_area_frame, text="Video Preview:", anchor=tk.N, bg=BG_COLOR, fg=FG_COLOR_LIGHT).pack(pady=(5,2))
        self.preview_label = tk.Label(preview_area_frame, bg=PREVIEW_BG_COLOR, relief=tk.SUNKEN)
        self.preview_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.preview_image_ref = None
        
        # Timeline
        self.timeline_scale = tk.Scale(preview_area_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                       showvalue=0, # We'll use a separate label for time
                                       sliderrelief=tk.FLAT,
                                       command=self.seek_from_timeline,
                                       bg=TIMELINE_BG, fg=FG_COLOR_LIGHT,
                                       troughcolor=TIMELINE_TROUGH, activebackground=ACCENT_COLOR,
                                       length=300, relief=tk.GROOVE, bd=1)
        self.timeline_scale.pack(fill=tk.X, padx=5, pady=(0,0))
        self.timeline_scale.bind("<ButtonPress-1>", self._on_timeline_press)
        self.timeline_scale.bind("<ButtonRelease-1>", self._on_timeline_release)


        # Playback Controls & Time Display Frame
        playback_and_time_frame = tk.Frame(preview_area_frame, bg=BG_COLOR)
        playback_and_time_frame.pack(fill=tk.X, pady=2)

        self.play_button = tk.Button(playback_and_time_frame, text="▶ Play", command=self.play_preview,
                                     bg=BUTTON_BG_COLOR, fg=BUTTON_FG_COLOR, relief=tk.FLAT, activebackground=ACCENT_COLOR)
        self.play_button.pack(side=tk.LEFT, padx=5)
        self.pause_button = tk.Button(playback_and_time_frame, text="❚❚ Pause", command=self.pause_preview,
                                      bg=BUTTON_BG_COLOR, fg=BUTTON_FG_COLOR, relief=tk.FLAT, activebackground=ACCENT_COLOR)
        self.pause_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = tk.Button(playback_and_time_frame, text="■ Stop", command=self.stop_preview,
                                     bg=BUTTON_BG_COLOR, fg=BUTTON_FG_COLOR, relief=tk.FLAT, activebackground=ACCENT_COLOR)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.time_display_label = tk.Label(playback_and_time_frame, text="00:00 / 00:00",
                                           bg=BG_COLOR, fg=FG_COLOR_LIGHT, padx=10)
        self.time_display_label.pack(side=tk.RIGHT)

        self.update_playback_buttons_state()


        # --- Bottom Frame (Status) ---
        status_frame = tk.Frame(self.master, relief=tk.SUNKEN, bd=1, bg=STATUS_BG_COLOR)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_label = tk.Label(status_frame, text="Welcome! Load a video to start.", anchor=tk.W, padx=5, pady=3,
                                     bg=STATUS_BG_COLOR, fg=FG_COLOR_LIGHT)
        self.status_label.pack(fill=tk.X)

    def _on_timeline_press(self, event):
        self.is_scrubbing = True
        if self.is_preview_playing:
            self.pause_preview() # Pause if playing, so user can scrub

    def _on_timeline_release(self, event):
        self.is_scrubbing = False
        # The command self.seek_from_timeline will be called automatically by Scale
        # due to value change. No need to call it explicitly here unless the command
        # is not triggered on release for some reason (it usually is).

    def seek_from_timeline(self, value_str):
        if not self.current_video_path or not self.is_scrubbing: # Only act if user is dragging
            return
        
        try:
            seek_time_sec = float(value_str)
            # Stop playback if active (should be paused by _on_timeline_press)
            # self.stop_preview(show_static_frame=False) # Stop completely
            self._update_static_preview_frame(target_time_sec=seek_time_sec)
        except ValueError:
            pass # Ignore if value is not a float yet (can happen during init)
        except Exception as e:
            print(f"Error seeking from timeline: {e}")


    def _ask_for_file(self, title, filetypes, placeholder_text_in_status="Please select a file..."):
        # ... (same as before) ...
        original_status = self.status_label.cget("text")
        original_fg = self.status_label.cget("fg")
        self.status_label.config(text=placeholder_text_in_status, fg=WARNING_FG_COLOR)
        self.master.update_idletasks()
        filepath = filedialog.askopenfilename(title=title, filetypes=filetypes)
        if not filepath:
            self.status_label.config(text=f"{title} selection cancelled.", fg=WARNING_FG_COLOR)
            return None
        self.status_label.config(text=f"File selected: {os.path.basename(filepath)}", fg=FG_COLOR_LIGHT)
        return filepath


    def update_playback_buttons_state(self):
        video_loaded = bool(self.current_video_path and os.path.exists(self.current_video_path))
        self.play_button.config(state=tk.NORMAL if video_loaded and not self.is_preview_playing else tk.DISABLED)
        self.pause_button.config(state=tk.NORMAL if self.is_preview_playing else tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL if video_loaded else tk.DISABLED) # Stop can be active if video loaded
        self.timeline_scale.config(state=tk.NORMAL if video_loaded else tk.DISABLED)


    def _update_static_preview_frame(self, video_path=None, target_time_sec=None):
        if self.is_preview_playing and target_time_sec is not None: # If seeking while playing, stop playback.
            self.stop_preview(show_static_frame=False)

        target_path = video_path if video_path else self.current_video_path

        if not target_path or not os.path.exists(target_path):
            self.preview_label.config(image='', text="No video loaded or preview unavailable", fg=FG_COLOR_LIGHT)
            self.preview_label.image = None
            self.time_display_label.config(text="00:00 / 00:00")
            if hasattr(self, 'timeline_scale'): self.timeline_scale.set(0)
            self.update_playback_buttons_state()
            return

        cap = None
        try:
            cap = cv2.VideoCapture(target_path)
            if not cap.isOpened():
                self.preview_label.config(image='', text="Error opening video for preview", fg=ERROR_FG_COLOR)
                self.preview_label.image = None
                return

            current_fps = cap.get(cv2.CAP_PROP_FPS)
            if current_fps == 0: current_fps = self.preview_fps # Fallback

            # Get total duration if not already set for this video (e.g., on first load for this path)
            # This check is a bit simplistic, ideally, self.video_total_duration_sec should be tied to current_video_path
            if self.video_total_duration_sec == 0 or video_path: # Recalculate if new video path
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                self.video_total_duration_sec = total_frames / current_fps if current_fps > 0 else 0
                self.timeline_scale.config(to=self.video_total_duration_sec if self.video_total_duration_sec > 0 else 100)


            seek_pos_msec = 0
            if target_time_sec is not None:
                seek_pos_msec = int(target_time_sec * 1000)
                cap.set(cv2.CAP_PROP_POS_MSEC, seek_pos_msec)
            else: # Default: show frame around 1s or midpoint
                default_seek_time_sec = min(1.0, self.video_total_duration_sec / 2.0) if self.video_total_duration_sec > 0.1 else 0.0
                seek_pos_msec = int(default_seek_time_sec * 1000)
                cap.set(cv2.CAP_PROP_POS_MSEC, seek_pos_msec)
            
            current_display_time_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

            ret, frame = cap.read()

            if not ret or frame is None:
                self.preview_label.config(image='', text="Could not read frame for preview", fg=ERROR_FG_COLOR)
                self.preview_label.image = None
                return

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)

            # Use cached dimensions for resizing if available, otherwise calculate
            self.preview_label.update_idletasks() # Ensure winfo is correct
            self.preview_label_width = self.preview_label.winfo_width() -10
            self.preview_label_height = self.preview_label.winfo_height() -10
            if self.preview_label_width <=1 : self.preview_label_width = 640
            if self.preview_label_height <=1 : self.preview_label_height = 480
            
            img.thumbnail((self.preview_label_width, self.preview_label_height), Image.Resampling.LANCZOS)
            self.preview_image_ref = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self.preview_image_ref, text="")
            self.preview_label.image = self.preview_image_ref
            
            # Update timeline and time display
            if not self.is_scrubbing: # Don't fight user dragging the scale
                 self.timeline_scale.set(current_display_time_sec)
            self.time_display_label.config(text=f"{format_time(current_display_time_sec)} / {format_time(self.video_total_duration_sec)}")
            # self.status_label.config(text="Preview updated.", fg=FG_COLOR_LIGHT) # Keep for more specific messages

        except Exception as e:
            error_msg = f"Error static preview: {str(e)[:100]}"
            self.status_label.config(text=error_msg, fg=ERROR_FG_COLOR)
            self.preview_label.config(image='', text="Preview Error", fg=ERROR_FG_COLOR)
            self.preview_label.image = None
            print(f"Full static preview error details: {e}")
        finally:
            if cap: cap.release()
            self.update_playback_buttons_state()


    def play_preview(self):
        if self.is_preview_playing: return
        if not self.current_video_path or not os.path.exists(self.current_video_path):
            self.status_label.config(text="No video loaded to play.", fg=WARNING_FG_COLOR)
            return

        self.stop_preview(show_static_frame=False) # Ensure any previous state is cleared, but don't show static frame yet

        try:
            self.preview_cap = cv2.VideoCapture(self.current_video_path)
            if not self.preview_cap.isOpened():
                self.status_label.config(text="Error: Could not open video for playback.", fg=ERROR_FG_COLOR)
                if self.preview_cap: self.preview_cap.release(); self.preview_cap = None
                return

            self.preview_fps = self.preview_cap.get(cv2.CAP_PROP_FPS)
            if self.preview_fps <= 0: self.preview_fps = 30

            # Set starting position from timeline if user scrubbed
            current_timeline_pos_sec = self.timeline_scale.get()
            self.preview_cap.set(cv2.CAP_PROP_POS_MSEC, int(current_timeline_pos_sec * 1000))

            self.is_preview_playing = True
            self.status_label.config(text="Playing preview...", fg=FG_COLOR_LIGHT)

            # Get preview label dimensions once for playback loop
            self.preview_label.update_idletasks()
            self.preview_label_width = self.preview_label.winfo_width() -10
            self.preview_label_height = self.preview_label.winfo_height() -10
            if self.preview_label_width <=1 : self.preview_label_width = 640
            if self.preview_label_height <=1 : self.preview_label_height = 480


            self.preview_thread = threading.Thread(target=self._preview_playback_loop, daemon=True)
            self.preview_thread.start()
        except Exception as e:
            self.status_label.config(text=f"Error starting playback: {e}", fg=ERROR_FG_COLOR)
            if self.preview_cap: self.preview_cap.release(); self.preview_cap = None
            self.is_preview_playing = False
        finally:
            self.update_playback_buttons_state()


    def _preview_playback_loop(self):
        try:
            frame_delay = 1.0 / self.preview_fps
            start_playback_time = time.perf_counter()
            initial_video_time_sec = self.preview_cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

            while self.is_preview_playing and self.preview_cap and self.preview_cap.isOpened():
                loop_iter_start_time = time.perf_counter()
                
                ret, frame = self.preview_cap.read()
                if not ret or frame is None:
                    break # End of video or error

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                
                # Use cached dimensions for speed
                img.thumbnail((self.preview_label_width, self.preview_label_height), Image.Resampling.LANCZOS)
                
                current_video_time_sec = self.preview_cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

                def update_gui_during_playback(image_to_show, current_time_val):
                    if not self.is_preview_playing: return
                    try:
                        photo = ImageTk.PhotoImage(image_to_show)
                        self.preview_label.config(image=photo)
                        self.preview_label.image = photo
                        
                        if not self.is_scrubbing: # Only update timeline if user isn't dragging it
                            self.timeline_scale.set(current_time_val)
                        self.time_display_label.config(text=f"{format_time(current_time_val)} / {format_time(self.video_total_duration_sec)}")
                    except tk.TclError: pass 
                    except Exception as e_gui: print(f"Error updating GUI during playback: {e_gui}")

                if self.master.winfo_exists():
                    self.master.after(0, lambda img_arg=img, time_arg=current_video_time_sec: update_gui_during_playback(img_arg, time_arg))
                else: break # Main window closed

                # Crude sync: Calculate elapsed time and expected video time, then sleep accordingly
                # This helps maintain FPS better than a fixed time.sleep(frame_delay)
                elapsed_real_time = time.perf_counter() - start_playback_time
                expected_video_time = initial_video_time_sec + elapsed_real_time
                
                # How much time the video has actually advanced
                actual_video_advanced_time = current_video_time_sec - initial_video_time_sec
                
                # Sleep for the difference to catch up, or a minimal amount if we are ahead
                # This is a simplified synchronization logic
                time_to_sleep = frame_delay - (time.perf_counter() - loop_iter_start_time)
                if time_to_sleep > 0:
                    time.sleep(time_to_sleep)

        except Exception as e: print(f"Error in playback loop: {e}")
        finally:
            # Schedule stop action on main thread if loop ends/breaks
            if self.master.winfo_exists():
                 self.master.after(0, self.stop_preview) # Ensure cleanup and button state update

    def pause_preview(self):
        self.is_preview_playing = False
        # The thread will see this flag and exit its loop.
        self.status_label.config(text="Preview paused.", fg=FG_COLOR_LIGHT)
        self.update_playback_buttons_state()

    def stop_preview(self, show_static_frame=True):
        was_playing = self.is_preview_playing
        self.is_preview_playing = False
        
        if self.preview_cap:
            self.preview_cap.release()
            self.preview_cap = None
        
        self.preview_thread = None

        if show_static_frame:
            # Update static frame to where timeline is currently pointing
            current_timeline_pos = self.timeline_scale.get()
            self._update_static_preview_frame(target_time_sec=current_timeline_pos)
        elif was_playing: # If it was playing and now stopped without showing static frame (e.g. new load)
            self.preview_label.config(image='', text="Preview stopped.", fg=FG_COLOR_LIGHT)
            self.preview_label.image = None
            # Reset timeline if stopping completely without new video
            # self.timeline_scale.set(0)
            # self.time_display_label.config(text=f"00:00 / {format_time(self.video_total_duration_sec)}")


        if was_playing: # Only show "Preview stopped" if it was actually playing
            self.status_label.config(text="Preview stopped.", fg=FG_COLOR_LIGHT)
        self.update_playback_buttons_state()


    def load_video(self):
        self.stop_preview(show_static_frame=False)
        filepath = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
        )
        if filepath:
            try:
                self.status_label.config(text="Verifying video file...", fg=FG_COLOR_LIGHT)
                self.master.update_idletasks()
                # Minimal check with MoviePy, full check with OpenCV for preview
                with VideoFileClip(filepath) as temp_clip: # Check if MoviePy can open
                    pass

                # Reset total duration so it gets recalculated in _update_static_preview_frame
                self.video_total_duration_sec = 0 

                self.current_video_path = filepath
                self.original_video_path = self.current_video_path
                self.video_path_label.config(text=os.path.basename(self.current_video_path))
                self.status_label.config(text="Video loaded successfully.", fg=SUCCESS_FG_COLOR)
                self.edit_count = 0
                
                self.undo_stack = [self.original_video_path]
                self.redo_stack = []
                self.update_undo_redo_buttons()
                
                self._update_static_preview_frame(video_path=self.current_video_path, target_time_sec=0) # Show first frame
                self.timeline_scale.set(0) # Ensure timeline is at start for new video

            except Exception as e:
                self.current_video_path = None
                self.original_video_path = None
                self.video_path_label.config(text="No video loaded")
                self.status_label.config(text=f"Error loading video: {str(e)[:100]}", fg=ERROR_FG_COLOR)
                messagebox.showerror("Load Error", f"Could not load video: {filepath}\nReason: {e}")
                self.video_total_duration_sec = 0
                self._update_static_preview_frame() # Clear preview
                self.undo_stack = []
                self.redo_stack = []
        elif not self.current_video_path: # No file chosen, and no previous video
            self.video_path_label.config(text="No video loaded")
            self.status_label.config(text="Video loading cancelled.", fg=WARNING_FG_COLOR)
            self.video_total_duration_sec = 0
            self._update_static_preview_frame()
        else: # No file chosen, but there was a previous video
            self.status_label.config(text="Video loading cancelled, previous video retained.", fg=WARNING_FG_COLOR)
            # Preview and timeline remain as is
        
        self.update_playback_buttons_state()
        self.update_undo_redo_buttons()


    def update_undo_redo_buttons(self):
        self.undo_button.config(state=tk.NORMAL if len(self.undo_stack) > 1 else tk.DISABLED)
        self.redo_button.config(state=tk.NORMAL if self.redo_stack else tk.DISABLED)

    def add_to_undo_stack(self, video_path):
        self.undo_stack.append(video_path)
        self.redo_stack.clear() # Any new action clears redo stack
        self.update_undo_redo_buttons()

    def undo_action(self):
        if len(self.undo_stack) > 1:
            self.stop_preview()
            self.redo_stack.append(self.undo_stack.pop())
            self.current_video_path = self.undo_stack[-1]
            self.video_path_label.config(text=os.path.basename(self.current_video_path))
            self.status_label.config(text=f"Undo: Now at {os.path.basename(self.current_video_path)}", fg=FG_COLOR_LIGHT)
            
            self.video_total_duration_sec = 0 # Force duration recalc for undone video
            self._update_static_preview_frame(target_time_sec=0) # Show first frame of undone video
            self.timeline_scale.set(0)

            self.update_undo_redo_buttons()
            self.update_playback_buttons_state()


    def redo_action(self):
        if self.redo_stack:
            self.stop_preview()
            self.undo_stack.append(self.redo_stack.pop())
            self.current_video_path = self.undo_stack[-1]
            self.video_path_label.config(text=os.path.basename(self.current_video_path))
            self.status_label.config(text=f"Redo: Now at {os.path.basename(self.current_video_path)}", fg=FG_COLOR_LIGHT)
            
            self.video_total_duration_sec = 0 # Force duration recalc for redone video
            self._update_static_preview_frame(target_time_sec=0) # Show first frame of redone video
            self.timeline_scale.set(0)

            self.update_undo_redo_buttons()
            self.update_playback_buttons_state()


    def get_edit_instruction_from_gemini(self, user_command_text):
        # ... (Gemini prompt as in your previous version, ensure it includes all features) ...
        if not self.api_key:
            self.status_label.config(text="Error: GOOGLE_API_KEY not set.", fg=ERROR_FG_COLOR)
            return {"action": "error", "message": "API key not configured."}

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel('gemini-1.5-flash') # Or your preferred model

        system_prompt = f"""
        You are a helpful assistant that translates natural language video editing commands into a structured JSON format.
        The user will provide a command. Your task is to identify the editing action and its parameters.
        Supported actions and their parameters are:
        1. Trim/Cut:
           - action: "trim"
           - start_time: float (seconds)
           - end_time: float (seconds, optional, trims to end from start_time if not given)
        2. Change Speed:
           - action: "speed"
           - factor: float (e.g., 2.0 for 2x speed, 0.5 for half speed)
        3. Add Text Overlay:
           - action: "add_text"
           - text_content: string (Mandatory)
           - start_time: float (seconds, default 0)
           - duration: float (seconds, default is until end of clip from start_time)
           - font_size: int (default 36)
           - color: string (default "white")
           - position: string or tuple (e.g., "center", ("10%","20%"), "('50', '50')") (default "center")
           - font: string (optional, default "Arial", e.g., "Impact", "Courier")
           - stroke_color: string (optional, default "black")
           - stroke_width: float (optional, default 1.5)
        4. Mute Audio: - action: "mute_audio"
        5. Extract Audio:
           - action: "extract_audio"
           - output_filename: string (optional, default "original_video_name_audio.mp3")
        6. Black and White Filter: - action: "black_and_white"
        7. Invert Colors Filter: - action: "invert_colors"
        8. Gamma Correction:
           - action: "gamma_correct"
           - gamma_value: float (e.g., 0.5 dark, 1.5 bright. Default 1.0)
        9. Adjust Volume:
           - action: "adjust_volume"
           - factor: float (e.g., 0.5 half, 2.0 double. Default 1.0)
        10. Rotate Video:
            - action: "rotate"
            - angle: float (degrees, e.g., 90, -90, 180)
        11. Fade In:
            - action: "fade_in"
            - duration: float (seconds, e.g., 1.5)
        12. Fade Out:
            - action: "fade_out"
            - duration: float (seconds, e.g., 1.5)
        13. Mirror/Flip:
            - action: "mirror"
            - direction: string ("horizontal" or "vertical")
        14. Normalize Audio: - action: "normalize_audio"
        15. Add Background Music:
            - action: "add_background_music"
            - music_path: string (Use "USER_SELECTS_MUSIC_FILE" if user doesn't specify a file path)
            - volume_factor: float (optional, default 0.3)
            - music_start_time_in_video: float (optional, default 0)
            - music_loop: boolean (optional, default false)
        16. Add Image Overlay/Watermark:
            - action: "add_image_overlay"
            - image_path: string (Use "USER_SELECTS_IMAGE_FILE" if not specified)
            - position: string or tuple (e.g., "center", "bottom_right", ("50","50%")) (default "bottom_right")
            - size_factor: float or tuple (optional, float scales e.g., 0.2 for 20% of video height, or tuple (width, height) in pixels. Default makes image 10% of video height, aspect preserved.)
            - opacity: float (optional, 0.0-1.0, default 0.8)
            - start_time: float (optional, default 0)
            - duration: float (optional, default until end of clip)
        17. Picture-in-Picture (PiP):
            - action: "picture_in_picture"
            - overlay_video_path: string (Use "USER_SELECTS_PIP_VIDEO_FILE" if not specified)
            - position: string or tuple (e.g., "top_left", ("10%","10%")) (default "top_right")
            - size_factor: float or tuple (optional, float scales overlay e.g., 0.25 for 1/4th of main video width, or (width, height) in pixels. Default is 25% of main video width.)
            - start_time: float (optional, default 0)
            - duration: float (optional, default overlay's duration or main's end)
        18. Blur Video:
            - action: "blur"
            - radius: int (optional, default 2, blur radius/strength)
        19. Concatenate Videos: (Appends videos to the CURRENTLY loaded video)
            - action: "concatenate"
            - videos_to_append: list of strings (Paths to videos to append. Use "USER_SELECTS_VIDEO_FILE_TO_APPEND" for each video if path not given.)

        If command is unclear/unsupported: {{"action": "error", "message": "Command not understood or not supported."}}
        User command: "{user_command_text}"
        Output *only* the JSON object.
        JSON Output:
        """
        try:
            response = model.generate_content(system_prompt)
            response_text = response.text
        except Exception as e:
            error_message = f"Gemini API Error: {str(e)[:150]}."
            self.status_label.config(text=error_message, fg=ERROR_FG_COLOR)
            return {"action": "error", "message": error_message}

        try:
            match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if match: json_str = match.group(1).strip()
            else: json_str = response_text.strip()
            json_str = json_str.replace('\\n', '\n') # Handle escaped newlines
            # Attempt to fix common JSON errors from LLMs (e.g. trailing commas)
            json_str = re.sub(r',\s*([\}\]])', r'\1', json_str) # Remove trailing commas before } or ]
            
            parsed_json = json.loads(json_str)
            return parsed_json
        except json.JSONDecodeError as e:
            error_message = f"AI Error: Could not parse AI's response. (Details: {e}. Response: {response_text[:100]}...)"
            self.status_label.config(text=error_message, fg=ERROR_FG_COLOR)
            return {"action": "error", "message": error_message}
        except Exception as e:
            error_message = f"Error processing AI response: {str(e)[:100]}."
            self.status_label.config(text=error_message, fg=ERROR_FG_COLOR)
            return {"action": "error", "message": error_message}

    def _parse_position(self, pos_param, main_clip_w, main_clip_h):
        simple_pos_keywords = ["center", "left", "right", "top", "bottom",
                               "top_left", "top_right", "bottom_left", "bottom_right"]
        if isinstance(pos_param, str) and pos_param in simple_pos_keywords:
            return pos_param

        if isinstance(pos_param, str) and pos_param.startswith("(") and pos_param.endswith(")"):
            try: # Try to eval if it's a string representation of a tuple
                pos_param = eval(pos_param)
            except:
                self.status_label.config(text=f"Warning: Could not parse position string '{pos_param}'. Using 'center'.", fg=WARNING_FG_COLOR)
                return "center"

        if isinstance(pos_param, (tuple, list)) and len(pos_param) == 2:
            x_val, y_val = pos_param
            px_x, px_y = None, None

            # Parse X
            if isinstance(x_val, str):
                if x_val in ["left", "center", "right"]: px_x = x_val
                elif '%' in x_val: px_x = float(x_val.strip('%')) / 100.0 * main_clip_w
                else:
                    try: px_x = float(x_val)
                    except ValueError: pass
            elif isinstance(x_val, (int, float)): px_x = x_val

            # Parse Y
            if isinstance(y_val, str):
                if y_val in ["top", "center", "bottom"]: px_y = y_val
                elif '%' in y_val: px_y = float(y_val.strip('%')) / 100.0 * main_clip_h
                else:
                    try: px_y = float(y_val)
                    except ValueError: pass
            elif isinstance(y_val, (int, float)): px_y = y_val

            if px_x is not None and px_y is not None:
                return (px_x, px_y)

        self.status_label.config(text=f"Warning: Invalid position format '{pos_param}'. Using 'center'.", fg=WARNING_FG_COLOR)
        return "center"


    def apply_video_edit(self, edit_params):
        # ... (Checks, stop_preview, load current_clip, temp_clips_to_close as before) ...
        if not self.current_video_path:
            self.status_label.config(text="Error: Please load a video first.", fg=ERROR_FG_COLOR)
            return None
        if not edit_params or edit_params.get("action") == "error":
            # Status label should already be set by get_edit_instruction_from_gemini or calling function
            if not self.status_label.cget("text").startswith("Error:"): # Set a generic one if not already set
                 self.status_label.config(text=f"Error: Cannot apply edit. {edit_params.get('message', 'Invalid parameters.')}", fg=ERROR_FG_COLOR)
            return None

        self.stop_preview()
        current_clip = None
        edited_clip = None
        new_filename_for_edit = None
        temp_clips_to_close = []

        try:
            self.status_label.config(text=f"Loading '{os.path.basename(self.current_video_path)}' for editing...", fg=FG_COLOR_LIGHT)
            self.master.update_idletasks()
            current_clip = VideoFileClip(self.current_video_path)
            temp_clips_to_close.append(current_clip)
        except Exception as e:
            self.status_label.config(text=f"Error: Could not load video for edit. (Details: {e})", fg=ERROR_FG_COLOR)
            return None

        action = edit_params.get("action")
        self.status_label.config(text=f"Applying '{action}'...", fg=FG_COLOR_LIGHT)
        self.master.update_idletasks()

        try:
            if action == "add_text":
                text_content = edit_params.get("text_content")
                if not text_content: raise ValueError("Text content is required.")
                start_time = float(edit_params.get("start_time", 0))
                duration_param = edit_params.get("duration")
                font_size = int(edit_params.get("font_size", 36))
                color = edit_params.get("color", "white")
                position_param = edit_params.get("position", "center") # This can be string or tuple
                font = edit_params.get("font", "Arial") # Changed default
                stroke_color = edit_params.get("stroke_color", "black")
                stroke_width = float(edit_params.get("stroke_width", 1.5))

                if start_time < 0: start_time = 0
                if start_time >= current_clip.duration: raise ValueError("Text start_time is beyond video duration.")
                duration = None
                if duration_param:
                    try: duration = float(duration_param)
                    except ValueError: pass
                if duration is None or duration <= 0: duration = max(0.1, current_clip.duration - start_time)
                if start_time + duration > current_clip.duration: duration = current_clip.duration - start_time
                
                # Use the improved _parse_position
                position = self._parse_position(position_param, current_clip.w, current_clip.h)

                txt_clip_obj = TextClip(text_content, fontsize=font_size, color=color, font=font,
                                        stroke_color=stroke_color, stroke_width=stroke_width)
                txt_clip_obj = txt_clip_obj.set_duration(duration).set_start(start_time).set_position(position)
                edited_clip = CompositeVideoClip([current_clip, txt_clip_obj]) # Removed set_opacity here for simplicity
                temp_clips_to_close.append(txt_clip_obj)
            
            # --- Other actions (trim, speed, mute, filters, etc. as before) ---
            elif action == "trim":
                start_time = float(edit_params.get("start_time", 0))
                end_time_param = edit_params.get("end_time")
                end_time = None
                if end_time_param is not None: end_time = float(end_time_param)
                if end_time is not None and start_time >= end_time: raise ValueError("Trim start < end.")
                if start_time >= current_clip.duration: raise ValueError("Trim start > duration.")
                edited_clip = current_clip.subclip(start_time, end_time)
            elif action == "speed":
                factor = float(edit_params.get("factor"));
                if factor <= 0: raise ValueError("Speed factor > 0."); edited_clip = current_clip.fx(vfx.speedx, factor)
            elif action == "mute_audio":
                if current_clip.audio: edited_clip = current_clip.without_audio()
                else: self.status_label.config(text="No audio to mute.", fg=WARNING_FG_COLOR); edited_clip = current_clip.copy()
            elif action == "extract_audio":
                audio_fn_suggest = edit_params.get("output_filename") or f"{os.path.splitext(os.path.basename(self.original_video_path))[0]}_audio.mp3"
                audio_save_path = filedialog.asksaveasfilename(title="Save Extracted Audio", initialfile=audio_fn_suggest, defaultextension=".mp3")
                if not audio_save_path: self.status_label.config(text="Audio extraction cancelled.", fg=WARNING_FG_COLOR); return self.current_video_path
                if current_clip.audio:
                    current_clip.audio.write_audiofile(audio_save_path)
                    self.status_label.config(text=f"Audio extracted: {os.path.basename(audio_save_path)}.", fg=SUCCESS_FG_COLOR)
                else: self.status_label.config(text="No audio to extract.", fg=WARNING_FG_COLOR)
                edited_clip = current_clip.copy()
            elif action == "black_and_white": edited_clip = current_clip.fx(vfx.blackwhite)
            elif action == "invert_colors": edited_clip = current_clip.fx(vfx.invert_colors)
            elif action == "gamma_correct":
                gamma = float(edit_params.get("gamma_value", 1.0)); edited_clip = current_clip.fx(vfx.gamma_corr, gamma)
            elif action == "adjust_volume":
                factor = float(edit_params.get("factor", 1.0))
                if current_clip.audio: edited_clip = current_clip.volumex(factor)
                else: self.status_label.config(text="No audio to adjust.", fg=WARNING_FG_COLOR); edited_clip = current_clip.copy()
            elif action == "rotate":
                angle = float(edit_params.get("angle", 0)); edited_clip = current_clip.rotate(angle, expand=True)
            elif action == "fade_in":
                dur = float(edit_params.get("duration"));
                if dur <= 0: raise ValueError("Fade In duration > 0."); edited_clip = current_clip.fadein(dur)
            elif action == "fade_out":
                dur = float(edit_params.get("duration"));
                if dur <= 0: raise ValueError("Fade Out duration > 0."); edited_clip = current_clip.fadeout(dur)
            elif action == "mirror":
                direction = edit_params.get("direction", "horizontal").lower()
                if direction == "horizontal": edited_clip = current_clip.fx(vfx.mirror_x)
                elif direction == "vertical": edited_clip = current_clip.fx(vfx.mirror_y)
                else: raise ValueError("Mirror direction: 'horizontal' or 'vertical'.")
            elif action == "normalize_audio":
                if current_clip.audio:
                    normalized_audio = current_clip.audio.fx(audio_normalize)
                    edited_clip = current_clip.set_audio(normalized_audio)
                    # MoviePy's fx often returns a new audio clip object, so track it if needed, though set_audio handles it.
                    # temp_clips_to_close.append(normalized_audio) # Usually not needed as set_audio incorporates
                else: self.status_label.config(text="No audio to normalize.", fg=WARNING_FG_COLOR); edited_clip = current_clip.copy()
            elif action == "add_background_music":
                music_path_param = edit_params.get("music_path")
                if not music_path_param or "USER_SELECTS" in music_path_param.upper():
                    music_path_param = self._ask_for_file("Select Background Music", [("Audio files", "*.mp3 *.wav *.aac")])
                if not music_path_param: raise ValueError("Background music file selection cancelled or failed.")
                music_clip_obj = AudioFileClip(music_path_param); temp_clips_to_close.append(music_clip_obj)
                volume_factor = float(edit_params.get("volume_factor", 0.3))
                music_start_time = float(edit_params.get("music_start_time_in_video", 0))
                loop_music = bool(edit_params.get("music_loop", False))
                music_to_composite = music_clip_obj.volumex(volume_factor)
                if loop_music and music_to_composite.duration < current_clip.duration - music_start_time :
                     num_loops = int((current_clip.duration - music_start_time) / music_to_composite.duration) + 1
                     looped_music = concatenate_audioclips([music_to_composite] * num_loops)
                     temp_clips_to_close.append(looped_music); music_to_composite = looped_music
                music_to_composite = music_to_composite.set_duration(min(music_to_composite.duration, current_clip.duration - music_start_time))
                final_audio = CompositeAudioClip([current_clip.audio, music_to_composite.set_start(music_start_time)]) if current_clip.audio else music_to_composite.set_start(music_start_time)
                temp_clips_to_close.append(final_audio) # CompositeAudioClip is new
                edited_clip = current_clip.set_audio(final_audio)
            elif action == "add_image_overlay":
                image_path_param = edit_params.get("image_path")
                if not image_path_param or "USER_SELECTS" in image_path_param.upper():
                    image_path_param = self._ask_for_file("Select Image Overlay", [("Image files", "*.png *.jpg *.jpeg")])
                if not image_path_param: raise ValueError("Image overlay selection cancelled or failed.")
                img_clip_obj = ImageClip(image_path_param); temp_clips_to_close.append(img_clip_obj)
                pos_param = edit_params.get("position", "bottom_right")
                size_factor_param = edit_params.get("size_factor")
                opacity = float(edit_params.get("opacity", 0.8))
                start_time = float(edit_params.get("start_time", 0))
                duration_param = edit_params.get("duration")
                if isinstance(size_factor_param, (int, float)): img_clip_obj = img_clip_obj.resize(height=int(current_clip.h * size_factor_param))
                elif isinstance(size_factor_param, (tuple,list)) and len(size_factor_param) == 2: img_clip_obj = img_clip_obj.resize(width=int(size_factor_param[0]), height=int(size_factor_param[1]))
                else: img_clip_obj = img_clip_obj.resize(height=int(current_clip.h * 0.1))
                duration = max(0.1, current_clip.duration - start_time) if not duration_param else float(duration_param)
                img_clip_obj = img_clip_obj.set_duration(duration).set_start(start_time).set_opacity(opacity)
                img_clip_obj = img_clip_obj.set_position(self._parse_position(pos_param, current_clip.w, current_clip.h)) # Use main clip w/h
                edited_clip = CompositeVideoClip([current_clip, img_clip_obj])
            elif action == "picture_in_picture":
                overlay_video_path_param = edit_params.get("overlay_video_path")
                if not overlay_video_path_param or "USER_SELECTS" in overlay_video_path_param.upper():
                    overlay_video_path_param = self._ask_for_file("Select PiP Video", [("Video files", "*.mp4 *.avi *.mov")])
                if not overlay_video_path_param: raise ValueError("PiP video selection cancelled or failed.")
                pip_clip_obj = VideoFileClip(overlay_video_path_param); temp_clips_to_close.append(pip_clip_obj)
                pos_param = edit_params.get("position", "top_right")
                size_factor_param = edit_params.get("size_factor")
                start_time = float(edit_params.get("start_time", 0))
                duration_param = edit_params.get("duration")
                if isinstance(size_factor_param, (int, float)): pip_clip_obj = pip_clip_obj.resize(width=int(current_clip.w * size_factor_param))
                elif isinstance(size_factor_param, (tuple, list)) and len(size_factor_param) == 2: pip_clip_obj = pip_clip_obj.resize(width=int(size_factor_param[0]), height=int(size_factor_param[1]))
                else: pip_clip_obj = pip_clip_obj.resize(width=int(current_clip.w * 0.25))
                duration = min(pip_clip_obj.duration, current_clip.duration - start_time) if not duration_param else min(float(duration_param), pip_clip_obj.duration)
                pip_clip_obj = pip_clip_obj.set_duration(duration).set_start(start_time)
                pip_clip_obj = pip_clip_obj.set_position(self._parse_position(pos_param, current_clip.w, current_clip.h)) # Use main clip w/h
                edited_clip = CompositeVideoClip([current_clip, pip_clip_obj])
            elif action == "blur":
                radius = int(edit_params.get("radius", 2)); edited_clip = current_clip.fx(vfx.blur, radius=radius)
            elif action == "concatenate":
                videos_to_append_params = edit_params.get("videos_to_append", [])
                if not videos_to_append_params: raise ValueError("No videos specified to concatenate.")
                clips_for_concat = [current_clip.copy()] # Start with a copy
                for i, video_path_param in enumerate(videos_to_append_params):
                    actual_video_path = video_path_param
                    if "USER_SELECTS" in video_path_param.upper():
                        actual_video_path = self._ask_for_file(f"Select Video {i+1} to Append", [("Video files", "*.mp4")])
                    if not actual_video_path: raise ValueError(f"Video {i+1} selection for concatenation cancelled.")
                    next_clip_obj = VideoFileClip(actual_video_path); temp_clips_to_close.append(next_clip_obj)
                    clips_for_concat.append(next_clip_obj)
                if len(clips_for_concat) > 1: edited_clip = concatenate_videoclips(clips_for_concat, method="compose")
                else: edited_clip = current_clip.copy()


            else:
                self.status_label.config(text=f"Error: Unknown action: {action}", fg=ERROR_FG_COLOR)
                return None
        except ValueError as ve:
            self.status_label.config(text=f"Parameter Error for '{action}': {ve}", fg=ERROR_FG_COLOR)
            return None
        except Exception as e_moviepy:
            self.status_label.config(text=f"MoviePy Error ('{action}'): {str(e_moviepy)[:150]}", fg=ERROR_FG_COLOR)
            print(f"Full MoviePy Error for {action}: {e_moviepy}")
            return None
        finally:
            for clip_obj in temp_clips_to_close:
                if clip_obj:
                    try: clip_obj.close()
                    except Exception as e_close: print(f"Minor error closing temp clip: {e_close}")

        # Save Edited Clip
        if edited_clip:
            try:
                self.edit_count += 1
                original_basename, original_ext = os.path.splitext(os.path.basename(self.original_video_path))
                edits_dir = os.path.join(os.path.dirname(self.original_video_path), "_video_editor_edits")
                os.makedirs(edits_dir, exist_ok=True)
                new_filename_for_edit = os.path.join(edits_dir, f"{original_basename}_edit_{self.edit_count}{original_ext}")
                
                self.status_label.config(text=f"Saving as {os.path.basename(new_filename_for_edit)}...", fg=FG_COLOR_LIGHT)
                self.master.update_idletasks()
                
                edited_clip.write_videofile(new_filename_for_edit, codec="libx264", audio_codec="aac", preset="medium", threads=os.cpu_count() or 2, logger='bar')
                
                self.status_label.config(text=f"Edit '{action}' applied: {os.path.basename(new_filename_for_edit)}", fg=SUCCESS_FG_COLOR)
                # After successful save, force recalculation of duration for the new clip
                self.video_total_duration_sec = 0 
            except Exception as e_save:
                self.status_label.config(text=f"Error saving video: {str(e_save)[:100]}.", fg=ERROR_FG_COLOR)
                print(f"Full Save Error: {e_save}")
                new_filename_for_edit = None
            finally:
                if edited_clip: edited_clip.close()
        return new_filename_for_edit


    def apply_edit(self):
        # ... (Main apply_edit logic as before) ...
        user_command = self.edit_entry.get()
        if not user_command:
            self.status_label.config(text="Please enter an editing command.", fg=WARNING_FG_COLOR); return
        if not self.current_video_path:
            self.status_label.config(text="Please load a video first.", fg=ERROR_FG_COLOR); return

        self.status_label.config(text="Processing command with AI...", fg=FG_COLOR_LIGHT)
        self.master.update_idletasks() 
        edit_params = self.get_edit_instruction_from_gemini(user_command)
        
        if edit_params and edit_params.get("action") != "error":
            saved_video_path = self.apply_video_edit(edit_params) # This is the path of the NEWLY created file
            if saved_video_path and os.path.exists(saved_video_path):
                if edit_params.get("action") != "extract_audio" or not self.undo_stack or saved_video_path != self.undo_stack[-1]:
                     self.current_video_path = saved_video_path
                     self.add_to_undo_stack(self.current_video_path)
                     self.video_path_label.config(text=os.path.basename(self.current_video_path))
                
                self.video_total_duration_sec = 0 # Force recalc of duration for new/edited video
                self._update_static_preview_frame(target_time_sec=0) # Update preview to this new state, show first frame
                self.timeline_scale.set(0) # Reset timeline to start
            elif edit_params.get("action") == "extract_audio" and saved_video_path == self.current_video_path:
                 self._update_static_preview_frame()
            else: # An error occurred during apply_video_edit or saving, status already set
                self._update_static_preview_frame(target_time_sec=self.timeline_scale.get()) # Refresh preview to current timeline pos
        
        self.update_playback_buttons_state()
        self.edit_entry.delete(0, tk.END)


    def export_video(self):
        # ... (Same as before) ...
        if not self.current_video_path or not os.path.exists(self.current_video_path):
            messagebox.showerror("Export Error", "No current video to export or file not found.")
            self.status_label.config(text="Export failed: No valid video loaded.", fg=ERROR_FG_COLOR); return
        default_filename = f"{os.path.splitext(os.path.basename(self.original_video_path if self.original_video_path else 'edited_video'))[0]}_exported.mp4"
        export_filepath = filedialog.asksaveasfilename(title="Export Video As", initialfile=default_filename, defaultextension=".mp4", filetypes=[("MP4 video", "*.mp4")])
        if export_filepath:
            try:
                self.status_label.config(text=f"Exporting to {os.path.basename(export_filepath)}...", fg=FG_COLOR_LIGHT)
                self.master.update_idletasks()
                shutil.copy(self.current_video_path, export_filepath)
                self.status_label.config(text=f"Video exported successfully: {os.path.basename(export_filepath)}", fg=SUCCESS_FG_COLOR)
                messagebox.showinfo("Export Success", f"Video saved to:\n{export_filepath}")
            except Exception as e:
                self.status_label.config(text=f"Export failed: {str(e)[:100]}", fg=ERROR_FG_COLOR)
                messagebox.showerror("Export Error", f"Could not export video: {e}")

    def on_closing(self):
        # ... (Same as before) ...
        self.stop_preview(show_static_frame=False)
        if self.original_video_path:
            edits_dir = os.path.join(os.path.dirname(self.original_video_path), "_video_editor_edits")
            if os.path.exists(edits_dir):
                try:
                    if messagebox.askyesno("Clean Up", "Delete intermediate edited files from '_video_editor_edits' folder?"):
                        shutil.rmtree(edits_dir)
                        print(f"Cleaned up temporary edit files in {edits_dir}")
                except Exception as e: print(f"Error cleaning up temporary files: {e}")
        self.master.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    app = VideoEditorApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
