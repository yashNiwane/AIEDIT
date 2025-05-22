"""
Preview Service module for handling video playback and frame extraction using OpenCV.

This module provides the PreviewService class, which is responsible for
loading videos, generating preview frames (static and during playback),
and managing playback state (play, pause, stop, seek) via OpenCV.
It uses threading for non-blocking playback.
"""
import cv2
import threading
import time
from PIL import Image # ImageTk is not used here, only PIL.Image

class PreviewService:
    """Manages video preview generation and playback using OpenCV."""

    def __init__(self, ui_update_callback=None, ui_time_update_callback=None, ui_playback_stopped_callback=None):
        """
        Initializes the PreviewService.

        Args:
            ui_update_callback: Callback function that takes a PIL.Image.Image argument to update the UI.
            ui_time_update_callback: Callback function that takes (current_time_sec, total_duration_sec) to update UI time display.
            ui_playback_stopped_callback: Callback function to notify UI when playback has completely stopped.
        """
        self.ui_update_callback = ui_update_callback
        self.ui_time_update_callback = ui_time_update_callback
        self.ui_playback_stopped_callback = ui_playback_stopped_callback # Added for better UI sync

        self.preview_cap = None
        self.is_playing: bool = False
        self.preview_thread: threading.Thread | None = None
        self.current_video_path: str | None = None
        self.total_duration_sec: float = 0.0
        self.fps: float = 30.0
        self.target_preview_width: int = 640
        self.target_preview_height: int = 480

    def load_video(self, video_path: str) -> bool:
        """
        Loads a video file for preview.

        Args:
            video_path: Path to the video file.

        Returns:
            True if video loaded successfully, False otherwise.
        """
        self.release()  # Clean up any existing resources

        if not os.path.exists(video_path):
            print(f"Error: Video file not found at {video_path}")
            return False

        self.current_video_path = video_path
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"Error: Could not open video file: {video_path}")
                self.current_video_path = None
                return False

            self.preview_cap = cap
            frame_count = self.preview_cap.get(cv2.CAP_PROP_FRAME_COUNT)
            cap_fps = self.preview_cap.get(cv2.CAP_PROP_FPS)

            if cap_fps > 0:
                self.fps = cap_fps
                if frame_count > 0:
                    self.total_duration_sec = frame_count / self.fps
                else: # Frame count might be unreliable for some formats/backends
                    self.total_duration_sec = 0.0 # Or try to estimate, but 0 is safer
                    print(f"Warning: Could not get frame count for {video_path}. Duration may be incorrect.")

            else: # FPS is 0 or invalid
                self.fps = 30.0 # Default
                # If FPS is 0, duration calculation is problematic.
                # For some streams, frame_count / fps might not be accurate.
                # It's better to indicate duration might be unknown or rely on seeking.
                self.total_duration_sec = 0.0
                print(f"Warning: Could not get valid FPS for {video_path}. Using default {self.fps}fps. Duration may be incorrect.")
            
            # Attempt a first read to confirm validity for some backends
            ret, _ = self.preview_cap.read()
            if not ret:
                print(f"Error: Could not read the first frame from {video_path}. Video might be corrupted or format unsupported.")
                self.release()
                return False
            self.seek(0) # Reset to beginning after the test read

            print(f"Video loaded: {video_path}, Duration: {self.total_duration_sec:.2f}s, FPS: {self.fps:.2f}")
            return True

        except Exception as e:
            print(f"Exception loading video {video_path}: {e}")
            self.release()
            return False

    def set_preview_dimensions(self, width: int, height: int):
        """Sets the target dimensions for preview frames."""
        if width > 0: self.target_preview_width = width
        if height > 0: self.target_preview_height = height

    def get_static_frame(self, time_sec: float = 0.0) -> Image.Image | None:
        """
        Gets a single frame from the video at a specific time.

        Args:
            time_sec: The time (in seconds) from which to grab the frame.

        Returns:
            A PIL.Image.Image object or None if failed.
        """
        if not self.is_active():
            # print("Debug: get_static_frame called but preview_cap is not active.")
            return None
        
        # Ensure time_sec is within valid range
        time_sec = max(0.0, min(time_sec, self.total_duration_sec if self.total_duration_sec > 0 else float('inf')))

        try:
            self.preview_cap.set(cv2.CAP_PROP_POS_MSEC, int(time_sec * 1000))
            ret, frame = self.preview_cap.read()

            if ret and frame is not None:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_image = Image.fromarray(rgb_frame)
                pil_image.thumbnail((self.target_preview_width, self.target_preview_height), Image.Resampling.LANCZOS)
                return pil_image
            else:
                # print(f"Debug: Failed to read frame at {time_sec}s. Ret: {ret}")
                return None
        except Exception as e:
            print(f"Error getting static frame at {time_sec}s: {e}")
            return None

    def play(self, start_time_sec: float = None):
        """Starts playback of the video from a specified time."""
        if self.is_active() and not self.is_playing:
            if start_time_sec is not None:
                self.seek(start_time_sec)
            
            self.is_playing = True
            # Ensure previous thread is cleaned up if it somehow exists and is dead
            if self.preview_thread and not self.preview_thread.is_alive():
                self.preview_thread.join(timeout=0.1) # Quick join attempt

            self.preview_thread = threading.Thread(target=self._playback_loop, daemon=True)
            self.preview_thread.start()
            print(f"Playback started from {start_time_sec if start_time_sec is not None else self.get_current_playback_time():.2f}s")
        elif self.is_playing:
            print("Info: Play called but already playing.")
        elif not self.is_active():
            print("Warning: Play called but no video loaded or cap not active.")


    def _playback_loop(self):
        """Internal loop for video playback, run in a separate thread."""
        print("Playback loop started.")
        initial_start_time_video_sec = self.get_current_playback_time()

        while self.is_playing and self.is_active():
            loop_iter_start_time = time.perf_counter()
            
            ret, frame = self.preview_cap.read()
            if not ret or frame is None:
                print("Playback loop: End of video or read error.")
                break 

            # Process frame
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_image = Image.fromarray(rgb_frame)
            pil_image.thumbnail((self.target_preview_width, self.target_preview_height), Image.Resampling.LANCZOS)

            current_pos_msec = self.preview_cap.get(cv2.CAP_PROP_POS_MSEC)
            current_pos_sec = current_pos_msec / 1000.0

            if self.ui_update_callback:
                try:
                    self.ui_update_callback(pil_image)
                except Exception as e_ui_update: # Catch errors in UI callback
                    print(f"Error in ui_update_callback: {e_ui_update}")
            
            if self.ui_time_update_callback:
                try:
                    self.ui_time_update_callback(current_pos_sec, self.total_duration_sec)
                except Exception as e_ui_time:
                    print(f"Error in ui_time_update_callback: {e_ui_time}")

            # Frame rate control
            # elapsed_iter_time = time.perf_counter() - loop_iter_start_time
            # time_to_sleep = (1.0 / self.fps) - elapsed_iter_time
            # More robust sync:
            expected_next_frame_time_video = initial_start_time_video_sec + (time.perf_counter() - loop_iter_start_time)
            # This simple sleep is often good enough if processing is fast
            time_to_sleep = (1.0 / self.fps) - (time.perf_counter() - loop_iter_start_time)


            if time_to_sleep > 0:
                time.sleep(time_to_sleep)
        
        # Playback finished or stopped
        self.is_playing = False
        print("Playback loop ended.")
        if self.ui_playback_stopped_callback:
            try:
                self.ui_playback_stopped_callback()
            except Exception as e_stopped_cb:
                print(f"Error in ui_playback_stopped_callback: {e_stopped_cb}")


    def pause(self):
        """Pauses video playback."""
        if self.is_playing:
            self.is_playing = False
            print("Playback paused.")
            # Thread will see self.is_playing is False and exit loop.
            # Consider joining thread here if immediate pause feedback is critical,
            # but usually letting the loop finish its current iteration is fine.
            # if self.preview_thread and self.preview_thread.is_alive():
            # self.preview_thread.join(timeout=0.5) # Wait briefly for thread to stop

    def stop(self):
        """Stops video playback and resets to the beginning."""
        if self.is_playing:
            self.is_playing = False
            print("Playback stopping...")
            if self.preview_thread and self.preview_thread.is_alive():
                 self.preview_thread.join(timeout=0.5) # Wait for thread to finish current iteration
        
        if self.is_active():
            current_seek_pos = self.seek(0.0)
            print(f"Playback stopped and seeked to {current_seek_pos:.2f}s.")
        else:
            print("Stop called but no active video.")


    def seek(self, time_sec: float) -> float:
        """
        Seeks to a specific time in the video.

        Args:
            time_sec: The time (in seconds) to seek to.

        Returns:
            The actual time (in seconds) after seeking, or 0.0 if failed.
        """
        if self.is_active():
            # Ensure time_sec is within valid range, especially if total_duration_sec is known and positive
            if self.total_duration_sec > 0:
                time_sec = max(0.0, min(time_sec, self.total_duration_sec - 0.01)) # -0.01 to avoid seeking exactly to end for some videos
            else:
                time_sec = max(0.0, time_sec)

            try:
                self.preview_cap.set(cv2.CAP_PROP_POS_MSEC, int(time_sec * 1000))
                actual_pos_msec = self.preview_cap.get(cv2.CAP_PROP_POS_MSEC)
                return actual_pos_msec / 1000.0
            except Exception as e:
                print(f"Error during seek to {time_sec}s: {e}")
                return self.get_current_playback_time() # return current time if seek fails
        return 0.0

    def get_current_playback_time(self) -> float:
        """Returns the current playback time in seconds."""
        if self.is_active() and self.preview_cap:
            try:
                return self.preview_cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            except Exception: # Catch potential cv2 errors if cap becomes invalid
                return 0.0
        return 0.0

    def get_total_duration(self) -> float:
        """Returns the total duration of the loaded video in seconds."""
        return self.total_duration_sec

    def is_active(self) -> bool:
        """Checks if a video is loaded and the capture object is opened."""
        return self.preview_cap is not None and self.preview_cap.isOpened()

    def release(self):
        """Releases all resources."""
        print("Releasing PreviewService resources...")
        if self.is_playing:
            self.is_playing = False # Signal thread to stop
        
        if self.preview_thread and self.preview_thread.is_alive():
            print("Joining preview thread...")
            self.preview_thread.join(timeout=0.5) # Wait for the thread to finish
            if self.preview_thread.is_alive():
                print("Warning: Preview thread did not terminate in time.")
        self.preview_thread = None

        if self.preview_cap:
            try:
                self.preview_cap.release()
                print("cv2.VideoCapture released.")
            except Exception as e:
                print(f"Error releasing preview_cap: {e}")
        
        self.preview_cap = None
        self.current_video_path = None
        self.total_duration_sec = 0.0
        self.is_playing = False # Ensure flag is reset
        print("PreviewService resources released.")

