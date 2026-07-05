import os
import random
import sys
import gc
import tempfile
import shutil
from moviepy import (
    VideoFileClip,
    concatenate_videoclips,
    AudioFileClip,
    vfx,
)

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
CLIPS_ROOT = r"C:\Users\User\Desktop\data for YTA\story clips"
OUTPUT_PATH = r"C:\Users\User\Desktop\Youtube video data\Secret chapter\final_video.mp4"

CHUNK_SIZE = 20                 # scenes rendered per chunk, then RAM is freed before the next chunk
MIN_CLIP_DURATION = 3.0         # sec
MAX_CLIP_DURATION = 6.0         # sec
CROSSFADE_DURATION = 0.7        # sec - fixed transition length
ENCODE_THREADS = 2               # ffmpeg threads (lowered for 8GB RAM safety)

VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".avi", ".webm")

# Fixed category sub-folders (all live inside CLIPS_ROOT). Clips are pulled
# randomly from across ALL of these folders combined - no folder is favored
# or excluded. Add/remove names here if your folder set changes later.
CATEGORY_FOLDERS = [
    "Animals", "Beach", "Birds", "Boyfriend Cheating", "Buildings",
    "Cheating Before Wedding", "Cheating Caught on Camera or Chat",
    "Cheating Confession Stories", "Cheating During Pregnancy",
    "Cheating with Best Friend", "Cheating with Ex",
    "Cheating with Siblings Partner", "City Streets", "Coffee Shop",
    "Couples", "Family Moments", "Flowers", "Forest", "Friends Talking",
    "Girlfriend Cheating", "Home & Bedroom", "Husband Cheating on Wife",
    "Lifestyle & Emotions", "Long Distance Relationship Cheating",
    "Mountains", "Nature", "Night City", "Office",
    "Online Dating App Cheating", "Parks", "Phone & Texting", "Rain",
    "Restaurant", "Revenge Cheating", "Rivers", "School", "Shopping Mall",
    "Sky", "Sunrise", "Traffic", "Travel", "Trees", "Walking People",
    "Wife Cheating on Husband", "Workplace Cheating",
]
TARGET_RESOLUTION = (1920, 1080)
EXPORT_FPS = 30
FINAL_EXPORT_PRESET = "ultrafast"
FINAL_EXPORT_CRF = "23"

# Pick ONE transition style for the whole video (per your requirement: "just
# one transition, 0.7 sec, based on the video"). Change this single line if
# you want a different one: "fade", "crossdissolve", or "cut" for no transition.
TRANSITION_STYLE = "crossdissolve"

# ----------------------------------------------------------------------------
# CLIP DISCOVERY
# ----------------------------------------------------------------------------
def list_all_clips(clips_root, category_folders):
    """
    Scans every category sub-folder inside clips_root and pools ALL video
    files found across ALL categories into one combined list. A folder that
    doesn't exist yet or has no clips is skipped with a warning instead of
    crashing the whole run.
    """
    if not os.path.isdir(clips_root):
        raise FileNotFoundError(f"Clips root folder not found: {clips_root}")

    all_files = []
    missing_or_empty = []

    for category in category_folders:
        folder_path = os.path.join(clips_root, category)
        if not os.path.isdir(folder_path):
            missing_or_empty.append(category)
            continue
        files = [
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if f.lower().endswith(VIDEO_EXTENSIONS)
        ]
        if not files:
            missing_or_empty.append(category)
            continue
        all_files.extend(files)

    if missing_or_empty:
        print(f"  ⚠ {len(missing_or_empty)} category folder(s) missing or empty (skipped): {', '.join(missing_or_empty)}")

    if not all_files:
        raise FileNotFoundError(f"No video clips found in any category folder inside: {clips_root}")

    print(f"  Pooled {len(all_files)} clip(s) from {len(category_folders) - len(missing_or_empty)} category folder(s).")
    return all_files

# ----------------------------------------------------------------------------
# RESIZE / CROP
# ----------------------------------------------------------------------------
def fit_to_resolution(clip, target_res):
    target_w, target_h = target_res
    target_ratio = target_w / target_h
    clip_ratio = clip.w / clip.h
    if clip_ratio > target_ratio:
        resized = clip.resized(height=target_h)
    else:
        resized = clip.resized(width=target_w)
    new_w, new_h = resized.w, resized.h
    x1 = int(round((new_w - target_w) / 2))
    y1 = int(round((new_h - target_h) / 2))
    return resized.cropped(x1=x1, y1=y1, width=target_w, height=target_h)

# ----------------------------------------------------------------------------
# CLIP CACHE (reuse opened handles within a chunk, close between chunks)
# ----------------------------------------------------------------------------
_clip_cache = {}

