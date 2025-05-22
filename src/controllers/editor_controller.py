"""
Editor Controller module for the video editor application.

This module provides the EditorController class, which acts as the central
coordinator between the MainView (UI), VideoState (model), and various
services (AI, Video Processing, Preview). It handles user interactions
from the view and orchestrates the application's logic.
"""
import os
import shutil
from src.models.video_state import VideoState
from src.services.ai_service import AIService
from src.services.video_processing_service import VideoProcessingService
from src.services.preview_service import PreviewService
from typing import TYPE_CHECKING, Optional # Optional is good for params that can be None

if TYPE_CHECKING:
    from src.views.main_view import MainView

class EditorController:
    """
    Connects the MainView with VideoState, AIService,
    VideoProcessingService, and PreviewService.
    """

    def __init__(self, view: 'MainView', video_state: VideoState, ai_service: AIService,
                 video_processing_service: VideoProcessingService, preview_service: PreviewService):
        self.view = view
        self.video_state = video_state
        self.ai_service = ai_service
        self.video_processing_service = video_processing_service
        self.preview_service = preview_service

        self.is_timeline_scrubbing: bool = False
        self.edits_dir: str = "_video_editor_edits"
        os.makedirs(self.edits_dir, exist_ok=True)

        # Connect PreviewService callbacks
        self.preview_service.ui_update_callback = self._on_preview_frame_update
        self.preview_service.ui_time_update_callback = self._on_preview_time_update
        self.preview_service.ui_playback_stopped_callback = self._on_preview_stopped

        # Initial UI state setup is deferred to main.py, after the view is fully assigned.
        # self.view.set_status("Welcome! Load a video to start.", "info")
        # if not self.ai_service.is_configured:
        #     self.view.set_status("Warning: GOOGLE_API_KEY not found or invalid. AI features disabled.", "warning")
        # self._update_all_button_states() # This will be called from main.py after view is set


    # --- Event Handler Methods (called by MainView) ---
    def handle_load_video(self):
        self.preview_service.release() # Release current video before loading new
        
        filepath = self.view.ask_open_filename(
            title="Select Video File",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv"), ("All files", "*.*")]
        )
        if not filepath:
            self.view.set_status("Video loading cancelled.", "warning")
            self._update_all_button_states() # Ensure buttons are correct if no video loaded
            return

        self.view.set_status(f"Loading '{os.path.basename(filepath)}'...", "info")
        if self.preview_service.load_video(filepath):
            self.video_state.set_original_video(filepath)
            self._update_view_for_new_video_data() # This updates duration, timeline, preview
            self.view.set_status("Video loaded: " + os.path.basename(filepath), "success")
        else:
            self.video_state.set_original_video(None) # Clear state if load failed
            self._update_view_for_new_video_data() # Clear UI elements
            self.view.show_error("Load Error", f"Could not load video: {filepath}")
            self.view.set_status(f"Error loading video: {os.path.basename(filepath)}", "error")
        
        self._update_all_button_states()

    def handle_apply_edit(self, command_text: str):
        current_input_path = self.video_state.get_current_path()
        if not current_input_path:
            self.view.show_error("Edit Error", "Please load a video first.")
            return

        if not command_text:
            self.view.set_status("Please enter an editing command.", "warning")
            return

        if not self.ai_service.is_configured:
            self.view.show_error("AI Error", "AI Service not configured (API Key missing or invalid).")
            self.view.set_status("AI Service not configured. Cannot process command.", "error")
            return

        self.view.set_status("Processing command with AI...", "info")
        edit_params = self.ai_service.parse_command_to_json(command_text)

        if not edit_params or edit_params.get("action") == "error":
            error_msg = edit_params.get('message', "AI command parsing failed or command not understood.")
            self.view.set_status(f"AI Error: {error_msg}", "error")
            self.view.show_error("AI Processing Error", error_msg)
            return

        action = edit_params.get("action")
        self.preview_service.pause() # Pause preview during processing

        # Handle actions requiring file dialogs from the view
        try:
            if action == "add_background_music" and "USER_SELECTS_MUSIC_FILE" in edit_params.get("music_path", ""):
                music_file = self.view.ask_open_filename("Select Background Music", [("Audio files", "*.mp3 *.wav *.aac")])
                if not music_file: self.view.set_status("Background music selection cancelled.", "warning"); return
                edit_params["music_path"] = music_file
            
            if action == "add_image_overlay" and "USER_SELECTS_IMAGE_FILE" in edit_params.get("image_path", ""):
                img_file = self.view.ask_open_filename("Select Image Overlay", [("Image files", "*.png *.jpg *.jpeg")])
                if not img_file: self.view.set_status("Image overlay selection cancelled.", "warning"); return
                edit_params["image_path"] = img_file

            if action == "picture_in_picture" and "USER_SELECTS_PIP_VIDEO_FILE" in edit_params.get("overlay_video_path", ""):
                pip_video_file = self.view.ask_open_filename("Select PiP Video", [("Video files", "*.mp4 *.avi *.mov")])
                if not pip_video_file: self.view.set_status("PiP video selection cancelled.", "warning"); return
                edit_params["overlay_video_path"] = pip_video_file
            
            if action == "concatenate" and any("USER_SELECTS_VIDEO_FILE_TO_APPEND" in p for p in edit_params.get("videos_to_append", [])):
                selected_videos_for_concat = []
                for i, p_param in enumerate(edit_params.get("videos_to_append",[])):
                    if "USER_SELECTS_VIDEO_FILE_TO_APPEND" in p_param:
                        vid_file = self.view.ask_open_filename(f"Select Video {i+1} to Append", [("Video files", "*.mp4")])
                        if not vid_file: self.view.set_status(f"Video {i+1} for concatenation cancelled.", "warning"); return
                        selected_videos_for_concat.append(vid_file)
                    else:
                        selected_videos_for_concat.append(p_param)
                edit_params["videos_to_append"] = selected_videos_for_concat

        except Exception as e_dialog: # Catch errors during file dialogs
            self.view.set_status(f"File selection error: {e_dialog}", "error")
            self.view.show_error("File Selection Error", str(e_dialog))
            return
        
        self.view.set_status(f"Applying '{action}'...", "info")
        
        original_basename, original_ext = os.path.splitext(os.path.basename(self.video_state.get_original_path() or "video"))
        output_filename = os.path.join(self.edits_dir, f"{original_basename}_edit_{self.video_state.edit_count + 1}_{action}{original_ext}")
        
        saved_path: Optional[str] = None
        
        try:
            if action == "extract_audio":
                default_audio_name = f"{original_basename}_audio.mp3"
                audio_output_path = self.view.ask_save_as_filename("Save Extracted Audio As", default_audio_name, ".mp3", [("MP3 audio", "*.mp3")])
                if audio_output_path:
                    self.video_processing_service.extract_audio(current_input_path, audio_output_path)
                    self.view.set_status(f"Audio extracted to: {os.path.basename(audio_output_path)}", "success")
                    # No change to video state, just update UI elements as they are
                    self._refresh_static_preview(self.preview_service.get_current_playback_time())
                else:
                    self.view.set_status("Audio extraction cancelled.", "warning")
                self.view.clear_edit_command()
                self._update_all_button_states()
                return # Special case, does not modify the video undo/redo stack for video edits

            # --- Call appropriate VideoProcessingService method ---
            # (Order based on AIService prompt for consistency)
            if action == "trim":
                saved_path = self.video_processing_service.apply_trim(
                    current_input_path, output_filename,
                    float(edit_params["start_time"]),
                    float(edit_params.get("end_time")) if edit_params.get("end_time") is not None else None
                )
            elif action == "speed":
                saved_path = self.video_processing_service.change_speed(
                    current_input_path, output_filename, float(edit_params["factor"])
                )
            elif action == "add_text":
                saved_path = self.video_processing_service.add_text(
                    current_input_path, output_filename,
                    edit_params["text_content"],
                    int(edit_params.get("font_size", 36)),
                    edit_params.get("color", "white"),
                    edit_params.get("position", "center"),
                    edit_params.get("font", "Arial"),
                    edit_params.get("stroke_color", "black"),
                    float(edit_params.get("stroke_width", 1.5)),
                    float(edit_params.get("start_time", 0)),
                    float(edit_params.get("duration")) if edit_params.get("duration") is not None else None
                )
            elif action == "mute_audio":
                saved_path = self.video_processing_service.mute_audio(current_input_path, output_filename)
            # extract_audio handled above
            elif action == "black_and_white":
                saved_path = self.video_processing_service.apply_black_and_white(current_input_path, output_filename)
            elif action == "invert_colors":
                saved_path = self.video_processing_service.invert_colors(current_input_path, output_filename)
            elif action == "gamma_correct":
                saved_path = self.video_processing_service.gamma_correct(
                    current_input_path, output_filename, float(edit_params.get("gamma_value", 1.0))
                )
            elif action == "adjust_volume":
                saved_path = self.video_processing_service.adjust_volume(
                    current_input_path, output_filename, float(edit_params.get("factor", 1.0))
                )
            elif action == "rotate":
                saved_path = self.video_processing_service.rotate_video(
                    current_input_path, output_filename, float(edit_params.get("angle", 0))
                )
            elif action == "fade_in":
                saved_path = self.video_processing_service.apply_fade_in(
                    current_input_path, output_filename, float(edit_params["duration"])
                )
            elif action == "fade_out":
                saved_path = self.video_processing_service.apply_fade_out(
                    current_input_path, output_filename, float(edit_params["duration"])
                )
            elif action == "mirror":
                saved_path = self.video_processing_service.mirror_video(
                    current_input_path, output_filename, edit_params.get("direction", "horizontal")
                )
            elif action == "normalize_audio":
                saved_path = self.video_processing_service.normalize_audio(current_input_path, output_filename)
            elif action == "add_background_music":
                 saved_path = self.video_processing_service.add_background_music(
                    current_input_path, output_filename,
                    edit_params["music_path"], # Should be resolved by now
                    float(edit_params.get("volume_factor", 0.3)),
                    float(edit_params.get("music_start_time_in_video", 0)),
                    bool(edit_params.get("music_loop", False))
                )
            elif action == "add_image_overlay":
                saved_path = self.video_processing_service.add_image_overlay(
                    current_input_path, output_filename,
                    edit_params["image_path"], # Should be resolved
                    edit_params.get("position", "bottom_right"),
                    edit_params.get("size_factor"), 
                    float(edit_params.get("opacity", 0.8)),
                    float(edit_params.get("start_time", 0)),
                    float(edit_params.get("duration")) if edit_params.get("duration") is not None else None
                )
            elif action == "picture_in_picture":
                saved_path = self.video_processing_service.apply_picture_in_picture(
                    current_input_path, output_filename,
                    edit_params["overlay_video_path"], # Should be resolved
                    edit_params.get("position", "top_right"),
                    edit_params.get("size_factor"), 
                    float(edit_params.get("start_time", 0)),
                    float(edit_params.get("duration")) if edit_params.get("duration") is not None else None
                )
            elif action == "blur":
                saved_path = self.video_processing_service.blur_video(
                    current_input_path, output_filename, int(edit_params.get("radius", 2))
                )
            elif action == "concatenate":
                saved_path = self.video_processing_service.concatenate_videos(
                    current_input_path, edit_params["videos_to_append"], output_filename # Resolved paths
                )
            else:
                self.view.set_status(f"Error: Action '{action}' is not recognized by the controller.", "error")
                self.view.show_error("Internal Error", f"Action '{action}' not implemented in controller.")

        except FileNotFoundError as e_fnf:
            self.view.set_status(f"Edit Error: {e_fnf}", "error")
            self.view.show_error(f"File Error ({action})", str(e_fnf))
            saved_path = None
        except (ValueError, RuntimeError) as e_proc: # Errors from VideoProcessingService or parameter issues
            self.view.set_status(f"Processing Error ({action}): {e_proc}", "error")
            self.view.show_error(f"Error during {action}", str(e_proc))
            saved_path = None
        except Exception as e_unexpected: # Catch any other unexpected errors
            self.view.set_status(f"Unexpected Error ({action}): {e_unexpected}", "error")
            self.view.show_error("Unexpected Error", f"An unexpected error occurred: {e_unexpected}")
            saved_path = None


        if saved_path and os.path.exists(saved_path):
            self.video_state.add_edit(saved_path)
            self._update_view_for_new_video_data() # Reloads preview with new video
            self.view.set_status(f"Edit '{action}' applied: {os.path.basename(saved_path)}", "success")
        elif action != "extract_audio": # extract_audio has its own success/fail messages
            self.view.set_status(f"Failed to apply edit: {action}. Output file not created or error occurred.", "error")
            # Re-load current state to ensure preview is consistent if edit failed
            self._update_view_for_new_video_data() 


        self.view.clear_edit_command()
        self._update_all_button_states()


    def handle_export_video(self):
        current_video = self.video_state.get_current_path()
        if not current_video or not os.path.exists(current_video):
            self.view.show_error("Export Error", "No current video to export or file not found.")
            self.view.set_status("Export failed: No valid video loaded.", "error")
            return

        original_name_base = os.path.splitext(os.path.basename(self.video_state.get_original_path() or "edited_video"))[0]
        default_export_name = f"{original_name_base}_exported.mp4"
        
        export_filepath = self.view.ask_save_as_filename(
            "Export Video As", default_export_name, ".mp4", [("MP4 video", "*.mp4")]
        )

        if export_filepath:
            try:
                self.view.set_status(f"Exporting to {os.path.basename(export_filepath)}...", "info")
                shutil.copy(current_video, export_filepath)
                self.view.set_status(f"Video exported successfully: {os.path.basename(export_filepath)}", "success")
                self.view.show_info("Export Success", f"Video saved to:\n{export_filepath}")
            except Exception as e:
                self.view.set_status(f"Export failed: {e}", "error")
                self.view.show_error("Export Error", f"Could not export video: {e}")
        else:
            self.view.set_status("Export cancelled.", "warning")

    def handle_undo_action(self):
        self.preview_service.release() # Stop and release before changing video
        undone_path = self.video_state.undo()
        if undone_path:
            self._update_view_for_new_video_data()
            self.view.set_status(f"Undo: Now at {os.path.basename(undone_path)}", "info")
        else:
            self.view.set_status("Nothing to undo.", "warning")
        self._update_all_button_states()

    def handle_redo_action(self):
        self.preview_service.release()
        redone_path = self.video_state.redo()
        if redone_path:
            self._update_view_for_new_video_data()
            self.view.set_status(f"Redo: Now at {os.path.basename(redone_path)}", "info")
        else:
            self.view.set_status("Nothing to redo.", "warning")
        self._update_all_button_states()

    def handle_play_preview(self):
        if self.preview_service.is_active():
            current_timeline_pos = self.preview_service.get_current_playback_time()
            self.preview_service.play(start_time_sec=current_timeline_pos)
            self.view.set_status("Playing preview...", "info")
            self._update_all_button_states()

    def handle_pause_preview(self):
        self.preview_service.pause()
        self.view.set_status("Preview paused.", "info")
        self._update_all_button_states()
        # Update static frame to show exactly where it paused
        self._refresh_static_preview(self.preview_service.get_current_playback_time())


    def handle_stop_preview(self):
        self.preview_service.stop() # This will trigger _on_preview_stopped callback
        # Callback handles status update and button state update.
        # PreviewService.stop() also seeks to 0.0.

    def handle_timeline_scrub_start(self):
        self.is_timeline_scrubbing = True
        if self.preview_service.is_playing:
             self.preview_service.pause() # Pause playback if user starts scrubbing

    def handle_timeline_scrub_end(self, seek_time_sec: float):
        self.is_timeline_scrubbing = False
        self.preview_service.seek(seek_time_sec) # Ensure service internal time is set
        self._refresh_static_preview(seek_time_sec)
        # Do not automatically resume playback, user can press play.
        self._update_all_button_states()


    def handle_timeline_seek(self, seek_time_sec: float):
        # This is called by Scale's `command` when not scrubbing (e.g. programmatic change, or if user clicks on scale)
        if not self.is_timeline_scrubbing:
            if self.preview_service.is_playing:
                self.preview_service.pause() # Pause if was playing
            
            self.preview_service.seek(seek_time_sec)
            self._refresh_static_preview(seek_time_sec)
            self._update_all_button_states()


    def handle_on_close(self):
        self.preview_service.release()
        cleanup_confirmed = self.view.ask_yes_no(
            "Clean Up",
            f"Delete intermediate edited files from '{os.path.basename(self.edits_dir)}' folder?"
        )
        if cleanup_confirmed:
            if os.path.exists(self.edits_dir):
                try:
                    shutil.rmtree(self.edits_dir)
                    self.view.set_status(f"Cleaned up {self.edits_dir}.", "info")
                    print(f"Cleaned up temporary edit files in {self.edits_dir}")
                except Exception as e:
                    print(f"Error cleaning up temporary files: {e}")
                    self.view.show_error("Cleanup Error", f"Error cleaning up temp files: {e}")
            else:
                 self.view.set_status("Temporary edits folder not found, no cleanup needed.", "info")
        else:
            self.view.set_status("Temporary edit files were not deleted.", "info")
        
        self.view.root.destroy() # Close the Tkinter window

    # --- Internal Helper Methods ---
    def _refresh_static_preview(self, time_sec: Optional[float] = None):
        if not self.preview_service.is_active():
            self.view.display_preview_image(None)
            self.view.update_time_display(0,0)
            self.view.update_timeline_slider(0) # Reset slider position
            return

        target_time = time_sec if time_sec is not None else self.preview_service.get_current_playback_time()
        
        preview_width, preview_height = self.view.get_preview_dimensions()
        self.preview_service.set_preview_dimensions(preview_width, preview_height)
        
        frame = self.preview_service.get_static_frame(target_time)
        self.view.display_preview_image(frame)
        
        actual_preview_time = self.preview_service.get_current_playback_time() # Time after seek/frame grab
        total_duration = self.preview_service.get_total_duration()
        
        self.view.update_time_display(actual_preview_time, total_duration)
        if not self.is_timeline_scrubbing : # Avoid fighting user dragging the scale
            self.view.update_timeline_slider(actual_preview_time)


    def _update_all_button_states(self):
        video_loaded = self.preview_service.is_active()
        is_playing = self.preview_service.is_playing

        self.view.update_playback_buttons_state(
            can_play=video_loaded and not is_playing,
            can_pause=is_playing,
            can_stop=video_loaded, # Can always stop if video is loaded (resets to start)
            timeline_enabled=video_loaded
        )
        self.view.update_undo_redo_buttons_state(
            can_undo=self.video_state.can_undo(),
            can_redo=self.video_state.can_redo()
        )

    def _update_view_for_new_video_data(self):
        path_to_load = self.video_state.get_current_path()
        if path_to_load and os.path.exists(path_to_load):
            if self.preview_service.load_video(path_to_load): # load_video also updates PreviewService's duration
                duration = self.preview_service.get_total_duration()
                self.video_state.set_duration(duration) # Sync VideoState's duration
                
                self.view.update_video_path_label(os.path.basename(path_to_load))
                self.view.update_timeline_range(duration if duration > 0 else 100.0)
                self._refresh_static_preview(0.0) # Show first frame
            else: # Should not happen if path_to_load is valid and from a successful edit
                self.view.show_error("Load Error", f"Failed to load '{os.path.basename(path_to_load)}' into preview.")
                self.view.update_video_path_label("Error loading video")
                self.view.update_timeline_range(0)
                self.view.display_preview_image(None)
                self.view.update_time_display(0,0)
        else: # No current path (e.g., all edits undone, or initial state)
            self.preview_service.release() # Ensure preview service is reset
            self.view.update_video_path_label("No video loaded")
            self.view.update_timeline_range(0) # Or a default like 100
            self.view.display_preview_image(None)
            self.view.update_time_display(0,0)
            self.video_state.set_duration(0) # Reset duration in model too
        
        self._update_all_button_states()


    # --- PreviewService Callback Implementations ---
    def _on_preview_frame_update(self, pil_image):
        self.view.display_preview_image(pil_image)

    def _on_preview_time_update(self, current_time: float, total_time: float):
        self.view.update_time_display(current_time, total_time)
        if not self.is_timeline_scrubbing:
            self.view.update_timeline_slider(current_time)
        # Sync VideoState duration if PreviewService discovers a more accurate one
        if total_time > 0 and self.video_state.get_duration() != total_time:
            self.video_state.set_duration(total_time)
            self.view.update_timeline_range(total_time)


    def _on_preview_stopped(self):
        self.view.set_status("Preview stopped.", "info")
        self._update_all_button_states()
        # Update static frame to where playback stopped or was reset by stop()
        self._refresh_static_preview(self.preview_service.get_current_playback_time())
