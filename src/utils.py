"""
Utility functions for the video editor application.

This module provides helper functions that are used across different
parts of the application, such as time formatting.
"""

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
