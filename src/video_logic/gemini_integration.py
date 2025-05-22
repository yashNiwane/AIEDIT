import os
import google.generativeai as genai
import json
import re

def get_edit_instruction_from_gemini(user_command_text, api_key, status_update_func, error_fg_color_val, warning_fg_color_val): # Added warning_fg_color_val for consistency
    if not api_key:
        status_update_func("Error: GOOGLE_API_KEY not set.", error_fg_color_val)
        return {"action": "error", "message": "API key not configured."}

    genai.configure(api_key=api_key)
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
        status_update_func(error_message, error_fg_color_val)
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
        status_update_func(error_message, error_fg_color_val)
        return {"action": "error", "message": error_message}
    except Exception as e:
        error_message = f"Error processing AI response: {str(e)[:100]}."
        status_update_func(error_message, error_fg_color_val)
        return {"action": "error", "message": error_message}
