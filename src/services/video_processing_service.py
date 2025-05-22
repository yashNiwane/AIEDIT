"""
Video Processing Service module for applying edits using MoviePy.

This module provides the VideoProcessingService class, which encapsulates
all MoviePy-based video editing operations such as trimming, speed changes,
adding text, applying filters, and more. Each method takes an input video
path, an output path, and operation-specific parameters.
"""
import os
from moviepy.editor import (
    VideoFileClip, vfx, TextClip, CompositeVideoClip,
    ImageClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips
)
from moviepy.audio.fx.all import audio_normalize

class VideoProcessingService:
    """Encapsulates all MoviePy-based video editing operations."""

    def __init__(self):
        """Initializes the video processing service."""
        # self.edits_dir = "_video_editor_edits" # Example, if service manages this
        # os.makedirs(self.edits_dir, exist_ok=True)
        pass

    def _parse_position(self, pos_param, main_clip_w: int, main_clip_h: int) -> tuple | str:
        """
        Converts string/tuple position parameters into pixel coordinates or MoviePy position strings.
        """
        simple_pos_keywords = ["center", "left", "right", "top", "bottom",
                               "top_left", "top_right", "bottom_left", "bottom_right"]
        if isinstance(pos_param, str) and pos_param in simple_pos_keywords:
            return pos_param

        if isinstance(pos_param, str) and pos_param.startswith("(") and pos_param.endswith(")"):
            try:
                pos_param = eval(pos_param) # Evaluate string representation of tuple
            except:
                # Log warning or raise error, for now, fallback to center
                print(f"Warning: Could not parse position string '{pos_param}'. Using 'center'.")
                return "center"

        if isinstance(pos_param, (tuple, list)) and len(pos_param) == 2:
            x_val, y_val = pos_param
            px_x, px_y = None, None

            # Parse X
            if isinstance(x_val, str):
                if x_val in ["left", "center", "right"]: px_x = x_val
                elif '%' in x_val: px_x = float(x_val.strip('%')) / 100.0 * main_clip_w
                else:
                    try: px_x = float(x_val)
                    except ValueError: pass
            elif isinstance(x_val, (int, float)): px_x = x_val

            # Parse Y
            if isinstance(y_val, str):
                if y_val in ["top", "center", "bottom"]: px_y = y_val
                elif '%' in y_val: px_y = float(y_val.strip('%')) / 100.0 * main_clip_h
                else:
                    try: px_y = float(y_val)
                    except ValueError: pass
            elif isinstance(y_val, (int, float)): px_y = y_val

            if px_x is not None and px_y is not None:
                return (px_x, px_y)

        print(f"Warning: Invalid position format '{pos_param}'. Using 'center'.")
        return "center"

    def get_video_duration(self, video_path: str) -> float:
        """Gets the duration of a video file."""
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")
        clip = None
        try:
            clip = VideoFileClip(video_path)
            duration = clip.duration
            return duration
        except Exception as e:
            raise RuntimeError(f"Error getting duration for {video_path}: {e}")
        finally:
            if clip:
                clip.close()

    def _write_output(self, clip, output_path: str):
        """Helper to write video file with common parameters."""
        clip.write_videofile(output_path, codec="libx264", audio_codec="aac",
                             preset="medium", threads=os.cpu_count() or 2, logger=None) # logger='bar' or None

    def apply_trim(self, input_path: str, output_path: str, start_time: float, end_time: float = None) -> str:
        main_clip = None
        try:
            main_clip = VideoFileClip(input_path)
            if start_time < 0: start_time = 0
            if start_time >= main_clip.duration:
                raise ValueError("Start time is beyond video duration.")
            if end_time is not None and start_time >= end_time:
                raise ValueError("Trim start_time must be less than end_time.")
            if end_time is not None and end_time > main_clip.duration:
                end_time = main_clip.duration

            edited_clip = main_clip.subclip(start_time, end_time)
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error applying trim: {e}")
        finally:
            if main_clip: main_clip.close()

    def change_speed(self, input_path: str, output_path: str, factor: float) -> str:
        main_clip = None
        try:
            if factor <= 0:
                raise ValueError("Speed factor must be greater than 0.")
            main_clip = VideoFileClip(input_path)
            edited_clip = main_clip.fx(vfx.speedx, factor)
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error changing speed: {e}")
        finally:
            if main_clip: main_clip.close()

    def add_text(self, input_path: str, output_path: str, text_content: str,
                   font_size: int, color: str, position_param, font: str,
                   stroke_color: str, stroke_width: float,
                   start_time: float, duration: float = None) -> str:
        main_clip = None
        txt_clip = None
        try:
            main_clip = VideoFileClip(input_path)
            
            if start_time < 0: start_time = 0
            if start_time >= main_clip.duration:
                raise ValueError("Text start_time is beyond video duration.")

            if duration is None or duration <= 0:
                duration = max(0.1, main_clip.duration - start_time)
            elif start_time + duration > main_clip.duration:
                duration = main_clip.duration - start_time

            position = self._parse_position(position_param, main_clip.w, main_clip.h)

            txt_clip = TextClip(text_content, fontsize=font_size, color=color, font=font,
                                stroke_color=stroke_color, stroke_width=stroke_width)
            txt_clip = txt_clip.set_duration(duration).set_start(start_time).set_position(position)
            
            edited_clip = CompositeVideoClip([main_clip, txt_clip])
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error adding text: {e}")
        finally:
            if main_clip: main_clip.close()
            if txt_clip: txt_clip.close() # TextClip might not need explicit close, but good practice

    def mute_audio(self, input_path: str, output_path: str) -> str:
        main_clip = None
        try:
            main_clip = VideoFileClip(input_path)
            if not main_clip.audio:
                # If no audio, just copy the video to output path or handle as no-op
                # For now, let's assume we should still produce an output file.
                # A more sophisticated approach might return input_path or raise a specific notice.
                print(f"Warning: Video {input_path} has no audio to mute. Copying video.")
                edited_clip = main_clip.copy()
            else:
                edited_clip = main_clip.without_audio()
            
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error muting audio: {e}")
        finally:
            if main_clip: main_clip.close()

    def extract_audio(self, input_path: str, audio_output_path: str) -> str:
        main_clip = None
        try:
            main_clip = VideoFileClip(input_path)
            if not main_clip.audio:
                raise ValueError("Video has no audio to extract.")
            main_clip.audio.write_audiofile(audio_output_path)
            return audio_output_path
        except Exception as e:
            raise RuntimeError(f"Error extracting audio: {e}")
        finally:
            if main_clip: main_clip.close()

    def apply_black_and_white(self, input_path: str, output_path: str) -> str:
        main_clip = None
        try:
            main_clip = VideoFileClip(input_path)
            edited_clip = main_clip.fx(vfx.blackwhite)
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error applying black and white filter: {e}")
        finally:
            if main_clip: main_clip.close()

    def invert_colors(self, input_path: str, output_path: str) -> str:
        main_clip = None
        try:
            main_clip = VideoFileClip(input_path)
            edited_clip = main_clip.fx(vfx.invert_colors)
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error inverting colors: {e}")
        finally:
            if main_clip: main_clip.close()

    def gamma_correct(self, input_path: str, output_path: str, gamma_value: float) -> str:
        main_clip = None
        try:
            main_clip = VideoFileClip(input_path)
            edited_clip = main_clip.fx(vfx.gamma_corr, gamma_value)
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error applying gamma correction: {e}")
        finally:
            if main_clip: main_clip.close()

    def adjust_volume(self, input_path: str, output_path: str, factor: float) -> str:
        main_clip = None
        try:
            main_clip = VideoFileClip(input_path)
            if not main_clip.audio:
                print(f"Warning: Video {input_path} has no audio to adjust. Copying video.")
                edited_clip = main_clip.copy()
            else:
                edited_clip = main_clip.volumex(factor)
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error adjusting volume: {e}")
        finally:
            if main_clip: main_clip.close()

    def rotate_video(self, input_path: str, output_path: str, angle: float) -> str:
        main_clip = None
        try:
            main_clip = VideoFileClip(input_path)
            # expand=True is important to prevent cropping on non-90/180/270 degree rotations
            edited_clip = main_clip.rotate(angle, expand=True)
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error rotating video: {e}")
        finally:
            if main_clip: main_clip.close()

    def apply_fade_in(self, input_path: str, output_path: str, fade_duration: float) -> str:
        main_clip = None
        try:
            if fade_duration <= 0: raise ValueError("Fade duration must be positive.")
            main_clip = VideoFileClip(input_path)
            edited_clip = main_clip.fadein(fade_duration)
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error applying fade in: {e}")
        finally:
            if main_clip: main_clip.close()

    def apply_fade_out(self, input_path: str, output_path: str, fade_duration: float) -> str:
        main_clip = None
        try:
            if fade_duration <= 0: raise ValueError("Fade duration must be positive.")
            main_clip = VideoFileClip(input_path)
            edited_clip = main_clip.fadeout(fade_duration)
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error applying fade out: {e}")
        finally:
            if main_clip: main_clip.close()

    def mirror_video(self, input_path: str, output_path: str, direction: str) -> str:
        main_clip = None
        try:
            main_clip = VideoFileClip(input_path)
            if direction == "horizontal":
                edited_clip = main_clip.fx(vfx.mirror_x)
            elif direction == "vertical":
                edited_clip = main_clip.fx(vfx.mirror_y)
            else:
                raise ValueError("Mirror direction must be 'horizontal' or 'vertical'.")
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error mirroring video: {e}")
        finally:
            if main_clip: main_clip.close()

    def normalize_audio(self, input_path: str, output_path: str) -> str:
        main_clip = None
        normalized_audio = None # Keep track for potential close
        try:
            main_clip = VideoFileClip(input_path)
            if not main_clip.audio:
                print(f"Warning: Video {input_path} has no audio to normalize. Copying video.")
                edited_clip = main_clip.copy()
            else:
                normalized_audio = main_clip.audio.fx(audio_normalize)
                edited_clip = main_clip.set_audio(normalized_audio)
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error normalizing audio: {e}")
        finally:
            if main_clip: main_clip.close()
            # Audio clips created from fx might also need closing if they hold resources
            if normalized_audio and hasattr(normalized_audio, 'close'):
                 normalized_audio.close()


    def add_background_music(self, input_path: str, output_path: str, music_path: str,
                               volume_factor: float, music_start_time_in_video: float,
                               loop_music: bool) -> str:
        main_clip = None
        music_clip = None
        looped_music_clip = None
        final_audio_composite = None
        try:
            main_clip = VideoFileClip(input_path)
            music_clip = AudioFileClip(music_path)

            music_to_composite = music_clip.volumex(volume_factor)

            video_duration_for_music = main_clip.duration - music_start_time_in_video
            if video_duration_for_music <= 0:
                raise ValueError("Music start time is at or after the main video's end.")

            if loop_music and music_to_composite.duration < video_duration_for_music:
                num_loops = int(video_duration_for_music / music_to_composite.duration) + 1
                looped_music_clip = concatenate_audioclips([music_to_composite] * num_loops)
                music_to_composite = looped_music_clip

            # Ensure music does not exceed the (remaining) video duration
            music_to_composite = music_to_composite.set_duration(
                min(music_to_composite.duration, video_duration_for_music)
            )
            
            music_to_composite = music_to_composite.set_start(music_start_time_in_video)

            if main_clip.audio:
                final_audio_composite = CompositeAudioClip([main_clip.audio, music_to_composite])
            else:
                final_audio_composite = CompositeAudioClip([music_to_composite]) # No, this is wrong, should be just music_to_composite
                # If main_clip.audio is None, final_audio is just the new music.
                # CompositeAudioClip expects a list of clips. If only one, it's that clip.
                # However, it's safer to handle the None case explicitly for set_audio.
                final_audio_composite = music_to_composite # Corrected

            edited_clip = main_clip.set_audio(final_audio_composite)
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error adding background music: {e}")
        finally:
            if main_clip: main_clip.close()
            if music_clip: music_clip.close()
            if looped_music_clip: looped_music_clip.close()
            if final_audio_composite and hasattr(final_audio_composite, 'close'):
                final_audio_composite.close()


    def add_image_overlay(self, input_path: str, output_path: str, image_path: str,
                            position_param, size_factor_param, opacity: float,
                            start_time: float, duration: float = None) -> str:
        main_clip = None
        img_clip = None
        try:
            main_clip = VideoFileClip(input_path)
            img_clip = ImageClip(image_path)

            # Size adjustment
            if isinstance(size_factor_param, (int, float)):
                img_clip = img_clip.resize(height=int(main_clip.h * size_factor_param))
            elif isinstance(size_factor_param, (tuple, list)) and len(size_factor_param) == 2:
                w, h = size_factor_param
                img_clip = img_clip.resize(width=int(w), height=int(h) if h is not None else None) # Allow None for aspect preservation by moviepy
            else: # Default sizing
                img_clip = img_clip.resize(height=int(main_clip.h * 0.1)) # Default: 10% of video height

            if start_time < 0: start_time = 0
            if start_time >= main_clip.duration:
                raise ValueError("Image overlay start_time is beyond video duration.")

            if duration is None or duration <= 0:
                duration = max(0.1, main_clip.duration - start_time)
            elif start_time + duration > main_clip.duration:
                duration = main_clip.duration - start_time
            
            img_clip = img_clip.set_duration(duration).set_start(start_time).set_opacity(opacity)
            position = self._parse_position(position_param, main_clip.w, main_clip.h)
            img_clip = img_clip.set_position(position)

            edited_clip = CompositeVideoClip([main_clip, img_clip])
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error adding image overlay: {e}")
        finally:
            if main_clip: main_clip.close()
            if img_clip: img_clip.close()


    def apply_picture_in_picture(self, input_path: str, output_path: str,
                                   overlay_video_path: str, position_param,
                                   size_factor_param, start_time: float,
                                   duration: float = None) -> str:
        main_clip = None
        pip_clip = None
        try:
            main_clip = VideoFileClip(input_path)
            pip_clip = VideoFileClip(overlay_video_path)

            # Size adjustment
            if isinstance(size_factor_param, (int, float)):
                pip_clip = pip_clip.resize(width=int(main_clip.w * size_factor_param))
            elif isinstance(size_factor_param, (tuple, list)) and len(size_factor_param) == 2:
                w, h = size_factor_param
                pip_clip = pip_clip.resize(width=int(w), height=int(h) if h is not None else None)
            else: # Default sizing
                pip_clip = pip_clip.resize(width=int(main_clip.w * 0.25)) # Default: 25% of main video width

            if start_time < 0: start_time = 0
            if start_time >= main_clip.duration:
                raise ValueError("PiP start_time is beyond main video duration.")

            # Duration logic: min of PiP's own duration, main video's remaining duration, or specified duration
            max_possible_duration = main_clip.duration - start_time
            if duration is None or duration <= 0:
                duration = min(pip_clip.duration, max_possible_duration)
            else:
                duration = min(float(duration), pip_clip.duration, max_possible_duration)
            
            if duration <=0: # If calculated duration is zero or negative (e.g. start time too late)
                 raise ValueError("PiP duration results in zero or negative length. Check start time and PiP video length.")


            pip_clip = pip_clip.set_duration(duration).set_start(start_time)
            position = self._parse_position(position_param, main_clip.w, main_clip.h)
            pip_clip = pip_clip.set_position(position)

            edited_clip = CompositeVideoClip([main_clip, pip_clip])
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error applying Picture-in-Picture: {e}")
        finally:
            if main_clip: main_clip.close()
            if pip_clip: pip_clip.close()

    def blur_video(self, input_path: str, output_path: str, blur_radius: int) -> str:
        main_clip = None
        try:
            if blur_radius < 0: raise ValueError("Blur radius cannot be negative.")
            main_clip = VideoFileClip(input_path)
            # MoviePy's vfx.blur takes (clip, radius). Radius is often a float for Gaussian blur sigma.
            # If the old app used an int, it might have been a box blur or specific interpretation.
            # For vfx.blur, radius is more like strength. Let's assume it's an int for now.
            edited_clip = main_clip.fx(vfx.blur, radius=blur_radius)
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error blurring video: {e}")
        finally:
            if main_clip: main_clip.close()

    def concatenate_videos(self, base_video_path: str, videos_to_append_paths: list[str], output_path: str) -> str:
        clips_to_concat = []
        try:
            if not base_video_path: raise ValueError("Base video path is required for concatenation.")
            if not videos_to_append_paths: raise ValueError("List of videos to append cannot be empty.")

            base_clip = VideoFileClip(base_video_path)
            clips_to_concat.append(base_clip)

            for video_path in videos_to_append_paths:
                if not os.path.exists(video_path):
                    raise FileNotFoundError(f"Video to append not found: {video_path}")
                clip_to_append = VideoFileClip(video_path)
                clips_to_concat.append(clip_to_append)
            
            # method="compose" is usually safer for clips with different sizes/audio
            edited_clip = concatenate_videoclips(clips_to_concat, method="compose")
            self._write_output(edited_clip, output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Error concatenating videos: {e}")
        finally:
            for clip in clips_to_concat:
                if clip: clip.close()

# Example Usage (Illustrative - requires video files to exist)
if __name__ == '__main__':
    service = VideoProcessingService()
    
    # Create dummy files for testing if they don't exist
    dummy_video = "dummy_video.mp4"
    dummy_audio = "dummy_audio.mp3"
    dummy_image = "dummy_image.png"
    dummy_pip_video = "dummy_pip_video.mp4"
    edits_folder = "_video_processing_service_tests"
    os.makedirs(edits_folder, exist_ok=True)

    # Very basic way to create a short dummy video with MoviePy if not present
    if not os.path.exists(dummy_video):
        try:
            from moviepy.editor import ColorClip
            clip = ColorClip(size=(100,100), color=(0,0,0), duration=5, fps=10)
            # Add a dummy audio to prevent issues with audio-dependent functions
            if not os.path.exists(dummy_audio): # Create dummy audio for the dummy video
                from moviepy.editor import AudioArrayClip
                import numpy as np
                dummy_audio_array = np.random.uniform(-1, 1, size=(44100 * 5, 2)) # 5s stereo
                audio = AudioArrayClip(dummy_audio_array, fps=44100)
                audio.write_audiofile(os.path.join(edits_folder, "silence.mp3")) # temp audio for dummy
                audio.close()
                clip = clip.set_audio(AudioFileClip(os.path.join(edits_folder, "silence.mp3")))

            clip.write_videofile(dummy_video, codec="libx264", audio_codec="aac", fps=10)
            clip.close()
            print(f"Created dummy video: {dummy_video}")
        except Exception as e_create:
            print(f"Could not create dummy video {dummy_video}: {e_create}. Some tests might fail.")

    if not os.path.exists(dummy_pip_video) and os.path.exists(dummy_video):
         shutil.copy(dummy_video, dummy_pip_video) # Just copy for PiP test
         print(f"Copied {dummy_video} to {dummy_pip_video} for PiP testing.")

    if not os.path.exists(dummy_image):
        try:
            from PIL import Image, ImageDraw
            img = Image.new('RGB', (50, 50), color = 'red')
            draw = ImageDraw.Draw(img)
            draw.text((10,10), "Test", fill=(255,255,0))
            img.save(dummy_image)
            print(f"Created dummy image: {dummy_image}")
        except Exception as e_create_img:
            print(f"Could not create dummy image {dummy_image}: {e_create_img}")


    if os.path.exists(dummy_video):
        try:
            print(f"Duration of {dummy_video}: {service.get_video_duration(dummy_video)}")
            
            out_trim = os.path.join(edits_folder, "trimmed.mp4")
            service.apply_trim(dummy_video, out_trim, 1, 3)
            print(f"Trimmed video saved to {out_trim}")

            out_speed = os.path.join(edits_folder, "speed_changed.mp4")
            service.change_speed(dummy_video, out_speed, 2.0)
            print(f"Speed changed video saved to {out_speed}")

            out_text = os.path.join(edits_folder, "text_added.mp4")
            service.add_text(dummy_video, out_text, "Hello MoviePy!", 24, "white", "center", "Arial", "black", 1, 1, 2)
            print(f"Text added video saved to {out_text}")
            
            out_audio_extract = os.path.join(edits_folder, "extracted_audio.mp3")
            if service.get_video_duration(dummy_video) > 0 : # Ensure video has some length
                # Check if dummy video has audio, VideoFileClip will raise error if no audio for extraction
                temp_vfc_check = VideoFileClip(dummy_video)
                if temp_vfc_check.audio:
                    service.extract_audio(dummy_video, out_audio_extract)
                    print(f"Extracted audio saved to {out_audio_extract}")
                else: print(f"Skipping audio extraction test as {dummy_video} has no audio.")
                temp_vfc_check.close()


            if os.path.exists(dummy_image):
                out_img_overlay = os.path.join(edits_folder, "image_overlayed.mp4")
                service.add_image_overlay(dummy_video, out_img_overlay, dummy_image, "bottom_right", 0.2, 0.7, 0.5, 2)
                print(f"Image overlay video saved to {out_img_overlay}")

            if os.path.exists(dummy_pip_video):
                out_pip = os.path.join(edits_folder, "pip_applied.mp4")
                service.apply_picture_in_picture(dummy_video, out_pip, dummy_pip_video, "top_left", 0.3, 1, 3)
                print(f"PiP video saved to {out_pip}")
            
            out_concat = os.path.join(edits_folder, "concatenated.mp4")
            if os.path.exists(out_trim): # Use a previously created clip
                service.concatenate_videos(dummy_video, [out_trim], out_concat)
                print(f"Concatenated video saved to {out_concat}")


        except FileNotFoundError as e:
            print(f"Test failed: A required dummy file was not found: {e}")
        except RuntimeError as e:
            print(f"A video processing test failed: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during tests: {e}")
    else:
        print(f"Skipping VideoProcessingService tests as {dummy_video} does not exist.")
