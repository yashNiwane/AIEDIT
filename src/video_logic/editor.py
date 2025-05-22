import os
import shutil
# from tkinter import filedialog # No longer needed directly here
from moviepy.editor import (
    VideoFileClip, vfx, TextClip, CompositeVideoClip,
    ImageClip, AudioFileClip, CompositeAudioClip, concatenate_videoclips,
    concatenate_audioclips # Added concatenate_audioclips
)
from moviepy.audio.fx.all import audio_normalize


class VideoEditorLogic:
    def process_edit(self, edit_params, current_video_path_param, original_video_path_param, edit_count_param, 
                     _ask_for_file_func, parse_position_func, status_update_func, ui_colors, asksaveasfilename_func):
        
        current_edit_count = edit_count_param # Use a local copy to modify

        if not current_video_path_param:
            status_update_func("Error: Please load a video first.", ui_colors['ERROR_FG_COLOR'])
            return {'new_video_path': None, 'updated_edit_count': current_edit_count, 'status_text': "Error: Please load a video first.", 'status_fg': ui_colors['ERROR_FG_COLOR']}
        
        if not edit_params or edit_params.get("action") == "error":
            message = edit_params.get('message', 'Invalid parameters.')
            if not status_update_func.__name__ == '<lambda>' or not "Error:" in message : # Avoid double "Error:" if already set by Gemini
                 status_update_func(f"Error: Cannot apply edit. {message}", ui_colors['ERROR_FG_COLOR'])
            return {'new_video_path': None, 'updated_edit_count': current_edit_count, 'status_text': f"Error: Cannot apply edit. {message}", 'status_fg': ui_colors['ERROR_FG_COLOR']}

        current_clip = None
        edited_clip = None
        new_filename_for_edit = None
        temp_clips_to_close = [] # To store clips that need explicit closing

        try:
            status_update_func(f"Loading '{os.path.basename(current_video_path_param)}' for editing...", ui_colors['FG_COLOR_LIGHT'])
            current_clip = VideoFileClip(current_video_path_param)
            temp_clips_to_close.append(current_clip)
        except Exception as e:
            error_msg = f"Error: Could not load video for edit. (Details: {str(e)})"
            status_update_func(error_msg, ui_colors['ERROR_FG_COLOR'])
            return {'new_video_path': None, 'updated_edit_count': current_edit_count, 'status_text': f"Error: Could not load video for edit. (Details: {str(e)})", 'status_fg': ui_colors['ERROR_FG_COLOR']}

        action = edit_params.get("action")
        status_update_func(f"Applying '{action}'...", ui_colors['FG_COLOR_LIGHT'])

        try:
            if action == "add_text":
                text_content = edit_params.get("text_content")
                if not text_content: raise ValueError("Text content is required.")
                start_time = float(edit_params.get("start_time", 0))
                duration_param = edit_params.get("duration")
                font_size = int(edit_params.get("font_size", 36))
                color = edit_params.get("color", "white")
                position_param = edit_params.get("position", "center")
                font = edit_params.get("font", "Arial")
                stroke_color = edit_params.get("stroke_color", "black")
                stroke_width = float(edit_params.get("stroke_width", 1.5))

                if start_time < 0: start_time = 0
                if start_time >= current_clip.duration: raise ValueError("Text start_time is beyond video duration.")
                duration = None
                if duration_param:
                    try: duration = float(duration_param)
                    except ValueError: pass
                if duration is None or duration <= 0: duration = max(0.1, current_clip.duration - start_time)
                if start_time + duration > current_clip.duration: duration = current_clip.duration - start_time
                
                position = parse_position_func(position_param, current_clip.w, current_clip.h)

                txt_clip_obj = TextClip(text_content, fontsize=font_size, color=color, font=font,
                                        stroke_color=stroke_color, stroke_width=stroke_width)
                txt_clip_obj = txt_clip_obj.set_duration(duration).set_start(start_time).set_position(position)
                temp_clips_to_close.append(txt_clip_obj)
                edited_clip = CompositeVideoClip([current_clip, txt_clip_obj])
            
            elif action == "trim":
                start_time = float(edit_params.get("start_time", 0))
                end_time_param = edit_params.get("end_time")
                end_time = None
                if end_time_param is not None: end_time = float(end_time_param)
                if end_time is not None and start_time >= end_time: raise ValueError("Trim start < end.")
                if start_time >= current_clip.duration: raise ValueError("Trim start > duration.")
                edited_clip = current_clip.subclip(start_time, end_time)
            elif action == "speed":
                factor = float(edit_params.get("factor", 1.0)) # Added default for safety
                if factor <= 0: raise ValueError("Speed factor > 0.")
                edited_clip = current_clip.fx(vfx.speedx, factor)
            elif action == "mute_audio":
                if current_clip.audio: edited_clip = current_clip.without_audio()
                else: 
                    status_update_func("No audio to mute.", ui_colors['WARNING_FG_COLOR'])
                    edited_clip = current_clip.copy() # Return a copy to signify an operation happened
            elif action == "extract_audio":
                audio_fn_suggest = edit_params.get("output_filename") or f"{os.path.splitext(os.path.basename(original_video_path_param))[0]}_audio.mp3"
                audio_save_path = asksaveasfilename_func(title="Save Extracted Audio", initialfile=audio_fn_suggest, defaultextension=".mp3")
                if not audio_save_path: 
                    status_update_func("Audio extraction cancelled.", ui_colors['WARNING_FG_COLOR'])
                    # Return current state as no change happened and no new file was made
                    return {'new_video_path': current_video_path_param, 'updated_edit_count': current_edit_count, 'status_text': "Audio extraction cancelled.", 'status_fg': ui_colors['WARNING_FG_COLOR'], 'action_specific_result': False}

                if current_clip.audio:
                    current_clip.audio.write_audiofile(audio_save_path)
                    status_update_func(f"Audio extracted: {os.path.basename(audio_save_path)}.", ui_colors['SUCCESS_FG_COLOR'])
                else: 
                    status_update_func("No audio to extract.", ui_colors['WARNING_FG_COLOR'])
                # For extract_audio, we don't change the video, so return the original path
                # and indicate success of the operation if a path was chosen.
                return {'new_video_path': current_video_path_param, 'updated_edit_count': current_edit_count, 'status_text': f"Audio extraction processed.", 'status_fg': ui_colors['SUCCESS_FG_COLOR'], 'action_specific_result': True}

            elif action == "black_and_white": edited_clip = current_clip.fx(vfx.blackwhite)
            elif action == "invert_colors": edited_clip = current_clip.fx(vfx.invert_colors)
            elif action == "gamma_correct":
                gamma = float(edit_params.get("gamma_value", 1.0))
                edited_clip = current_clip.fx(vfx.gamma_corr, gamma)
            elif action == "adjust_volume":
                factor = float(edit_params.get("factor", 1.0))
                if current_clip.audio: edited_clip = current_clip.volumex(factor)
                else: 
                    status_update_func("No audio to adjust.", ui_colors['WARNING_FG_COLOR'])
                    edited_clip = current_clip.copy()
            elif action == "rotate":
                angle = float(edit_params.get("angle", 0))
                edited_clip = current_clip.rotate(angle, expand=True) # expand=True is important
            elif action == "fade_in":
                dur = float(edit_params.get("duration"))
                if dur <= 0: raise ValueError("Fade In duration > 0.")
                edited_clip = current_clip.fadein(dur)
            elif action == "fade_out":
                dur = float(edit_params.get("duration"))
                if dur <= 0: raise ValueError("Fade Out duration > 0.")
                edited_clip = current_clip.fadeout(dur)
            elif action == "mirror":
                direction = edit_params.get("direction", "horizontal").lower()
                if direction == "horizontal": edited_clip = current_clip.fx(vfx.mirror_x)
                elif direction == "vertical": edited_clip = current_clip.fx(vfx.mirror_y)
                else: raise ValueError("Mirror direction: 'horizontal' or 'vertical'.")
            elif action == "normalize_audio":
                if current_clip.audio:
                    normalized_audio = current_clip.audio.fx(audio_normalize)
                    edited_clip = current_clip.set_audio(normalized_audio)
                    # temp_clips_to_close.append(normalized_audio) # Not usually needed for set_audio
                else: 
                    status_update_func("No audio to normalize.", ui_colors['WARNING_FG_COLOR'])
                    edited_clip = current_clip.copy()
            elif action == "add_background_music":
                music_path_param = edit_params.get("music_path")
                if not music_path_param or "USER_SELECTS" in music_path_param.upper():
                    music_path_param = _ask_for_file_func("Select Background Music", [("Audio files", "*.mp3 *.wav *.aac")])
                if not music_path_param: raise ValueError("Background music file selection cancelled or failed.")
                
                music_clip_obj = AudioFileClip(music_path_param)
                temp_clips_to_close.append(music_clip_obj)
                
                volume_factor = float(edit_params.get("volume_factor", 0.3))
                music_start_time = float(edit_params.get("music_start_time_in_video", 0))
                loop_music = bool(edit_params.get("music_loop", False))
                
                music_to_composite = music_clip_obj.volumex(volume_factor)
                
                # Calculate duration needed for music
                video_effective_duration_for_music = current_clip.duration - music_start_time
                if video_effective_duration_for_music <= 0:
                    raise ValueError("Music start time is at or after the video ends.")

                if loop_music and music_to_composite.duration < video_effective_duration_for_music :
                     num_loops = int(video_effective_duration_for_music / music_to_composite.duration) + 1
                     looped_clips = [music_to_composite] * num_loops
                     # Check if concatenate_audioclips is imported
                     final_looped_music = concatenate_audioclips(looped_clips)
                     temp_clips_to_close.append(final_looped_music)
                     music_to_composite = final_looped_music
                
                # Ensure music does not extend beyond video duration from its start point
                music_to_composite = music_to_composite.set_duration(min(music_to_composite.duration, video_effective_duration_for_music))
                
                final_audio_segments = []
                if current_clip.audio:
                    final_audio_segments.append(current_clip.audio)
                
                final_audio_segments.append(music_to_composite.set_start(music_start_time))
                
                final_audio = CompositeAudioClip(final_audio_segments)
                temp_clips_to_close.append(final_audio)
                edited_clip = current_clip.set_audio(final_audio)

            elif action == "add_image_overlay":
                image_path_param = edit_params.get("image_path")
                if not image_path_param or "USER_SELECTS" in image_path_param.upper():
                    image_path_param = _ask_for_file_func("Select Image Overlay", [("Image files", "*.png *.jpg *.jpeg")])
                if not image_path_param: raise ValueError("Image overlay selection cancelled or failed.")
                
                img_clip_obj = ImageClip(image_path_param)
                temp_clips_to_close.append(img_clip_obj)

                pos_param = edit_params.get("position", "bottom_right")
                size_factor_param = edit_params.get("size_factor") # Can be float or tuple
                opacity = float(edit_params.get("opacity", 0.8))
                start_time = float(edit_params.get("start_time", 0))
                duration_param = edit_params.get("duration")

                if isinstance(size_factor_param, (int, float)): 
                    img_clip_obj = img_clip_obj.resize(height=int(current_clip.h * size_factor_param))
                elif isinstance(size_factor_param, (tuple,list)) and len(size_factor_param) == 2: 
                    img_clip_obj = img_clip_obj.resize(width=int(size_factor_param[0]), height=int(size_factor_param[1]))
                else: # Default sizing
                    img_clip_obj = img_clip_obj.resize(height=int(current_clip.h * 0.1)) 

                duration = max(0.1, current_clip.duration - start_time) if not duration_param else float(duration_param)
                if start_time + duration > current_clip.duration: duration = current_clip.duration - start_time
                
                img_clip_obj = img_clip_obj.set_duration(duration).set_start(start_time).set_opacity(opacity)
                img_clip_obj = img_clip_obj.set_position(parse_position_func(pos_param, current_clip.w, current_clip.h))
                edited_clip = CompositeVideoClip([current_clip, img_clip_obj])

            elif action == "picture_in_picture":
                overlay_video_path_param = edit_params.get("overlay_video_path")
                if not overlay_video_path_param or "USER_SELECTS" in overlay_video_path_param.upper():
                    overlay_video_path_param = _ask_for_file_func("Select PiP Video", [("Video files", "*.mp4 *.avi *.mov")])
                if not overlay_video_path_param: raise ValueError("PiP video selection cancelled or failed.")

                pip_clip_obj = VideoFileClip(overlay_video_path_param)
                temp_clips_to_close.append(pip_clip_obj)

                pos_param = edit_params.get("position", "top_right")
                size_factor_param = edit_params.get("size_factor") # Can be float or tuple
                start_time = float(edit_params.get("start_time", 0))
                duration_param = edit_params.get("duration")

                if isinstance(size_factor_param, (int, float)):
                     pip_clip_obj = pip_clip_obj.resize(width=int(current_clip.w * size_factor_param))
                elif isinstance(size_factor_param, (tuple, list)) and len(size_factor_param) == 2:
                     pip_clip_obj = pip_clip_obj.resize(width=int(size_factor_param[0]), height=int(size_factor_param[1]))
                else: # Default sizing
                     pip_clip_obj = pip_clip_obj.resize(width=int(current_clip.w * 0.25))

                # Ensure PiP duration is valid and doesn't exceed main clip or its own duration
                effective_pip_duration = pip_clip_obj.duration
                if duration_param:
                    effective_pip_duration = min(float(duration_param), pip_clip_obj.duration)
                
                # Ensure PiP does not extend beyond main video from its start time
                if start_time + effective_pip_duration > current_clip.duration:
                    effective_pip_duration = current_clip.duration - start_time
                if effective_pip_duration <=0 : raise ValueError("PiP duration results in zero or negative time.")


                pip_clip_obj = pip_clip_obj.set_duration(effective_pip_duration).set_start(start_time)
                pip_clip_obj = pip_clip_obj.set_position(parse_position_func(pos_param, current_clip.w, current_clip.h))
                edited_clip = CompositeVideoClip([current_clip, pip_clip_obj])

            elif action == "blur":
                radius = int(edit_params.get("radius", 2))
                edited_clip = current_clip.fx(vfx.blur, radius=radius)
            
            elif action == "concatenate":
                videos_to_append_params = edit_params.get("videos_to_append", [])
                if not videos_to_append_params: raise ValueError("No videos specified to concatenate.")
                
                clips_for_concat = [current_clip.copy()] # Start with a copy of the current clip
                
                for i, video_path_param_item in enumerate(videos_to_append_params):
                    actual_video_path = video_path_param_item
                    if "USER_SELECTS" in video_path_param_item.upper():
                        actual_video_path = _ask_for_file_func(f"Select Video {i+1} to Append", [("Video files", "*.mp4 *.avi *.mov")]) # Added more types
                    if not actual_video_path: raise ValueError(f"Video {i+1} selection for concatenation cancelled.")
                    
                    next_clip_obj = VideoFileClip(actual_video_path)
                    temp_clips_to_close.append(next_clip_obj)
                    clips_for_concat.append(next_clip_obj)
                
                if len(clips_for_concat) > 1:
                    # Ensure all clips have audio or no audio to avoid issues, or handle explicitly
                    # For simplicity, this example assumes they are compatible or MoviePy handles it.
                    # Consider adding audio normalization or padding if issues arise.
                    edited_clip = concatenate_videoclips(clips_for_concat, method="compose") # compose is often safer
                else: # Only one clip (the original), so no actual concatenation
                    edited_clip = current_clip.copy()


            else:
                error_msg = f"Error: Unknown action: {action}"
                status_update_func(error_msg, ui_colors['ERROR_FG_COLOR'])
                return {'new_video_path': None, 'updated_edit_count': current_edit_count, 'status_text': error_msg, 'status_fg': ui_colors['ERROR_FG_COLOR']}
        
        except ValueError as ve:
            error_msg = f"Parameter Error for '{action}': {str(ve)}"
            status_update_func(error_msg, ui_colors['ERROR_FG_COLOR'])
            return {'new_video_path': None, 'updated_edit_count': current_edit_count, 'status_text': f"Parameter Error for '{action}': {str(ve)}", 'status_fg': ui_colors['ERROR_FG_COLOR']}
        except Exception as e_moviepy:
            error_msg = f"MoviePy Error ('{action}'): {str(e_moviepy)[:150]}" # Already uses str() here, but good to be consistent if it didn't
            status_update_func(error_msg, ui_colors['ERROR_FG_COLOR'])
            print(f"Full MoviePy Error for {action}: {e_moviepy}") # Keep detailed log for debugging
            return {'new_video_path': None, 'updated_edit_count': current_edit_count, 'status_text': error_msg, 'status_fg': ui_colors['ERROR_FG_COLOR']}
        # `finally` for closing temp_clips is outside this try-except, placed before returning the final dict

        # Save Edited Clip
        if edited_clip:
            current_edit_count += 1 # Increment edit count for this successful edit
            try:
                original_basename, original_ext = os.path.splitext(os.path.basename(original_video_path_param))
                # Use temp_edits directory at the root for intermediate files
                edits_dir = os.path.join("temp_edits") # Changed path
                os.makedirs(edits_dir, exist_ok=True)
                
                new_filename_for_edit = os.path.join(edits_dir, f"{original_basename}_edit_{current_edit_count}{original_ext}")
                
                status_update_func(f"Saving as {os.path.basename(new_filename_for_edit)}...", ui_colors['FG_COLOR_LIGHT'])
                
                # Standard parameters for write_videofile
                edited_clip.write_videofile(new_filename_for_edit, codec="libx264", audio_codec="aac", 
                                            preset="medium", threads=os.cpu_count() or 2, logger='bar')
                
                status_text = f"Edit '{action}' applied: {os.path.basename(new_filename_for_edit)}"
                status_update_func(status_text, ui_colors['SUCCESS_FG_COLOR'])
                
                # Clean up temp_clips after successful save and before returning
                for clip_obj in temp_clips_to_close:
                    if clip_obj:
                        try: clip_obj.close()
                        except Exception as e_close: print(f"Minor error closing temp clip (after save): {e_close}")
                if edited_clip: edited_clip.close()

                return {'new_video_path': new_filename_for_edit, 'updated_edit_count': current_edit_count, 'status_text': status_text, 'status_fg': ui_colors['SUCCESS_FG_COLOR']}

            except Exception as e_save:
                error_msg = f"Error saving video: {str(e_save)[:100]}" # Already uses str() here
                status_update_func(error_msg, ui_colors['ERROR_FG_COLOR'])
                print(f"Full Save Error: {e_save}") # Keep detailed log
                # Clean up temp_clips even if save fails
                for clip_obj in temp_clips_to_close:
                    if clip_obj:
                        try: clip_obj.close()
                        except Exception as e_close: print(f"Minor error closing temp clip (save error): {e_close}")
                if edited_clip: edited_clip.close()
                return {'new_video_path': None, 'updated_edit_count': edit_count_param, 'status_text': f"Error saving video: {str(e_save)[:100]}", 'status_fg': ui_colors['ERROR_FG_COLOR']} # Ensure str(e) is used here too
        else: # No edited_clip was created (e.g., error before processing or action didn't produce one)
            status_text = f"Edit action '{action}' did not result in a new video clip."
            status_update_func(status_text, ui_colors['WARNING_FG_COLOR'])
            # Clean up clips that might have been opened
            for clip_obj in temp_clips_to_close:
                if clip_obj:
                    try: clip_obj.close()
                    except Exception as e_close: print(f"Minor error closing temp clip (no edit clip): {e_close}")
            return {'new_video_path': current_video_path_param, 'updated_edit_count': current_edit_count, 'status_text': status_text, 'status_fg': ui_colors['WARNING_FG_COLOR']}

        # Fallback return, though should be covered by above logic
        for clip_obj in temp_clips_to_close: # Ensure cleanup in all paths
            if clip_obj:
                try: clip_obj.close()
                except Exception: pass
        if edited_clip: edited_clip.close()
        return {'new_video_path': None, 'updated_edit_count': edit_count_param, 'status_text': "An unexpected state occurred in process_edit.", 'status_fg': ui_colors['ERROR_FG_COLOR']}
