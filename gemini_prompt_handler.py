import google.generativeai as genai

genai.configure(api_key="AIzaSyDh3EPsNyndUdUqKMq0gencXLdwpL1j0lk")

def parse_prompt(prompt_text):
    model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest")

    prompt = f"""
    Analyze this video editing instruction: "{prompt_text}"

    Return a JSON with fields:
    - cut_start (in seconds)
    - cut_end (in seconds)
    - text (string to add) [optional]
    - text_time (time at which text appears) [optional]
    - background_music (file name, assume uploaded) [optional]
    - export_quality (720p or 1080p)

    Reply only with clean JSON.
    """

    response = model.generate_content(prompt)
    json_data = response.text
    return json_data
