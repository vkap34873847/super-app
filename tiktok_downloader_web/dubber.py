import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import whisper
from googletrans import Translator
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

import edge_tts
import imageio_ffmpeg as ffmpeg

FFMPEG = ffmpeg.get_ffmpeg_exe()
SENTIMENT = SentimentIntensityAnalyzer()
TRANSLATOR = Translator()
WHISPER_MODEL = None

MALE_VOICE = "hi-IN-MadhurNeural"
FEMALE_VOICE = "hi-IN-SwaraNeural"
MALE_PITCH_THRESH = 180


def _run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def extract_audio(video_path, audio_path):
    _run([FFMPEG, "-i", str(video_path), "-vn", "-acodec", "pcm_s16le",
          "-ar", "16000", "-ac", "1", str(audio_path)])


def separate_vocals(audio_path, out_dir):
    import demucs.separate
    demucs.separate.main([
        "--two-stems", "vocals",
        "-o", str(out_dir),
        str(audio_path)
    ])
    stem_dir = out_dir / "htdemucs" / audio_path.stem
    return stem_dir / "vocals.wav", stem_dir / "no_vocals.wav"


def get_segments(vocals_path):
    global WHISPER_MODEL
    if WHISPER_MODEL is None:
        WHISPER_MODEL = whisper.load_model("base")
    result = WHISPER_MODEL.transcribe(str(vocals_path), language="en")
    return result["text"], result["segments"]


def classify_speaker(audio_path, segment, tmp_dir):
    start = segment["start"]
    end = segment["end"]
    dur = end - start
    if dur < 0.5:
        return "female"
    chunk_path = tmp_dir / f"seg_{start:.1f}.wav"
    _run([FFMPEG, "-i", str(audio_path), "-ss", str(start), "-to", str(end),
          "-ar", "16000", "-ac", "1", "-y", str(chunk_path)])
    try:
        y, sr = librosa.load(str(chunk_path), sr=16000)
        if len(y) < 400:
            return "female"
        f0, _, _ = librosa.pyin(y, fmin=librosa.note_to_hz('C2'), fmax=librosa.note_to_hz('C7'), sr=sr)
        f0 = f0[~np.isnan(f0)]
        if len(f0) == 0:
            return "female"
        avg_pitch = np.mean(f0)
        return "male" if avg_pitch < MALE_PITCH_THRESH else "female"
    except Exception:
        return "female"


def speaker_diarize(vocals_path, segments, tmp_dir):
    labeled = []
    for seg in segments:
        gender = classify_speaker(vocals_path, seg, tmp_dir)
        labeled.append({**seg, "gender": gender})
    return labeled


def translate_text(text, dest="hi"):
    return TRANSLATOR.translate(text, dest=dest).text


async def generate_speech(text, output_path, gender="female"):
    voice = MALE_VOICE if gender == "male" else FEMALE_VOICE
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(output_path))


def analyze_sentiment(texts):
    results = []
    for t in texts:
        scores = SENTIMENT.polarity_scores(t)
        if scores["compound"] >= 0.3:
            results.append("positive")
        elif scores["compound"] <= -0.3:
            results.append("negative")
        else:
            results.append("neutral")
    return results


def generate_emotional_tone(sentiment, duration_sec, sr=44100):
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    if sentiment == "positive":
        freqs = [220, 330, 440]
        amps = [0.015, 0.01, 0.005]
    elif sentiment == "negative":
        freqs = [110, 165, 220]
        amps = [0.02, 0.015, 0.01]
    else:
        freqs = [0]
        amps = [0]
    tone = np.zeros_like(t)
    for f, a in zip(freqs, amps):
        tone += a * np.sin(2 * np.pi * f * t)
    tone_stereo = np.column_stack([tone, tone])
    return tone_stereo


