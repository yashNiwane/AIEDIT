from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip, AudioFileClip

def cut_video(input_path, start_time, end_time):
    clip = VideoFileClip(input_path).subclip(start_time, end_time)
    return clip

def add_text(clip, text, start_time):
    txt_clip = (TextClip(text, fontsize=70, color='white')
                .set_position('center')
                .set_duration(clip.duration)
                .set_start(start_time))
    return CompositeVideoClip([clip, txt_clip])

def add_background_music(clip, music_path):
    audio = AudioFileClip(music_path)
    final_audio = audio.set_duration(clip.duration)
    clip = clip.set_audio(final_audio)
    return clip

def export_video(clip, output_path, resolution="720p"):
    if resolution == "720p":
        clip.write_videofile(output_path, fps=24, codec='libx264', preset="ultrafast")
    elif resolution == "1080p":
        clip.resize(height=1080).write_videofile(output_path, fps=24, codec='libx264', preset="ultrafast")
