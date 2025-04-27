import streamlit as st
import json
import tempfile
from video_editor import cut_video, add_text, add_background_music, export_video
from gemini_prompt_handler import parse_prompt

st.title("🎬 AI Video Editor (Prompt Based) - Powered by Gemini 2.0 Flash Lite")

uploaded_video = st.file_uploader("Upload a Video", type=["mp4"])
uploaded_music = st.file_uploader("Upload Background Music (optional)", type=["mp3"])
prompt = st.text_area("Write your editing prompt here:")

if st.button("Edit Video") and uploaded_video is not None and prompt:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_input:
        temp_input.write(uploaded_video.read())
        input_video_path = temp_input.name

    # 1️⃣ Get AI Response
    response_text = parse_prompt(prompt)
    print("Gemini API Raw Response:", response_text)

    # 2️⃣ Clean the response
    clean_text = response_text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[6:].strip()
    if clean_text.startswith("```"):
        clean_text = clean_text[3:].strip()
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3].strip()

    # 3️⃣ Parse clean JSON
    try:
        parsed_data = json.loads(clean_text)
    except json.JSONDecodeError as e:
        st.error(f"Failed to parse response. Error: {e}")
        st.stop()

    print("Parsed Data:", parsed_data)

    # 4️⃣ Start Editing
    clip = cut_video(input_video_path, parsed_data["cut_start"], parsed_data["cut_end"])

    if parsed_data.get("text"):
        clip = add_text(clip, parsed_data["text"], parsed_data["text_time"])

    if uploaded_music and parsed_data.get("background_music"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_audio:
            temp_audio.write(uploaded_music.read())
            music_path = temp_audio.name
            clip = add_background_music(clip, music_path)

    # 5️⃣ Export final video
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_output:
        export_video(clip, temp_output.name, parsed_data.get("export_quality", "720p"))
        
        st.success("🎉 Video edited successfully!")
        st.video(temp_output.name)
        st.download_button("Download Edited Video", temp_output.name, file_name="edited_video.mp4")