def get_duration(path):
    result = subprocess.run(
        [FFMPEG, "-i", str(path), "-f", "null", "-"],
        capture_output=True, text=True, timeout=30
    )
    for line in result.stderr.split("\n"):
        if "Duration" in line:
            parts = line.strip().split(",")[0].split(": ", 1)[1]
            h, m, s = parts.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def resample_match(audio_path, target_sr, output_path):
    data, sr = sf.read(str(audio_path))
    if sr == target_sr:
        if output_path != audio_path:
            os.replace(str(audio_path), str(output_path))
        return data, sr
    _run([FFMPEG, "-i", str(audio_path), "-ar", str(target_sr), str(output_path), "-y"])
    return sf.read(str(output_path))


def generate_sad_background(duration_sec, sr=44100):
    n = int(sr * duration_sec)
    t = np.linspace(0, duration_sec, n, endpoint=False)
    bg = np.zeros(n)

    chord_freqs = [55, 65.41, 82.41, 110, 130.81, 164.81, 220, 261.63]
    chord_amps = [0.10, 0.08, 0.05, 0.04, 0.03, 0.02, 0.015, 0.01]
    for f, a in zip(chord_freqs, chord_amps):
        bg += a * np.sin(2 * np.pi * f * t)

    mod = 0.5 + 0.5 * np.sin(2 * np.pi * 0.12 * t)
    bg = bg * mod

    fade = min(int(1.0 * sr), n // 4)
    bg[:fade] *= np.linspace(0, 1, fade)
    bg[-fade:] *= np.linspace(1, 0, fade)

    peak = max(abs(bg).max(), 1e-10)
    bg = bg / peak * 0.25
    return np.column_stack([bg, bg])


def mix_with_music(vocals_segments, bg_path, emotion_tones, output_path, video_dur):
    bg_data, bg_sr = sf.read(str(bg_path))
    if len(bg_data.shape) == 1:
        bg_data = np.column_stack([bg_data, bg_data])
    target_sr = bg_sr

    mixed = bg_data.copy()

    for seg_data, start_sample, _ in vocals_segments:
        if start_sample < len(mixed):
            seg_len = min(seg_data.shape[0], len(mixed) - start_sample)
            mixed[start_sample:start_sample + seg_len] += seg_data[:seg_len] * 1.5

    tone_total = np.zeros_like(mixed)
    for tone_data, start_sample, _ in emotion_tones:
        if start_sample < len(tone_total):
            tone_len = min(tone_data.shape[0], len(tone_total) - start_sample)
            tone_total[start_sample:start_sample + tone_len] += tone_data[:tone_len]

    mixed = mixed + tone_total * 0.15
    peak = max(abs(mixed).max(), 1e-10)
    mixed = mixed / peak * 0.95
    sf.write(str(output_path), mixed, target_sr)


def dub_video(video_path, output_path, tmp_dir=None):
    ff_dir = str(Path(FFMPEG).parent)
    bin_dir = str(Path.home() / "bin")
    os.environ["PATH"] = bin_dir + os.pathsep + ff_dir + os.pathsep + os.environ.get("PATH", "")

    if tmp_dir is None:
        tmp_dir = Path(tempfile.mkdtemp())
    else:
        tmp_dir = Path(tmp_dir)
        tmp_dir.mkdir(parents=True, exist_ok=True)

    print("1/7 Extracting audio...")
    raw_audio = tmp_dir / "raw_audio.wav"
    extract_audio(video_path, raw_audio)

    print("2/7 Separating vocals from music...")
    sep_dir = tmp_dir / "separated"
    vocals, music = separate_vocals(raw_audio, sep_dir)

    print("3/7 Transcribing & diarizing speakers...")
    full_text, segments = get_segments(vocals)
    if not full_text.strip():
        raise ValueError("No speech detected in video")
    labeled_segs = speaker_diarize(vocals, segments, tmp_dir)
    print(f"   Speakers found: {len(set(s['gender'] for s in labeled_segs))} "
          f"({', '.join(sorted(set(s['gender'] for s in labeled_segs)))})")

    print("4/7 Translating & analyzing emotion...")
    seg_texts = [s["text"].strip() for s in labeled_segs if s["text"].strip()]
    hindi_texts = [translate_text(t) for t in seg_texts]
    emotions = analyze_sentiment(seg_texts)
    print(f"   Emotions: {', '.join(set(emotions))}")

    print("5/7 Generating Hindi speech with character voices...")
    speech_segments = []
    for i, seg in enumerate(labeled_segs):
        if not seg["text"].strip():
            continue
        gender = seg["gender"]
        hindi = hindi_texts[i]
        out_file = tmp_dir / f"speech_{i}.wav"
        asyncio.run(generate_speech(hindi, out_file, gender))
        dur = get_duration(out_file)
        speech_segments.append({
            "path": out_file,
            "gender": gender,
            "duration": dur,
            "original_start": seg["start"],
            "original_end": seg["end"],
        })

    print("6/7 Mixing Hindi speech + emotional music...")
    video_dur = get_duration(video_path)
    target_sr = 44100

    sad_bg_path = tmp_dir / "sad_background.wav"
    sad_bg = generate_sad_background(video_dur, target_sr)
    sf.write(str(sad_bg_path), sad_bg, target_sr)

    vocals_orig, vocals_orig_sr = sf.read(str(vocals))
    if len(vocals_orig.shape) > 1:
        vocals_orig = vocals_orig.mean(axis=1)
    if vocals_orig_sr != target_sr:
        vocals_orig = librosa.resample(vocals_orig, orig_sr=vocals_orig_sr, target_sr=target_sr)

    vocals_segments = []
    emotion_tones = []

    for i, seg in enumerate(speech_segments):
        data, sr = sf.read(str(seg["path"]))
        orig_dur = seg["original_end"] - seg["original_start"]
        rate = seg["duration"] / max(orig_dur, 0.1)
        rate = max(0.5, min(2.0, rate))
        stretched = tmp_dir / f"stretched_{i}.wav"
        _run([FFMPEG, "-i", str(seg["path"]), "-filter:a", f"atempo={rate}",
              "-y", str(stretched)])
        stretched_data, stretched_sr = sf.read(str(stretched))

        if len(stretched_data.shape) == 1:
            stretched_data = np.column_stack([stretched_data, stretched_data])
        if stretched_sr != target_sr:
            stretched_data = librosa.resample(
                stretched_data.T, orig_sr=stretched_sr, target_sr=target_sr
            ).T

        start_sample = int(seg["original_start"] * target_sr)
        end_sample = min(start_sample + len(stretched_data), len(vocals_orig))

        orig_section = vocals_orig[start_sample:end_sample]
        orig_rms = max(np.sqrt(np.mean(orig_section ** 2)), 1e-6)
        speech_rms = max(np.sqrt(np.mean(stretched_data ** 2)), 1e-6)
        scale = orig_rms / speech_rms
        scale = min(scale, 5.0)
        stretched_data = stretched_data * scale

        vocals_segments.append((stretched_data, start_sample, start_sample + len(stretched_data)))

        emotion = emotions[i] if i < len(emotions) else "neutral"
        seg_dur = len(stretched_data) / target_sr
        tone = generate_emotional_tone(emotion, seg_dur, target_sr)
        emotion_tones.append((tone, start_sample, start_sample + len(tone)))

    mix_with_music(vocals_segments, sad_bg_path, emotion_tones,
                   tmp_dir / "mixed_audio.wav", video_dur)

    print("7/7 Replacing audio in video...")
    replace_audio(video_path, tmp_dir / "mixed_audio.wav", output_path)
    return output_path


def replace_audio(video_path, new_audio_path, output_path):
    _run([FFMPEG, "-i", str(video_path), "-i", str(new_audio_path),
          "-c:v", "copy", "-map", "0:v:0", "-map", "1:a:0",
          "-shortest", "-y", str(output_path)])
