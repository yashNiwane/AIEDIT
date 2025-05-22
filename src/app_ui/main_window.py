import tkinter as tk
from tkinter import filedialog, messagebox
import os
import cv2 # Assuming cv2 is for OpenCV
from PIL import Image, ImageTk
import threading
import time
import shutil

# Local/application-specific imports
from . import ui_styles # For color constants
from ..video_logic.utils import _parse_position as util_parse_position # Renamed to avoid clash
from ..video_logic.gemini_integration import get_edit_instruction_from_gemini as util_get_gemini_edit # Renamed
from ..video_logic.editor import VideoEditorLogic

# --- Helper Function (from original, can be kept here or moved to a UI utils if more accumulate) ---
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


class VideoEditorAppUI:
    def __init__(self, master):
        self.master = master
        master.title("Prompt-Based Video Editor")
        master.geometry("1000x800")
        master.configure(bg=ui_styles.BG_COLOR)

        self.video_logic = VideoEditorLogic() # Instantiate logic class

        self.current_video_path = None
        self.original_video_path = None # To keep track of the initially loaded video
        self.edit_count = 0 # For naming intermediate files
        self.undo_stack = []
        self.redo_stack = []
        
        self.preview_cap = None
        self.is_preview_playing = False
        self.preview_thread = None
        self.preview_fps = 30
        self.video_total_duration_sec = 0
        self.preview_label_width = 640 
        self.preview_label_height = 480
        self.is_scrubbing = False

        # API Key - consider moving to a config file or env var setup at app start
        self.api_key = os.environ.get('GOOGLE_API_KEY') 

        self._setup_ui()

        if not self.api_key:
            self.status_label.config(text="Warning: GOOGLE_API_KEY not found. AI features disabled.", fg=ui_styles.WARNING_FG_COLOR)
            print("Warning: GOOGLE_API_KEY environment variable not found. AI features disabled.")
        
        self.update_undo_redo_buttons()
        self.update_playback_buttons_state()


    def _status_update_lambda(self):
        return lambda text, color: self.status_label.config(text=text, fg=color)

    # Modified to use the imported utility function
    def _parse_position(self, pos_param, main_clip_w, main_clip_h):
        # This method now delegates to the utility function, passing the status update lambda
        return util_parse_position(pos_param, main_clip_w, main_clip_h, 
                                   self._status_update_lambda(), 
                                   ui_styles.WARNING_FG_COLOR)

    # Modified to use the imported Gemini integration function
    def get_edit_instruction_from_gemini(self, user_command_text):
        # This method now delegates to the utility function
        if not self.api_key: # Check API key before calling, as the util might not have UI access
            self.status_label.config(text="Error: GOOGLE_API_KEY not set for Gemini.", fg=ui_styles.ERROR_FG_COLOR)
            return {"action": "error", "message": "API key not configured."}
        
        return util_get_gemini_edit(user_command_text, self.api_key, 
                                    self._status_update_lambda(), 
                                    ui_styles.ERROR_FG_COLOR, 
                                    ui_styles.WARNING_FG_COLOR)

    def _setup_ui(self):
        # Top Frame for Load, Path, Undo, Redo
        top_controls_frame = tk.Frame(self.master, bg=ui_styles.BG_COLOR, pady=10, padx=10)
        top_controls_frame.pack(fill=tk.X)

        self.load_button = tk.Button(top_controls_frame, text="Load Video", command=self.load_video,
                                     bg=ui_styles.BUTTON_BG_COLOR, fg=ui_styles.BUTTON_FG_COLOR, relief=tk.FLAT, activebackground=ui_styles.ACCENT_COLOR)
        self.load_button.pack(side=tk.LEFT, padx=(0,5))
        self.video_path_label = tk.Label(top_controls_frame, text="No video loaded", relief=tk.SUNKEN, anchor=tk.W, padx=5,
                                         bg=ui_styles.BG_COLOR, fg=ui_styles.FG_COLOR_LIGHT, width=40)
        self.video_path_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.undo_button = tk.Button(top_controls_frame, text="Undo", command=self.undo_action,
                                     bg=ui_styles.BUTTON_BG_COLOR, fg=ui_styles.BUTTON_FG_COLOR, relief=tk.FLAT, activebackground=ui_styles.ACCENT_COLOR)
        self.undo_button.pack(side=tk.LEFT, padx=5)
        self.redo_button = tk.Button(top_controls_frame, text="Redo", command=self.redo_action,
                                     bg=ui_styles.BUTTON_BG_COLOR, fg=ui_styles.BUTTON_FG_COLOR, relief=tk.FLAT, activebackground=ui_styles.ACCENT_COLOR)
        self.redo_button.pack(side=tk.LEFT, padx=5)

        # Middle Frame (Editing Controls and Preview Area)
        middle_frame = tk.Frame(self.master, bg=ui_styles.BG_COLOR, padx=5, pady=5)
        middle_frame.pack(fill=tk.BOTH, expand=True)

        # Left Sub-Frame (Editing Controls)
        edit_controls_frame = tk.Frame(middle_frame, bg=ui_styles.BG_COLOR, padx=10)
        edit_controls_frame.pack(side=tk.LEFT, fill=tk.Y, anchor=tk.N)
        tk.Label(edit_controls_frame, text="Enter Editing Command:", bg=ui_styles.BG_COLOR, fg=ui_styles.FG_COLOR_LIGHT).pack(anchor=tk.W, pady=(0,2))
        self.edit_entry = tk.Entry(edit_controls_frame, width=40, bg=ui_styles.FG_COLOR_LIGHT, fg=ui_styles.BG_COLOR, insertbackground=ui_styles.BG_COLOR)
        self.edit_entry.pack(pady=5, fill=tk.X)
        self.apply_button = tk.Button(edit_controls_frame, text="Apply Edit", command=self.apply_edit_ui_wrapper, # Changed command
                                      bg=ui_styles.ACCENT_COLOR, fg=ui_styles.BUTTON_FG_COLOR, relief=tk.FLAT, padx=10, activebackground="#005f9e")
        self.apply_button.pack(pady=10, fill=tk.X)
        self.export_button = tk.Button(edit_controls_frame, text="Export Video As...", command=self.export_video,
                                       bg=ui_styles.BUTTON_BG_COLOR, fg=ui_styles.BUTTON_FG_COLOR, relief=tk.FLAT, padx=10, activebackground=ui_styles.ACCENT_COLOR)
        self.export_button.pack(pady=10, fill=tk.X)

        # Right Sub-Frame (Preview Area)
        preview_area_frame = tk.Frame(middle_frame, bg=ui_styles.BG_COLOR)
        preview_area_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)
        tk.Label(preview_area_frame, text="Video Preview:", anchor=tk.N, bg=ui_styles.BG_COLOR, fg=ui_styles.FG_COLOR_LIGHT).pack(pady=(5,2))
        self.preview_label = tk.Label(preview_area_frame, bg=ui_styles.PREVIEW_BG_COLOR, relief=tk.SUNKEN)
        self.preview_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.preview_image_ref = None # To hold reference to PhotoImage

        # Timeline
        self.timeline_scale = tk.Scale(preview_area_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                       showvalue=0, sliderrelief=tk.FLAT, command=self.seek_from_timeline,
                                       bg=ui_styles.TIMELINE_BG, fg=ui_styles.FG_COLOR_LIGHT,
                                       troughcolor=ui_styles.TIMELINE_TROUGH, activebackground=ui_styles.ACCENT_COLOR,
                                       length=300, relief=tk.GROOVE, bd=1)
        self.timeline_scale.pack(fill=tk.X, padx=5, pady=(0,0))
        self.timeline_scale.bind("<ButtonPress-1>", self._on_timeline_press)
        self.timeline_scale.bind("<ButtonRelease-1>", self._on_timeline_release)

        # Playback Controls & Time Display Frame
        playback_and_time_frame = tk.Frame(preview_area_frame, bg=ui_styles.BG_COLOR)
        playback_and_time_frame.pack(fill=tk.X, pady=2)
        self.play_button = tk.Button(playback_and_time_frame, text="▶ Play", command=self.play_preview,
                                     bg=ui_styles.BUTTON_BG_COLOR, fg=ui_styles.BUTTON_FG_COLOR, relief=tk.FLAT, activebackground=ui_styles.ACCENT_COLOR)
        self.play_button.pack(side=tk.LEFT, padx=5)
        self.pause_button = tk.Button(playback_and_time_frame, text="❚❚ Pause", command=self.pause_preview,
                                      bg=ui_styles.BUTTON_BG_COLOR, fg=ui_styles.BUTTON_FG_COLOR, relief=tk.FLAT, activebackground=ui_styles.ACCENT_COLOR)
        self.pause_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = tk.Button(playback_and_time_frame, text="■ Stop", command=self.stop_preview,
                                     bg=ui_styles.BUTTON_BG_COLOR, fg=ui_styles.BUTTON_FG_COLOR, relief=tk.FLAT, activebackground=ui_styles.ACCENT_COLOR)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.time_display_label = tk.Label(playback_and_time_frame, text="00:00 / 00:00",
                                           bg=ui_styles.BG_COLOR, fg=ui_styles.FG_COLOR_LIGHT, padx=10)
        self.time_display_label.pack(side=tk.RIGHT)

        # Bottom Frame (Status)
        status_frame = tk.Frame(self.master, relief=tk.SUNKEN, bd=1, bg=ui_styles.STATUS_BG_COLOR)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_label = tk.Label(status_frame, text="Welcome! Load a video to start.", anchor=tk.W, padx=5, pady=3,
                                     bg=ui_styles.STATUS_BG_COLOR, fg=ui_styles.FG_COLOR_LIGHT)
        self.status_label.pack(fill=tk.X)

    def _on_timeline_press(self, event):
        self.is_scrubbing = True
        if self.is_preview_playing:
            self.pause_preview() 

    def _on_timeline_release(self, event):
        self.is_scrubbing = False
        # self.seek_from_timeline is called by Scale command

    def seek_from_timeline(self, value_str):
        if not self.current_video_path or not self.is_scrubbing:
            return
        try:
            seek_time_sec = float(value_str)
            self._update_static_preview_frame(target_time_sec=seek_time_sec)
        except ValueError: pass 
        except Exception as e: print(f"Error seeking from timeline: {e}")


    def _ask_for_file(self, title, filetypes, placeholder_text_in_status="Please select a file..."):
        original_status = self.status_label.cget("text") # Not used, but good to remember this pattern
        original_fg = self.status_label.cget("fg")
        self.status_label.config(text=placeholder_text_in_status, fg=ui_styles.WARNING_FG_COLOR)
        self.master.update_idletasks()
        filepath = filedialog.askopenfilename(title=title, filetypes=filetypes)
        if not filepath:
            self.status_label.config(text=f"{title} selection cancelled.", fg=ui_styles.WARNING_FG_COLOR)
            return None
        self.status_label.config(text=f"File selected: {os.path.basename(filepath)}", fg=ui_styles.FG_COLOR_LIGHT)
        return filepath

    def update_playback_buttons_state(self):
        video_loaded = bool(self.current_video_path and os.path.exists(self.current_video_path))
        self.play_button.config(state=tk.NORMAL if video_loaded and not self.is_preview_playing else tk.DISABLED)
        self.pause_button.config(state=tk.NORMAL if self.is_preview_playing else tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL if video_loaded else tk.DISABLED)
        self.timeline_scale.config(state=tk.NORMAL if video_loaded else tk.DISABLED)


    def _update_static_preview_frame(self, video_path=None, target_time_sec=None):
        if self.is_preview_playing and target_time_sec is not None:
            self.stop_preview(show_static_frame=False)

        target_path = video_path if video_path else self.current_video_path

        if not target_path or not os.path.exists(target_path):
            self.preview_label.config(image='', text="No video loaded or preview unavailable", fg=ui_styles.FG_COLOR_LIGHT)
            self.preview_label.image = None
            self.time_display_label.config(text="00:00 / 00:00")
            if hasattr(self, 'timeline_scale'): self.timeline_scale.set(0)
            self.update_playback_buttons_state()
            return

        cap = None
        try:
            cap = cv2.VideoCapture(target_path)
            if not cap.isOpened():
                self.preview_label.config(image='', text="Error opening video for preview", fg=ui_styles.ERROR_FG_COLOR)
                return

            current_fps = cap.get(cv2.CAP_PROP_FPS)
            if current_fps == 0: current_fps = self.preview_fps 

            if self.video_total_duration_sec == 0 or video_path: 
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                self.video_total_duration_sec = total_frames / current_fps if current_fps > 0 else 0
                self.timeline_scale.config(to=self.video_total_duration_sec if self.video_total_duration_sec > 0 else 100)

            seek_pos_msec = 0
            if target_time_sec is not None:
                seek_pos_msec = int(target_time_sec * 1000)
                cap.set(cv2.CAP_PROP_POS_MSEC, seek_pos_msec)
            else: 
                default_seek_time_sec = min(1.0, self.video_total_duration_sec / 2.0) if self.video_total_duration_sec > 0.1 else 0.0
                seek_pos_msec = int(default_seek_time_sec * 1000)
                cap.set(cv2.CAP_PROP_POS_MSEC, seek_pos_msec)
            
            current_display_time_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            ret, frame = cap.read()

            if not ret or frame is None:
                self.preview_label.config(image='', text="Could not read frame for preview", fg=ui_styles.ERROR_FG_COLOR)
                return

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)

            self.preview_label.update_idletasks()
            self.preview_label_width = self.preview_label.winfo_width() -10 
            self.preview_label_height = self.preview_label.winfo_height() -10
            if self.preview_label_width <=1 : self.preview_label_width = 640
            if self.preview_label_height <=1 : self.preview_label_height = 480
            
            img.thumbnail((self.preview_label_width, self.preview_label_height), Image.Resampling.LANCZOS)
            self.preview_image_ref = ImageTk.PhotoImage(img)
            self.preview_label.config(image=self.preview_image_ref, text="")
            
            if not self.is_scrubbing:
                 self.timeline_scale.set(current_display_time_sec)
            self.time_display_label.config(text=f"{format_time(current_display_time_sec)} / {format_time(self.video_total_duration_sec)}")

        except Exception as e:
            error_msg = f"Error static preview: {str(e)[:100]}"
            self.status_label.config(text=error_msg, fg=ui_styles.ERROR_FG_COLOR)
            self.preview_label.config(image='', text="Preview Error", fg=ui_styles.ERROR_FG_COLOR)
            print(f"Full static preview error details: {e}")
        finally:
            if cap: cap.release()
            self.update_playback_buttons_state()

    def play_preview(self):
        if self.is_preview_playing: return
        if not self.current_video_path or not os.path.exists(self.current_video_path):
            self.status_label.config(text="No video loaded to play.", fg=ui_styles.WARNING_FG_COLOR)
            return

        self.stop_preview(show_static_frame=False) 

        try:
            self.preview_cap = cv2.VideoCapture(self.current_video_path)
            if not self.preview_cap.isOpened():
                self.status_label.config(text="Error: Could not open video for playback.", fg=ui_styles.ERROR_FG_COLOR)
                if self.preview_cap: self.preview_cap.release(); self.preview_cap = None
                return

            self.preview_fps = self.preview_cap.get(cv2.CAP_PROP_FPS)
            if self.preview_fps <= 0: self.preview_fps = 30

            current_timeline_pos_sec = self.timeline_scale.get()
            self.preview_cap.set(cv2.CAP_PROP_POS_MSEC, int(current_timeline_pos_sec * 1000))

            self.is_preview_playing = True
            self.status_label.config(text="Playing preview...", fg=ui_styles.FG_COLOR_LIGHT)

            self.preview_label.update_idletasks()
            self.preview_label_width = self.preview_label.winfo_width() -10
            self.preview_label_height = self.preview_label.winfo_height() -10
            if self.preview_label_width <=1 : self.preview_label_width = 640
            if self.preview_label_height <=1 : self.preview_label_height = 480

            self.preview_thread = threading.Thread(target=self._preview_playback_loop, daemon=True)
            self.preview_thread.start()
        except Exception as e:
            self.status_label.config(text=f"Error starting playback: {e}", fg=ui_styles.ERROR_FG_COLOR)
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
                if not ret or frame is None: break

                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                img.thumbnail((self.preview_label_width, self.preview_label_height), Image.Resampling.LANCZOS)
                current_video_time_sec = self.preview_cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0

                def update_gui_during_playback(image_to_show, current_time_val):
                    if not self.is_preview_playing: return
                    try:
                        photo = ImageTk.PhotoImage(image_to_show)
                        self.preview_label.config(image=photo)
                        self.preview_label.image = photo
                        if not self.is_scrubbing:
                            self.timeline_scale.set(current_time_val)
                        self.time_display_label.config(text=f"{format_time(current_time_val)} / {format_time(self.video_total_duration_sec)}")
                    except tk.TclError: pass 
                    except Exception as e_gui: print(f"Error updating GUI during playback: {e_gui}")

                if self.master.winfo_exists():
                    self.master.after(0, lambda img_arg=img, time_arg=current_video_time_sec: update_gui_during_playback(img_arg, time_arg))
                else: break

                time_to_sleep = frame_delay - (time.perf_counter() - loop_iter_start_time)
                if time_to_sleep > 0:
                    time.sleep(time_to_sleep)
        except Exception as e: print(f"Error in playback loop: {e}")
        finally:
            if self.master.winfo_exists():
                 self.master.after(0, self.stop_preview)

    def pause_preview(self):
        self.is_preview_playing = False
        self.status_label.config(text="Preview paused.", fg=ui_styles.FG_COLOR_LIGHT)
        self.update_playback_buttons_state()

    def stop_preview(self, show_static_frame=True):
        was_playing = self.is_preview_playing
        self.is_preview_playing = False
        if self.preview_cap:
            self.preview_cap.release()
            self.preview_cap = None
        self.preview_thread = None

        if show_static_frame:
            current_timeline_pos = self.timeline_scale.get()
            self._update_static_preview_frame(target_time_sec=current_timeline_pos)
        elif was_playing: 
            self.preview_label.config(image='', text="Preview stopped.", fg=ui_styles.FG_COLOR_LIGHT)
            self.preview_label.image = None

        if was_playing:
            self.status_label.config(text="Preview stopped.", fg=ui_styles.FG_COLOR_LIGHT)
        self.update_playback_buttons_state()

    def load_video(self):
        self.stop_preview(show_static_frame=False)
        filepath = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
        )
        if filepath:
            try:
                self.status_label.config(text="Verifying video file...", fg=ui_styles.FG_COLOR_LIGHT)
                self.master.update_idletasks()
                # A minimal check can be done here if needed, but full check in _update_static_preview_frame
                # For example, using a quick VideoFileClip to see if it loads
                # from moviepy.editor import VideoFileClip 
                # with VideoFileClip(filepath) as temp_clip: pass

                self.video_total_duration_sec = 0 
                self.current_video_path = filepath
                self.original_video_path = self.current_video_path # Set original path
                self.video_path_label.config(text=os.path.basename(self.current_video_path))
                self.status_label.config(text="Video loaded successfully.", fg=ui_styles.SUCCESS_FG_COLOR)
                self.edit_count = 0 # Reset edit count for new video
                
                # Initialize undo stack with the original loaded video
                self.undo_stack = [self.original_video_path] 
                self.redo_stack = []
                self.update_undo_redo_buttons()
                
                self._update_static_preview_frame(video_path=self.current_video_path, target_time_sec=0)
                self.timeline_scale.set(0)

            except Exception as e:
                self.current_video_path = None
                self.original_video_path = None
                self.video_path_label.config(text="No video loaded")
                self.status_label.config(text=f"Error loading video: {str(e)[:100]}", fg=ui_styles.ERROR_FG_COLOR)
                messagebox.showerror("Load Error", f"Could not load video: {filepath}\nReason: {e}")
                self.video_total_duration_sec = 0
                self._update_static_preview_frame() 
                self.undo_stack = []
                self.redo_stack = []
        elif not self.current_video_path: 
            self.video_path_label.config(text="No video loaded")
            self.status_label.config(text="Video loading cancelled.", fg=ui_styles.WARNING_FG_COLOR)
            self.video_total_duration_sec = 0
            self._update_static_preview_frame()
        else: 
            self.status_label.config(text="Video loading cancelled, previous video retained.", fg=ui_styles.WARNING_FG_COLOR)
        
        self.update_playback_buttons_state()
        self.update_undo_redo_buttons()

    def update_undo_redo_buttons(self):
        self.undo_button.config(state=tk.NORMAL if len(self.undo_stack) > 1 else tk.DISABLED)
        self.redo_button.config(state=tk.NORMAL if self.redo_stack else tk.DISABLED)

    def add_to_undo_stack(self, video_path):
        # Make sure we're not adding the same path consecutively if it's already the last one
        if not self.undo_stack or self.undo_stack[-1] != video_path:
            self.undo_stack.append(video_path)
        self.redo_stack.clear() 
        self.update_undo_redo_buttons()

    def undo_action(self):
        if len(self.undo_stack) > 1: # More than just the original video
            self.stop_preview()
            self.redo_stack.append(self.undo_stack.pop())
            self.current_video_path = self.undo_stack[-1]
            self.video_path_label.config(text=os.path.basename(self.current_video_path))
            self.status_label.config(text=f"Undo: Now at {os.path.basename(self.current_video_path)}", fg=ui_styles.FG_COLOR_LIGHT)
            
            self.video_total_duration_sec = 0 # Force duration recalc
            self._update_static_preview_frame(target_time_sec=0) 
            self.timeline_scale.set(0)
            self.update_undo_redo_buttons()
            self.update_playback_buttons_state()

    def redo_action(self):
        if self.redo_stack:
            self.stop_preview()
            self.undo_stack.append(self.redo_stack.pop())
            self.current_video_path = self.undo_stack[-1]
            self.video_path_label.config(text=os.path.basename(self.current_video_path))
            self.status_label.config(text=f"Redo: Now at {os.path.basename(self.current_video_path)}", fg=ui_styles.FG_COLOR_LIGHT)
            
            self.video_total_duration_sec = 0 # Force duration recalc
            self._update_static_preview_frame(target_time_sec=0)
            self.timeline_scale.set(0)
            self.update_undo_redo_buttons()
            self.update_playback_buttons_state()

    def apply_edit_ui_wrapper(self):
        user_command = self.edit_entry.get()
        if not user_command:
            self.status_label.config(text="Please enter an editing command.", fg=ui_styles.WARNING_FG_COLOR); return
        if not self.current_video_path:
            self.status_label.config(text="Please load a video first.", fg=ui_styles.ERROR_FG_COLOR); return

        self.stop_preview() # Stop preview before applying edit
        self.status_label.config(text="Processing command with AI...", fg=ui_styles.FG_COLOR_LIGHT)
        self.master.update_idletasks() 
        
        edit_params = self.get_edit_instruction_from_gemini(user_command) # Calls the refactored method
        
        if edit_params and edit_params.get("action") != "error":
            # Prepare the ui_colors dictionary to pass to the logic layer
            all_ui_colors = {name: getattr(ui_styles, name) for name in dir(ui_styles) if name.isupper() and name.endswith('_COLOR')}

            # Call the refactored process_edit method from VideoEditorLogic
            result = self.video_logic.process_edit(
                edit_params,
                self.current_video_path,
                self.original_video_path, # Pass original video path
                self.edit_count,
                self._ask_for_file,       # Pass the UI file dialog function
                self._parse_position,     # Pass the UI wrapper for parse_position
                self._status_update_lambda(), # Pass the status update lambda
                all_ui_colors,            # Pass all UI colors
                filedialog.asksaveasfilename # Pass the save dialog function
            )

            # Update UI based on the result from video_logic
            if result and result.get('new_video_path'):
                # Handle 'extract_audio' specifically if it doesn't change current_video_path
                action_performed = edit_params.get("action", "")
                action_specific_result = result.get('action_specific_result', True) # Default to true if not present

                if action_performed == "extract_audio" and not action_specific_result:
                    # Audio extraction was cancelled or failed, status already set by logic
                    pass
                elif action_performed == "extract_audio" and action_specific_result:
                    # Audio extraction successful, no change to current video path, status set by logic
                    self.status_label.config(text=result.get('status_text', 'Audio extracted.'), fg=result.get('status_fg', ui_styles.SUCCESS_FG_COLOR))
                elif result['new_video_path'] != self.current_video_path: # A new video was created
                    self.current_video_path = result['new_video_path']
                    self.edit_count = result['updated_edit_count']
                    self.add_to_undo_stack(self.current_video_path)
                    self.video_path_label.config(text=os.path.basename(self.current_video_path))
                
                self.status_label.config(text=result.get('status_text', 'Edit applied.'), fg=result.get('status_fg', ui_styles.SUCCESS_FG_COLOR))
                self.video_total_duration_sec = 0 # Force recalc of duration
                self._update_static_preview_frame(target_time_sec=0) 
                self.timeline_scale.set(0)
            else:
                # Error or no new video path, status should be set by video_logic.process_edit
                if result and result.get('status_text'):
                     self.status_label.config(text=result.get('status_text'), fg=result.get('status_fg', ui_styles.ERROR_FG_COLOR))
                else: # Generic error if logic didn't provide one
                     self.status_label.config(text="Failed to apply edit.", fg=ui_styles.ERROR_FG_COLOR)
                self._update_static_preview_frame(target_time_sec=self.timeline_scale.get()) # Refresh preview

        elif edit_params and edit_params.get("action") == "error":
             # Status label should already be set by get_edit_instruction_from_gemini
             if not self.status_label.cget("text").startswith("Error:"): # Set a generic one if not already set by Gemini call
                self.status_label.config(text=edit_params.get('message', "AI command processing error."), fg=ui_styles.ERROR_FG_COLOR)
        
        self.update_playback_buttons_state()
        self.edit_entry.delete(0, tk.END)


    def export_video(self):
        if not self.current_video_path or not os.path.exists(self.current_video_path):
            messagebox.showerror("Export Error", "No current video to export or file not found.")
            self.status_label.config(text="Export failed: No valid video loaded.", fg=ui_styles.ERROR_FG_COLOR); return
        
        # Suggest a filename based on the original video name, not the intermediate edit name
        default_filename_base = "edited_video"
        if self.original_video_path: # Use original path if available
             default_filename_base = os.path.splitext(os.path.basename(self.original_video_path))[0]
        
        default_filename = f"{default_filename_base}_exported.mp4"
        
        export_filepath = filedialog.asksaveasfilename(
            title="Export Video As", 
            initialfile=default_filename, 
            defaultextension=".mp4", 
            filetypes=[("MP4 video", "*.mp4"), ("All files", "*.*")]
        )
        if export_filepath:
            try:
                self.status_label.config(text=f"Exporting to {os.path.basename(export_filepath)}...", fg=ui_styles.FG_COLOR_LIGHT)
                self.master.update_idletasks()
                shutil.copy(self.current_video_path, export_filepath) # Copy the latest edited version
                self.status_label.config(text=f"Video exported successfully: {os.path.basename(export_filepath)}", fg=ui_styles.SUCCESS_FG_COLOR)
                messagebox.showinfo("Export Success", f"Video saved to:\n{export_filepath}")
            except Exception as e:
                self.status_label.config(text=f"Export failed: {str(e)[:100]}", fg=ui_styles.ERROR_FG_COLOR)
                messagebox.showerror("Export Error", f"Could not export video: {e}")

    def on_closing(self):
        self.stop_preview(show_static_frame=False)
        # Clean up the 'temp_edits' directory
        edits_dir = "temp_edits" # Path to the intermediate edits directory
        if os.path.exists(edits_dir):
            try:
                if messagebox.askyesno("Clean Up", f"Delete intermediate edited files from '{edits_dir}' folder?"):
                    shutil.rmtree(edits_dir)
                    print(f"Cleaned up temporary edit files in {edits_dir}")
            except Exception as e: 
                print(f"Error cleaning up temporary files from {edits_dir}: {e}")
        self.master.destroy()

# Note: The if __name__ == '__main__': block will be in the main executable script
# that initializes and runs the Tkinter application.
# For example, in a new video_editor_main.py (or similar)
#
# if __name__ == '__main__':
#     root = tk.Tk()
#     app = VideoEditorAppUI(root) # Assuming this class is VideoEditorAppUI
#     root.protocol("WM_DELETE_WINDOW", app.on_closing)
#     root.mainloop()
#
# This file (main_window.py) should only contain the class definition.