def get_cached_clip(clip_path):
    cached = _clip_cache.get(clip_path)
    if cached is not None:
        return cached
    clip = VideoFileClip(clip_path)
    _clip_cache[clip_path] = clip
    return clip

def close_all_cached_clips():
    for clip in _clip_cache.values():
        try:
            clip.close()
        except Exception:
            pass
    _clip_cache.clear()

# ----------------------------------------------------------------------------
# RANDOM SCENE PLAN (no script/table - built purely from clip pool + audio length)
# ----------------------------------------------------------------------------
def build_random_scene_plan(all_clip_paths, target_total_duration):
    """
    Builds a list of (clip_path, start_time, take_duration) tuples that:
      - never reuses the same clip file twice in one video
      - picks a random duration between MIN_CLIP_DURATION and MAX_CLIP_DURATION
      - picks a random trim start point inside that clip
      - stops once the accumulated duration covers the audio length
    If there aren't enough unique clips to cover the whole audio, it raises
    a clear error instead of silently repeating clips (per your "no repeat"
    requirement) - add more clips to the folder if this happens.

    IMPORTANT (RAM fix): this only needs each clip's DURATION to build the
    plan - it must NOT keep the clip open or cached. Opening every clip via
    the shared cache here (the old bug) meant that by the time chunked
    rendering even started, every single clip needed to cover the whole
    voiceover was already open in memory at once - defeating the entire
    point of chunking. Each clip is now opened briefly just to read its
    duration, then closed immediately before moving to the next one.
    """
    available = all_clip_paths.copy()
    random.shuffle(available)

    plan = []
    total_time = 0.0
    idx = 0

    while total_time < target_total_duration:
        if idx >= len(available):
            raise RuntimeError(
                f"Ran out of unique clips before reaching the audio length "
                f"({total_time:.1f}s built / {target_total_duration:.1f}s needed). "
                f"Add more video files to: {CLIPS_ROOT}"
            )
        clip_path = available[idx]
        idx += 1

        try:
            probe = VideoFileClip(clip_path, audio=False)
        except Exception as e:
            print(f"  ⚠ Could not open clip '{clip_path}': {e}")
            continue

        try:
            probe_duration = probe.duration
        finally:
            try:
                probe.close()
            except Exception:
                pass

        remaining_needed = target_total_duration - total_time
        wanted = random.uniform(MIN_CLIP_DURATION, MAX_CLIP_DURATION)
        take = min(wanted, remaining_needed, probe_duration)

        if take <= 0.3:
            continue  # clip too short / negligible remainder, skip it

        max_start = max(0.0, probe_duration - take)
        start_time = random.uniform(0, max_start) if max_start > 0 else 0.0

        plan.append((clip_path, start_time, take))
        total_time += take

    return plan

# ----------------------------------------------------------------------------
# BUILD CHUNK VIDEO FROM PLAN SLICE
# ----------------------------------------------------------------------------
def build_chunk_video(plan_slice, apply_transitions):
    segments = []
    for clip_path, start_time, take in plan_slice:
        clip = get_cached_clip(clip_path)
        sub = clip.subclipped(start_time, start_time + take)
        sub = fit_to_resolution(sub, TARGET_RESOLUTION)
        sub = sub.without_mask()
        segments.append(sub)

    if not apply_transitions or TRANSITION_STYLE == "cut" or len(segments) < 2:
        return concatenate_videoclips(segments, method="chain")

    processed: list = [segments[0]]
    for clip in segments[1:]:
        c = clip.with_effects([vfx.CrossFadeIn(CROSSFADE_DURATION)])
        processed.append(c)
    return concatenate_videoclips(processed, method="compose")

