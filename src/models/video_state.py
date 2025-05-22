"""
Defines the VideoState model for managing video editing state.

This module contains the VideoState class, which is responsible for tracking
the current video path, original video path, edit history (for undo/redo),
and video duration.
"""

class VideoState:
    """Manages the state of the video being edited, including undo/redo history."""

    def __init__(self):
        """
        Initializes the video state.
        """
        self.current_video_path: str | None = None
        self.original_video_path: str | None = None
        self.edit_count: int = 0
        self.undo_paths: list[str] = []
        self.redo_paths: list[str] = []
        self.video_total_duration_sec: float = 0.0

    def set_original_video(self, path: str):
        """
        Sets the original video path and resets the editing state.
        """
        self.original_video_path = path
        self.current_video_path = path
        self.edit_count = 0
        self.undo_paths = [path]
        self.redo_paths = []
        self.video_total_duration_sec = 0.0 # Reset duration, to be recalculated

    def add_edit(self, new_video_path: str):
        """
        Adds a new edited video path to the state.
        """
        self.edit_count += 1
        self.current_video_path = new_video_path
        self.undo_paths.append(new_video_path)
        self.redo_paths = []  # Any new edit clears the redo stack
        self.video_total_duration_sec = 0.0 # Reset duration, to be recalculated

    def can_undo(self) -> bool:
        """
        Checks if an undo operation can be performed.
        """
        return len(self.undo_paths) > 1

    def undo(self) -> str | None:
        """
        Performs an undo operation.
        Moves the current state to the redo stack and reverts to the previous state.
        Returns the path of the video after undo, or None if cannot undo.
        """
        if self.can_undo():
            undone_path = self.undo_paths.pop()
            self.redo_paths.insert(0, undone_path)
            self.current_video_path = self.undo_paths[-1]
            self.video_total_duration_sec = 0.0 # Reset duration, to be recalculated
            return self.current_video_path
        return None

    def can_redo(self) -> bool:
        """
        Checks if a redo operation can be performed.
        """
        return len(self.redo_paths) > 0

    def redo(self) -> str | None:
        """
        Performs a redo operation.
        Moves a state from the redo stack back to the undo stack.
        Returns the path of the video after redo, or None if cannot redo.
        """
        if self.can_redo():
            redone_path = self.redo_paths.pop(0)
            self.undo_paths.append(redone_path)
            self.current_video_path = redone_path
            self.video_total_duration_sec = 0.0 # Reset duration, to be recalculated
            return self.current_video_path
        return None

    def get_current_path(self) -> str | None:
        """
        Returns the path of the current video.
        """
        return self.current_video_path

    def get_original_path(self) -> str | None:
        """
        Returns the path of the original video.
        """
        return self.original_video_path

    def set_duration(self, duration_sec: float):
        """
        Sets the total duration of the current video.
        """
        self.video_total_duration_sec = duration_sec

    def get_duration(self) -> float:
        """
        Returns the total duration of the current video.
        """
        return self.video_total_duration_sec
