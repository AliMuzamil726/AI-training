"""
NexusWithAli - Auto Video Editor
==================================
Voiceover ko transcribe karta hai, uske content ke hisab se
relevant clips ko category folders se match karta hai, aur
ek final stitched video banata hai.

REQUIREMENTS (apne computer pe install karo):
    pip install faster-whisper moviepy

FFmpeg bhi zaroori hai:
    Windows: https://ffmpeg.org/download.html se download karo, PATH mein add karo
    (ya: pip install imageio-ffmpeg  -- moviepy khud isko use kar leta hai)

FOLDER STRUCTURE (expected):
    clips/
        heart/
            heart1.mp4
            heart2.mp4
            ...
        arm/
            arm1.mp4
            ...
        doctor_checking/
            doc1.mp4
            ...

USAGE:
    python auto_video_editor.py --voiceover "path/to/voice.mp3" --clips "path/to/clips_folder" --output "final_video.mp4"
"""

import os
import re
import random
import json
from pathlib import Path

# ---------------------------------------------------------
# STEP 0: Config - category keywords (customize as needed)
# ---------------------------------------------------------
# Har category ke liye related keywords likho, jo transcript
# mein dhoonde jayenge. Category ka apna naam automatically
# bhi ek keyword ke tor pe include ho jata hai.

CATEGORY_KEYWORDS = {
    "heart": ["heart", "cardiac", "pulse", "blood pressure", "cardiovascular", "artery"],
    "arm": ["arm", "muscle", "bicep", "hand", "forearm", "injection", "vein"],
    "doctor_checking": ["doctor", "checkup", "examine", "clinic", "physician", "hospital", "patient", "diagnosis"],
    # Yahan apni real categories add karo, isi format mein:
    # "category_folder_name": ["keyword1", "keyword2", ...],
}

SEGMENT_DURATION = 4.0  # seconds - transcript ko kitne der ke chunks mein todna hai
MAX_CLIP_DURATION = 5.0  # seconds - har clip se max itna hi time lena hai, baqi skip


# ---------------------------------------------------------
# STEP 1: Transcribe voiceover with word-level timestamps
# ---------------------------------------------------------
def transcribe_voiceover(audio_path, model_size="base"):
    """
    faster-whisper se voiceover transcribe karta hai.
    Returns: list of words with start/end timestamps.
    """
    from faster_whisper import WhisperModel

    print(f"[1/5] Transcribing voiceover: {audio_path}")
    print("      (pehli baar model download hoga, thoda time lagega)")

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(audio_path, word_timestamps=True)

    words = []
    full_segments = []
    for seg in segments:
        full_segments.append({"start": seg.start, "end": seg.end, "text": seg.text})
        if seg.words:
            for w in seg.words:
                words.append({"word": w.word, "start": w.start, "end": w.end})

    print(f"      Duration: {info.duration:.1f}s | Language: {info.language}")
    return words, full_segments, info.duration


# ---------------------------------------------------------
# STEP 2: Break transcript into fixed-duration chunks
# ---------------------------------------------------------
def build_chunks(words, total_duration, chunk_len=SEGMENT_DURATION):
    """
    Words ko fixed-duration chunks mein group karta hai,
    har chunk ka combined text nikal ke. Chunk length kabhi
    MAX_CLIP_DURATION se bari nahi hogi (usse zyada waqt
    wapas voiceover mein "skip" ho jayega, koi clip nahi milegi).
    """
    effective_len = min(chunk_len, MAX_CLIP_DURATION)
    print(f"[2/5] Building {effective_len}s segments (max clip length: {MAX_CLIP_DURATION}s)...")

    chunks = []
    t = 0.0
    while t < total_duration:
        chunk_end = min(t + effective_len, total_duration)
        chunk_words = [w["word"] for w in words if w["start"] >= t and w["start"] < chunk_end]
        text = " ".join(chunk_words).strip()
        chunks.append({"start": t, "end": chunk_end, "text": text})
        t = chunk_end

    print(f"      Created {len(chunks)} segments")
    return chunks


# ---------------------------------------------------------
# STEP 3: Scan clips folder for categories
# ---------------------------------------------------------
def scan_clips_folder(clips_root):
    """
    clips_root ke andar har subfolder ek category hai.
    Returns: {category_name: [list_of_clip_paths]}
    """
    print(f"[3/5] Scanning clips folder: {clips_root}")

    categories = {}
    root = Path(clips_root)
    valid_ext = {".mp4", ".mov", ".avi", ".mkv"}

    for folder in root.iterdir():
        if folder.is_dir():
            clips = [str(f) for f in folder.iterdir() if f.suffix.lower() in valid_ext]
            if clips:
                categories[folder.name.lower()] = clips

    for cat, clips in categories.items():
        print(f"      {cat}: {len(clips)} clips")

    if not categories:
        raise ValueError("Koi category folder nahi mili! Check karo clips_root path sahi hai.")

    return categories


# ---------------------------------------------------------
# STEP 4: Match each chunk's text to the best category
# ---------------------------------------------------------
def match_category(text, categories, keyword_map, fallback_category=None):
    """
    Chunk text ko category keywords se match karta hai.
    Score = kitne keywords match hue.
    """
    text_lower = text.lower()
    best_cat = None
    best_score = 0

    for cat in categories:
        keywords = keyword_map.get(cat, [cat])  # agar keywords defined nahi, folder ka naam use karo
        score = 0
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw.lower()) + r"\b", text_lower):
                score += 1
        if score > best_score:
            best_score = score
            best_cat = cat

    if best_cat is None:
        # Fallback: closest/general category (default: first category, ya specify karo)
        best_cat = fallback_category or list(categories.keys())[0]

    return best_cat, best_score