# Minimal example for testing (requires a video file named 'test_video.mp4' or similar)
if __name__ == '__main__':
    import os # For path check

    # Dummy callbacks for testing
    def my_ui_update(pil_img):
        print(f"UI Update: Received frame of size {pil_img.size} at {time.time():.2f}")
        # In a real app, you'd display this image in Tkinter, PyQt, etc.
        # For testing, maybe save the first few frames:
        # if not hasattr(my_ui_update, 'counter'): my_ui_update.counter = 0
        # if my_ui_update.counter < 5:
        #     pil_img.save(f"frame_{my_ui_update.counter}.png")
        #     my_ui_update.counter +=1


    def my_time_update(current_t, total_t):
        print(f"Time Update: {current_t:.2f}s / {total_t:.2f}s")

    def my_playback_stopped():
        print("Playback Stopped Callback: Playback has finished or been stopped.")

    # --- Test Setup ---
    # Create a dummy video file if it doesn't exist for basic testing
    test_video_file = "test_preview_video.mp4"
    if not os.path.exists(test_video_file):
        print(f"Creating dummy video: {test_video_file} for testing...")
        try:
            # Create a short black video with MoviePy as cv2.VideoWriter can be complex
            from moviepy.editor import ColorClip
            clip = ColorClip(size=(320, 240), color=(0,0,0), duration=5, fps=10) # 5 seconds, 10 fps
            clip.write_videofile(test_video_file, codec="libx264", audio=False, logger=None)
            clip.close()
            print("Dummy video created successfully.")
        except Exception as e_create:
            print(f"Could not create dummy video: {e_create}. Please provide a '{test_video_file}'.")
            # exit() # Exit if we can't create a test video

    if not os.path.exists(test_video_file):
        print(f"Test video '{test_video_file}' not found. Aborting test.")
    else:
        preview_service = PreviewService(
            ui_update_callback=my_ui_update,
            ui_time_update_callback=my_time_update,
            ui_playback_stopped_callback=my_playback_stopped
        )
        preview_service.set_preview_dimensions(320, 240)

        if preview_service.load_video(test_video_file):
            print(f"Successfully loaded '{test_video_file}'. Duration: {preview_service.get_total_duration():.2f}s")

            print("\nGetting static frame at 1.0s...")
            static_frame = preview_service.get_static_frame(1.0)
            if static_frame:
                print(f"Static frame received: size {static_frame.size}")
                # static_frame.show() # This would open it in default image viewer

            print("\nPlaying video for 2 seconds...")
            preview_service.play(start_time_sec=0.5)
            time.sleep(2)

            print("\nPausing video...")
            preview_service.pause()
            time.sleep(1)
            current_t_paused = preview_service.get_current_playback_time()
            print(f"Paused at: {current_t_paused:.2f}s")


            print("\nResuming video (play again)...")
            preview_service.play(start_time_sec=current_t_paused) # Resume from where it was paused
            time.sleep(2) # Play for another 2 seconds

            print("\nStopping video...")
            preview_service.stop()
            time.sleep(0.5) # Give time for stop actions
            print(f"Current time after stop: {preview_service.get_current_playback_time():.2f}s")

            print("\nGetting static frame at 0s after stop...")
            static_frame_after_stop = preview_service.get_static_frame(0)
            if static_frame_after_stop:
                 print(f"Static frame after stop: size {static_frame_after_stop.size}")


            print("\nReleasing resources...")
            preview_service.release()
            print("PreviewService test finished.")
        else:
            print(f"Failed to load video: {test_video_file}")
    
    # Test loading a non-existent file
    print("\nTesting loading a non-existent file...")
    preview_service_fail = PreviewService()
    if not preview_service_fail.load_video("non_existent_video.mp4"):
        print("Correctly failed to load non-existent video.")
    preview_service_fail.release()

    print("\nAll tests done.")
