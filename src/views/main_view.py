"""
Main View module for the Tkinter-based UI of the video editor.

This module provides the MainView class, which is responsible for
creating and managing all UI elements, displaying information to the user,
and forwarding user actions (e.g., button clicks, timeline interactions)
to the EditorController.
"""
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import src.config as config
from src.utils import format_time

class MainView:
    """Manages the Tkinter UI, displays information, and forwards user actions to a controller."""

    def __init__(self, controller):
        self.controller = controller
        self.root = tk.Tk()
        self.root.title("Prompt-Based Video Editor (Refactored)")
        self.root.geometry("1000x800")
        self.root.configure(bg=config.BG_COLOR)

        self.preview_image_ref = None # To keep a reference to the PhotoImage
        self.is_scrubbing_timeline = False # Internal state for timeline interaction

        # Initialize attributes for widgets that will be dynamically updated
        self.video_path_label = None
        self.status_label = None
        self.edit_entry = None
        self.preview_label = None
        self.timeline_scale = None
        self.time_display_label = None
        self.load_button = None
        self.undo_button = None
        self.redo_button = None
        self.apply_button = None
        self.export_button = None
        self.play_button = None
        self.pause_button = None
        self.stop_button = None
        
        self._setup_ui()

    def _setup_ui(self):
        # --- Top Frame ---
        top_controls_frame = tk.Frame(self.root, bg=config.BG_COLOR, pady=10, padx=10)
        top_controls_frame.pack(fill=tk.X)

        self.load_button = tk.Button(top_controls_frame, text="Load Video",
                                     command=self.controller.handle_load_video,
                                     bg=config.BUTTON_BG_COLOR, fg=config.BUTTON_FG_COLOR,
                                     relief=tk.FLAT, activebackground=config.ACCENT_COLOR)
        self.load_button.pack(side=tk.LEFT, padx=(0, 5))

        self.video_path_label = tk.Label(top_controls_frame, text="No video loaded", relief=tk.SUNKEN,
                                         anchor=tk.W, padx=5, bg=config.BG_COLOR,
                                         fg=config.FG_COLOR_LIGHT, width=40)
        self.video_path_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.undo_button = tk.Button(top_controls_frame, text="Undo",
                                     command=self.controller.handle_undo_action,
                                     bg=config.BUTTON_BG_COLOR, fg=config.BUTTON_FG_COLOR,
                                     relief=tk.FLAT, activebackground=config.ACCENT_COLOR)
        self.undo_button.pack(side=tk.LEFT, padx=5)

        self.redo_button = tk.Button(top_controls_frame, text="Redo",
                                     command=self.controller.handle_redo_action,
                                     bg=config.BUTTON_BG_COLOR, fg=config.BUTTON_FG_COLOR,
                                     relief=tk.FLAT, activebackground=config.ACCENT_COLOR)
        self.redo_button.pack(side=tk.LEFT, padx=5)

        # --- Middle Frame ---
        middle_frame = tk.Frame(self.root, bg=config.BG_COLOR, padx=5, pady=5)
        middle_frame.pack(fill=tk.BOTH, expand=True)

        # Left Sub-Frame (Editing Controls)
        edit_controls_frame = tk.Frame(middle_frame, bg=config.BG_COLOR, padx=10)
        edit_controls_frame.pack(side=tk.LEFT, fill=tk.Y, anchor=tk.N)

        tk.Label(edit_controls_frame, text="Enter Editing Command:", bg=config.BG_COLOR,
                 fg=config.FG_COLOR_LIGHT).pack(anchor=tk.W, pady=(0, 2))
        self.edit_entry = tk.Entry(edit_controls_frame, width=40, bg=config.FG_COLOR_LIGHT,
                                   fg=config.BG_COLOR, insertbackground=config.BG_COLOR)
        self.edit_entry.pack(pady=5, fill=tk.X)

        self.apply_button = tk.Button(edit_controls_frame, text="Apply Edit",
                                      command=self._on_apply_edit_clicked,
                                      bg=config.ACCENT_COLOR, fg=config.BUTTON_FG_COLOR,
                                      relief=tk.FLAT, padx=10, activebackground="#005f9e")
        self.apply_button.pack(pady=10, fill=tk.X)

        self.export_button = tk.Button(edit_controls_frame, text="Export Video As...",
                                       command=self.controller.handle_export_video,
                                       bg=config.BUTTON_BG_COLOR, fg=config.BUTTON_FG_COLOR,
                                       relief=tk.FLAT, padx=10, activebackground=config.ACCENT_COLOR)
        self.export_button.pack(pady=10, fill=tk.X)

        # Right Sub-Frame (Preview Area)
        preview_area_frame = tk.Frame(middle_frame, bg=config.BG_COLOR)
        preview_area_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        tk.Label(preview_area_frame, text="Video Preview:", anchor=tk.N, bg=config.BG_COLOR,
                 fg=config.FG_COLOR_LIGHT).pack(pady=(5, 2))
        self.preview_label = tk.Label(preview_area_frame, bg=config.PREVIEW_BG_COLOR, relief=tk.SUNKEN)
        self.preview_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Timeline
        self.timeline_scale = tk.Scale(preview_area_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                                       showvalue=0, sliderrelief=tk.FLAT,
                                       command=self._on_timeline_seek, # This is called when value changes, including on release
                                       bg=config.TIMELINE_BG, fg=config.FG_COLOR_LIGHT,
                                       troughcolor=config.TIMELINE_TROUGH, activebackground=config.ACCENT_COLOR,
                                       length=300, relief=tk.GROOVE, bd=1)
        self.timeline_scale.pack(fill=tk.X, padx=5, pady=(0, 0))
        self.timeline_scale.bind("<ButtonPress-1>", self._on_timeline_press)
        self.timeline_scale.bind("<ButtonRelease-1>", self._on_timeline_release)

        # Playback Controls & Time Display Frame
        playback_and_time_frame = tk.Frame(preview_area_frame, bg=config.BG_COLOR)
        playback_and_time_frame.pack(fill=tk.X, pady=2)

        self.play_button = tk.Button(playback_and_time_frame, text="▶ Play",
                                     command=self.controller.handle_play_preview,
                                     bg=config.BUTTON_BG_COLOR, fg=config.BUTTON_FG_COLOR,
                                     relief=tk.FLAT, activebackground=config.ACCENT_COLOR)
        self.play_button.pack(side=tk.LEFT, padx=5)

        self.pause_button = tk.Button(playback_and_time_frame, text="❚❚ Pause",
                                      command=self.controller.handle_pause_preview,
                                      bg=config.BUTTON_BG_COLOR, fg=config.BUTTON_FG_COLOR,
                                      relief=tk.FLAT, activebackground=config.ACCENT_COLOR)
        self.pause_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = tk.Button(playback_and_time_frame, text="■ Stop",
                                     command=self.controller.handle_stop_preview,
                                     bg=config.BUTTON_BG_COLOR, fg=config.BUTTON_FG_COLOR,
                                     relief=tk.FLAT, activebackground=config.ACCENT_COLOR)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.time_display_label = tk.Label(playback_and_time_frame, text="00:00 / 00:00",
                                           bg=config.BG_COLOR, fg=config.FG_COLOR_LIGHT, padx=10)
        self.time_display_label.pack(side=tk.RIGHT)

        # --- Bottom Frame (Status) ---
        status_frame = tk.Frame(self.root, relief=tk.SUNKEN, bd=1, bg=config.STATUS_BG_COLOR)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_label = tk.Label(status_frame, text="Welcome! Load a video to start.",
                                     anchor=tk.W, padx=5, pady=3,
                                     bg=config.STATUS_BG_COLOR, fg=config.FG_COLOR_LIGHT)
        self.status_label.pack(fill=tk.X)

    # --- Internal Event Handlers ---
    def _on_apply_edit_clicked(self):
        command_text = self.edit_entry.get()
        self.controller.handle_apply_edit(command_text)

    def _on_timeline_seek(self, value_str: str):
        # This is called when the scale's value changes, either by user release or programmatically.
        # We only want to act if it's NOT during a user drag (scrub).
        if not self.is_scrubbing_timeline:
            self.controller.handle_timeline_seek(float(value_str))

    def _on_timeline_press(self, event):
        self.is_scrubbing_timeline = True
        self.controller.handle_timeline_scrub_start()

    def _on_timeline_release(self, event):
        self.is_scrubbing_timeline = False
        value_str = self.timeline_scale.get()
        self.controller.handle_timeline_scrub_end(float(value_str))

    # --- UI Update Methods (callable by the Controller) ---
    def update_video_path_label(self, path_text: str):
        if self.video_path_label:
            self.video_path_label.config(text=path_text)

    def set_status(self, text: str, msg_type: str = "info"):
        if self.status_label:
            color = config.FG_COLOR_LIGHT # Default
            if msg_type == "error": color = config.ERROR_FG_COLOR
            elif msg_type == "success": color = config.SUCCESS_FG_COLOR
            elif msg_type == "warning": color = config.WARNING_FG_COLOR
            self.status_label.config(text=text, fg=color)

    def display_preview_image(self, pil_image: Image.Image | None):
        if self.preview_label:
            if pil_image:
                self.preview_image_ref = ImageTk.PhotoImage(pil_image)
                self.preview_label.config(image=self.preview_image_ref, text="")
            else:
                self.preview_label.config(image='', text="No preview available")
                self.preview_image_ref = None # Clear reference

    def update_timeline_slider(self, value: float):
        if self.timeline_scale:
            # Only set if not currently being dragged by user, to avoid fighting user input
            if not self.is_scrubbing_timeline:
                 self.timeline_scale.set(value)

    def update_timeline_range(self, max_value: float):
        if self.timeline_scale:
            self.timeline_scale.config(to=max_value if max_value > 0 else 100.0) # Scale 'to' must be > 'from' (0)

    def update_time_display(self, current_time_sec: float, total_duration_sec: float):
        if self.time_display_label:
            self.time_display_label.config(
                text=f"{format_time(current_time_sec)} / {format_time(total_duration_sec)}"
            )

    def get_edit_command(self) -> str:
        return self.edit_entry.get() if self.edit_entry else ""

    def clear_edit_command(self):
        if self.edit_entry:
            self.edit_entry.delete(0, tk.END)

    def update_playback_buttons_state(self, can_play: bool, can_pause: bool, can_stop: bool, timeline_enabled: bool):
        if self.play_button: self.play_button.config(state=tk.NORMAL if can_play else tk.DISABLED)
        if self.pause_button: self.pause_button.config(state=tk.NORMAL if can_pause else tk.DISABLED)
        if self.stop_button: self.stop_button.config(state=tk.NORMAL if can_stop else tk.DISABLED)
        if self.timeline_scale: self.timeline_scale.config(state=tk.NORMAL if timeline_enabled else tk.DISABLED)

    def update_undo_redo_buttons_state(self, can_undo: bool, can_redo: bool):
        if self.undo_button: self.undo_button.config(state=tk.NORMAL if can_undo else tk.DISABLED)
        if self.redo_button: self.redo_button.config(state=tk.NORMAL if can_redo else tk.DISABLED)

    def get_preview_dimensions(self) -> tuple[int, int]:
        # Ensure the label has had a chance to be drawn and has valid dimensions
        self.preview_label.update_idletasks() # Crucial for getting correct winfo_width/height
        width = self.preview_label.winfo_width()
        height = self.preview_label.winfo_height()
        
        # Subtract a bit for padding/border if any, though Label usually gives usable area
        # Default to a reasonable size if winfo returns 1 (common for unmapped widgets)
        # These values should match some default expectation if the label isn't rendered yet.
        return (width if width > 1 else 640, height if height > 1 else 480)


    # --- Dialog Wrappers (callable by Controller) ---
    def show_error(self, title: str, message: str):
        messagebox.showerror(title, message, parent=self.root)

    def show_info(self, title: str, message: str):
        messagebox.showinfo(title, message, parent=self.root)
    
    def show_warning(self, title: str, message: str): # Added for completeness
        messagebox.showwarning(title, message, parent=self.root)

    def ask_yes_no(self, title: str, message: str) -> bool:
        return messagebox.askyesno(title, message, parent=self.root)

    def ask_open_filename(self, title: str, filetypes: list) -> str | None:
        # Temporarily make status bar say something useful during file dialog
        original_status = self.status_label.cget("text")
        original_fg = self.status_label.cget("fg")
        self.set_status(f"Waiting for file selection: {title}...", "info")
        self.root.update_idletasks() # Force UI update

        filepath = filedialog.askopenfilename(title=title, filetypes=filetypes, parent=self.root)
        
        # Restore original status or set new one
        if filepath:
            self.set_status(f"File selected: {filepath.split('/')[-1]}", "info")
        else:
            self.set_status(f"{title} cancelled.", "warning")
        # If there was a specific status before, this might overwrite it.
        # Consider a more robust status management if needed.
        return filepath

    def ask_save_as_filename(self, title: str, initialfile: str, defaultextension: str, filetypes: list) -> str | None:
        original_status = self.status_label.cget("text")
        original_fg = self.status_label.cget("fg")
        self.set_status(f"Waiting for save location: {title}...", "info")
        self.root.update_idletasks()

        filepath = filedialog.asksaveasfilename(title=title, initialfile=initialfile,
                                                defaultextension=defaultextension, filetypes=filetypes, parent=self.root)
        if filepath:
            self.set_status(f"Output file selected: {filepath.split('/')[-1]}", "info")
        else:
            self.set_status(f"{title} cancelled.", "warning")
        return filepath

    # --- Lifecycle Methods ---
    def start_mainloop(self):
        self.root.mainloop()

    def set_on_closing_callback(self, callback):
        self.root.protocol("WM_DELETE_WINDOW", callback)