def assign_clips_to_chunks(chunks, categories, keyword_map, fallback_category=None):
    """
    Har chunk ke liye category match karta hai aur us category
    se ek random clip select karta hai.
    """
    print("[4/5] Matching segments to clips...")

    assignments = []
    for chunk in chunks:
        if not chunk["text"]:
            # Silence/no speech - fallback category use karo
            cat = fallback_category or list(categories.keys())[0]
            score = 0
        else:
            cat, score = match_category(chunk["text"], categories, keyword_map, fallback_category)

        clip_path = random.choice(categories[cat])

        assignments.append({
            "start": chunk["start"],
            "end": chunk["end"],
            "duration": chunk["end"] - chunk["start"],
            "text": chunk["text"],
            "category": cat,
            "match_score": score,
            "clip": clip_path,
        })
        match_note = "matched" if score > 0 else "fallback"
        print(f"      [{chunk['start']:6.1f}s-{chunk['end']:6.1f}s] '{chunk['text'][:40]}' -> {cat} ({match_note})")

    return assignments


# ---------------------------------------------------------
# STEP 5: Stitch clips together with moviepy, synced to voiceover
# ---------------------------------------------------------
def build_final_video(assignments, voiceover_path, output_path):
    """
    Har assignment ke clip ko uski required duration tak trim/loop
    karta hai, sabko jodta hai, aur voiceover audio overlay karta hai.
    """
    from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip

    print(f"[5/5] Building final video -> {output_path}")

    processed_clips = []
    # Cache loaded clips so we don't reopen the same file repeatedly
    clip_cache = {}

    for i, a in enumerate(assignments):
        duration = min(a["duration"], MAX_CLIP_DURATION)
        if duration <= 0:
            continue

        path = a["clip"]
        if path not in clip_cache:
            clip_cache[path] = VideoFileClip(path)
        source = clip_cache[path]

        if source.duration >= duration:
            # Trim: random start point so it's not always the same portion
            max_start = max(0, source.duration - duration)
            start = random.uniform(0, max_start) if max_start > 0 else 0
            sub = source.subclip(start, start + duration)
        else:
            # Clip is shorter than needed - loop it
            loops_needed = int(duration / source.duration) + 1
            looped = concatenate_videoclips([source] * loops_needed)
            sub = looped.subclip(0, duration)

        sub = sub.without_audio()  # remove original clip audio - voiceover replaces it
        processed_clips.append(sub)
        print(f"      Segment {i+1}/{len(assignments)} ready ({a['category']}, {duration:.1f}s)")

    print("      Concatenating all clips...")
    final_video = concatenate_videoclips(processed_clips, method="compose")

    print("      Adding voiceover audio...")
    voiceover_audio = AudioFileClip(voiceover_path)
    final_video = final_video.set_audio(voiceover_audio)

    # Match final video length to voiceover exactly
    final_video = final_video.subclip(0, min(final_video.duration, voiceover_audio.duration))

    final_video.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=30,
        threads=4,
        preset="medium",
    )

    # Cleanup
    for c in clip_cache.values():
        c.close()
    voiceover_audio.close()

    print(f"\n✅ Done! Final video saved: {output_path}")


# ---------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------
def clean_path(p):
    """User path se quotes/extra spaces hata deta hai (copy-paste se aksar aa jate hain)."""
    return p.strip().strip('"').strip("'")


def main():
    print("=" * 55)
    print("  NexusWithAli - Auto Video Editor")
    print("=" * 55)
    print()

    voiceover_path = clean_path(input("Voiceover audio file ka path do (mp3/wav): "))
    while not os.path.isfile(voiceover_path):
        print("  ❌ File nahi mili, dobara sahi path do.")
        voiceover_path = clean_path(input("Voiceover audio file ka path do (mp3/wav): "))

    clips_folder = clean_path(input("Clips wali folder ka path do (categories ke subfolders wali): "))
    while not os.path.isdir(clips_folder):
        print("  ❌ Folder nahi mili, dobara sahi path do.")
        clips_folder = clean_path(input("Clips wali folder ka path do: "))

    output_path = clean_path(input("Output video ka naam/path do [default: final_video.mp4]: ") or "final_video.mp4")

    print()
    print("Ab automatic pipeline chal rahi hai, bas thoda intezar karo...")
    print()

    # Auto-run all steps, no further input needed
    words, segments, duration = transcribe_voiceover(voiceover_path, "base")
    chunks = build_chunks(words, duration)
    categories = scan_clips_folder(clips_folder)
    fallback_category = list(categories.keys())[0]  # sabse pehli category ko default fallback rakho
    assignments = assign_clips_to_chunks(chunks, categories, CATEGORY_KEYWORDS, fallback_category)

    # Plan ko hamesha save karo reference ke liye
    plan_path = os.path.join(os.path.dirname(output_path) or ".", "matching_plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(assignments, f, indent=2, ensure_ascii=False)
    print(f"      Matching plan save hui: {plan_path}")

    build_final_video(assignments, voiceover_path, output_path)


if __name__ == "__main__":
    main()