# ----------------------------------------------------------------------------
# MAIN PIPELINE
# ----------------------------------------------------------------------------
def main():
    print("=" * 60)
    print("  Random B-Roll Builder — NexusWithAli (low-RAM mode)")
    print("=" * 60)

    voiceover_path = input("Enter voiceover audio file path: ").strip().strip('"')
    if not os.path.isfile(voiceover_path):
        print(f"❌ Voiceover file not found: {voiceover_path}")
        sys.exit(1)

    clips_root = CLIPS_ROOT
    print(f"Using fixed clips folder: {clips_root}")

    output_path = OUTPUT_PATH
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    print(f"Output will be saved to: {output_path}")

    print("\n🎙️ Loading voiceover audio...")
    voiceover_audio = AudioFileClip(voiceover_path)
    target_duration = voiceover_audio.duration
    print(f"  Voiceover duration: {target_duration:.1f}s (video length will match this)")

    print("\n📂 Scanning fixed category folders...")
    all_clips = list_all_clips(clips_root, CATEGORY_FOLDERS)

    print("\n🎲 Building random scene plan (no repeats, 3-6s random trims)...")
    plan = build_random_scene_plan(all_clips, target_duration)
    print(f"  Plan has {len(plan)} scene(s) covering {sum(p[2] for p in plan):.1f}s.")

    close_all_cached_clips()
    gc.collect()

    temp_dir = tempfile.mkdtemp(prefix="broll_chunks_")
    print(f"  Temp chunk folder: {temp_dir}")
    chunk_file_paths = []

    try:
        total = len(plan)
        num_chunks = (total + CHUNK_SIZE - 1) // CHUNK_SIZE
        print(f"\n🎬 Rendering {total} scenes in {num_chunks} chunk(s) of up to {CHUNK_SIZE} each...")

        for chunk_idx in range(num_chunks):
            start = chunk_idx * CHUNK_SIZE
            end = min(start + CHUNK_SIZE, total)
            plan_slice = plan[start:end]

            print(f"\n  --- Chunk {chunk_idx + 1}/{num_chunks}: scenes {start + 1}-{end} ---")
            for i, (clip_path, start_time, take) in enumerate(plan_slice, start=start + 1):
                print(f"  Scene {i}: {os.path.basename(clip_path)} | trim={start_time:.1f}s→{start_time+take:.1f}s | dur={take:.1f}s")

            chunk_video = build_chunk_video(plan_slice, apply_transitions=True)
            chunk_out_path = os.path.join(temp_dir, f"chunk_{chunk_idx:03d}.mp4")
            print(f"  💾 Rendering chunk {chunk_idx + 1} to disk (frees RAM before next chunk)...")
            chunk_video.write_videofile(
                chunk_out_path,
                fps=EXPORT_FPS,
                codec="libx264",
                audio=False,
                preset=FINAL_EXPORT_PRESET,
                ffmpeg_params=["-crf", FINAL_EXPORT_CRF, "-tune", "fastdecode"],
                threads=ENCODE_THREADS,
            )
            chunk_file_paths.append(chunk_out_path)

            # CRITICAL: chunk_video wraps subclipped/resized/cropped/crossfade
            # clips that hold their own internal buffers and references back
            # to the source clips. Just clearing the source-clip cache is not
            # enough - this wrapper chain must be closed and dropped too, or
            # its memory stays alive until Python decides to overwrite the
            # variable on the next loop pass (too late on an 8GB machine).
            try:
                chunk_video.close()
            except Exception:
                pass
            del chunk_video

            close_all_cached_clips()
            gc.collect()

        print(f"\n🔗 Concatenating {len(chunk_file_paths)} chunk file(s) into the final video...")
        chunk_video_clips = [VideoFileClip(p) for p in chunk_file_paths]

        # Apply the same single transition style across chunk boundaries too,
        # so the whole video (not just within a chunk) has consistent transitions.
        if TRANSITION_STYLE == "cut" or len(chunk_video_clips) < 2:
            final_video = concatenate_videoclips(chunk_video_clips, method="chain")
        else:
            processed_chunks: list = [chunk_video_clips[0]]
            for c in chunk_video_clips[1:]:
                processed_chunks.append(c.with_effects([vfx.CrossFadeIn(CROSSFADE_DURATION)]))
            final_video = concatenate_videoclips(processed_chunks, method="compose")

        print("\n🎙️ Attaching voiceover audio...")
        if final_video.duration > voiceover_audio.duration:
            final_video = final_video.subclipped(0, voiceover_audio.duration)
        elif final_video.duration < voiceover_audio.duration:
            print("  ⚠ Video is shorter than voiceover. Voiceover will be trimmed to match video length.")
            voiceover_audio = voiceover_audio.subclipped(0, final_video.duration)

        final_video = final_video.with_audio(voiceover_audio)

        print(f"\n💾 Exporting final video to: {output_path}")
        final_video.write_videofile(
            output_path,
            fps=EXPORT_FPS,
            codec="libx264",
            audio_codec="aac",
            preset=FINAL_EXPORT_PRESET,
            ffmpeg_params=["-crf", FINAL_EXPORT_CRF, "-tune", "fastdecode"],
            threads=ENCODE_THREADS,
            temp_audiofile=os.path.join(output_dir or ".", "_temp_audio.m4a"),
            remove_temp=True,
        )

        for c in chunk_video_clips:
            try:
                c.close()
            except Exception:
                pass
        gc.collect()

        print("\n✅ Done! Your video is ready:", output_path)

    finally:
        close_all_cached_clips()
        try:
            voiceover_audio.close()
        except Exception:
            pass
        gc.collect()
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()