# Example of how the MainView might be instantiated (for testing purposes)
if __name__ == '__main__':
    # A dummy controller for testing the view standalone
    class DummyController:
        def handle_load_video(self): print("Dummy: Load Video clicked")
        def handle_apply_edit(self, cmd): print(f"Dummy: Apply Edit clicked with '{cmd}'")
        def handle_export_video(self): print("Dummy: Export Video clicked")
        def handle_undo_action(self): print("Dummy: Undo clicked")
        def handle_redo_action(self): print("Dummy: Redo clicked")
        def handle_play_preview(self): print("Dummy: Play clicked")
        def handle_pause_preview(self): print("Dummy: Pause clicked")
        def handle_stop_preview(self): print("Dummy: Stop clicked")
        def handle_timeline_seek(self, val): print(f"Dummy: Timeline seek to {val}")
        def handle_timeline_scrub_start(self): print("Dummy: Timeline scrub start")
        def handle_timeline_scrub_end(self, val): print(f"Dummy: Timeline scrub end at {val}")
        def handle_on_closing(self): print("Dummy: Closing window"); app_view.root.destroy()

    print("Initializing MainView with DummyController...")
    dummy_controller = DummyController()
    app_view = MainView(dummy_controller)
    app_view.set_on_closing_callback(dummy_controller.handle_on_closing)
    
    # Test some UI update methods
    app_view.set_status("Testing status update from MainView __main__.", "success")
    app_view.update_video_path_label("test_video.mp4")
    app_view.update_time_display(10, 60)
    app_view.update_timeline_range(60)
    app_view.update_timeline_slider(10)
    app_view.update_playback_buttons_state(True, False, True, True)
    app_view.update_undo_redo_buttons_state(True, False)

    # Simulate showing a preview image (requires a dummy image)
    try:
        dummy_pil_image = Image.new('RGB', (100, 100), color = 'blue')
        app_view.display_preview_image(dummy_pil_image)
        print("Dummy preview image displayed.")
    except Exception as e:
        print(f"Could not create/display dummy PIL image: {e}")

    print("Starting MainView mainloop...")
    app_view.start_mainloop()
    print("MainView mainloop finished.")
