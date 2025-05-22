# Prompt-Based Video Editor

This Python application provides a simple GUI for basic and some advanced video editing operations, driven by natural language prompts interpreted by Google's Gemini AI. It leverages MoviePy for video processing, Tkinter for the GUI, OpenCV for video preview playback, and Pillow for image manipulation (including a custom text rendering solution).

## Features

*   **AI-Powered Editing:** Enter commands in natural language (e.g., "cut the first 5 seconds", "add 'Hello World' text at center", "make video black and white").
*   **GUI Interface:**
    *   Load video files (MP4, AVI, MOV, MKV).
    *   Preview window with playback controls (Play, Pause, Stop) and a timeline scrubber.
    *   Status bar for messages and errors.
    *   Undo/Redo functionality for edits.
    *   Export the final edited video.
*   **Supported Editing Operations:**
    *   **Basic:**
        *   Trim/Cut
        *   Change Speed
        *   Mute Audio
        *   Extract Audio
    *   **Text Overlay (Pillow-based):**
        *   Custom text content, font (path or name), size, color.
        *   Stroke color and width.
        *   Positioning (keywords, pixel coordinates, percentages).
        *   Start time and duration.
    *   **Filters & Adjustments:**
        *   Black and White
        *   Invert Colors
        *   Gamma Correction
        *   Adjust Volume
        *   Rotate Video
        *   Fade In / Fade Out
        *   Mirror/Flip (Horizontal/Vertical)
        *   Normalize Audio
        *   Blur Video
    *   **Compositing & Advanced:**
        *   Add Background Music (with volume, start time, loop)
        *   Add Image Overlay/Watermark (with position, size, opacity, timing)
        *   Picture-in-Picture (PiP)
        *   Concatenate Videos

## Setup

### Prerequisites

*   Python 3.7+
*   Google Gemini API Key

### Installation

1.  **Clone the repository (or download the script):**
    ```bash
    # If you have it in a git repo
    # git clone <repository_url>
    # cd <repository_directory>
    ```

2.  **Set up a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # On Windows
    venv\Scripts\activate
    # On macOS/Linux
    source venv/bin/activate
    ```

3.  **Install required Python packages:**
    ```bash
    pip install moviepy google-generativeai opencv-python Pillow numpy
    ```
    *   `moviepy`: For core video editing.
    *   `google-generativeai`: For interacting with the Gemini API.
    *   `opencv-python`: For video preview playback and frame manipulation.
    *   `Pillow`: For image manipulation (preview frames, custom text rendering).
    *   `numpy`: Numerical operations, often a dependency for MoviePy and image processing.

4.  **Set up Google Gemini API Key:**
    *   Obtain an API key from [Google AI Studio](https://aistudio.google.com/app/apikey).
    *   Set it as an environment variable named `GOOGLE_API_KEY`.
        *   **Windows (Command Prompt - current session):**
            ```bash
            set GOOGLE_API_KEY=YOUR_API_KEY_HERE
            ```
        *   **Windows (PowerShell - current session):**
            ```bash
            $env:GOOGLE_API_KEY="YOUR_API_KEY_HERE"
            ```
        *   **macOS/Linux (Terminal - current session):**
            ```bash
            export GOOGLE_API_KEY=YOUR_API_KEY_HERE
            ```
        *   For persistent storage, add this to your system's environment variables or your shell's profile file (e.g., `.bashrc`, `.zshrc`, `.profile`).

5.  **Fonts (for Text Overlay):**
    *   The Pillow-based text overlay feature works best if you provide a path to a `.ttf` or `.otf` font file (e.g., `"C:/Windows/Fonts/arial.ttf"` or `"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"`).
    *   Common font names like `"arial.ttf"` or `"Arial"` might work if your system's Pillow installation can find them. Otherwise, it will fall back to a default Pillow font which may not look as intended.

## Running the Application

Execute the Python script:
```bash
python video_editor_app.py
