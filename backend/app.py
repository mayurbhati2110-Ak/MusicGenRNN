"""
FastAPI backend for AI music generation pipeline.

- Serves list of tunes and original WAVs
- Sends chosen tune's ABC to Hugging Face Space (public) and receives generated ABC
- Converts generated ABC -> MIDI -> WAV using fluidsynth (preferred) or ffmpeg fallback
- Returns generated WAV to frontend
"""

import os
import uuid
import subprocess
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from music21 import converter, midi
from fastapi.middleware.cors import CORSMiddleware   # ✅ CORS

# ---------- CONFIG ----------
BASE_DIR = Path(__file__).resolve().parent
TUNES_DIR = BASE_DIR / "tunes"                 # .abc files (input)
STATIC_DIR = BASE_DIR / "static"               # for original & generated audio
ORIG_DIR = STATIC_DIR / "original"
GEN_DIR = STATIC_DIR / "generated"
SOUNDFONT_DIR = BASE_DIR / "soundfonts"
SOUNDFONT_PATH = SOUNDFONT_DIR / "FluidR3_GM.sf2"  # place a .sf2 here for fluidsynth

HF_API_URL = "https://mayurbhati2110-MusicGenRNN.hf.space/generate"  # <-- your Hugging Face Space
HF_API_TOKEN = ""  # optional

# Make sure directories exist
ORIG_DIR.mkdir(parents=True, exist_ok=True)
GEN_DIR.mkdir(parents=True, exist_ok=True)
TUNES_DIR.mkdir(parents=True, exist_ok=True)
SOUNDFONT_DIR.mkdir(parents=True, exist_ok=True)

# ---------- Tune registry ----------
TUNES = [
    {"id": 1, "title": "Tune 1", "abc": "tune_1.abc", "orig_audio": "tune_1.wav"},
    {"id": 2, "title": "Tune 2", "abc": "tune_2.abc", "orig_audio": "tune_2.wav"},
    {"id": 3, "title": "Tune 3", "abc": "tune_3.abc", "orig_audio": "tune_3.wav"},
    {"id": 4, "title": "Tune 4", "abc": "tune_4.abc", "orig_audio": "tune_4.wav"},
    {"id": 5, "title": "Tune 5", "abc": "tune_5.abc", "orig_audio": "tune_5.wav"},
    {"id": 6, "title": "Tune 6", "abc": "tune_6.abc", "orig_audio": "tune_6.wav"},
    {"id": 7, "title": "Tune 7", "abc": "tune_7.abc", "orig_audio": "tune_7.wav"},
    {"id": 8, "title": "Tune 8", "abc": "tune_8.abc", "orig_audio": "tune_8.wav"},
    {"id": 9, "title": "Tune 9", "abc": "tune_9.abc", "orig_audio": "tune_9.wav"},
    {"id": 10, "title": "Tune 10", "abc": "tune_10.abc", "orig_audio": "tune_10.wav"},
]

# ---------- FastAPI app ----------
app = FastAPI(title="MusicGen Backend")

# ✅ CORS fix (allow frontend to call backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to ["https://mayurbhati2110-ak.github.io"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# mount static files at /static
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def find_tune_entry(tune_id: int):
    for t in TUNES:
        if t["id"] == tune_id:
            return t
    return None


def call_hf_space(abc_text: str) -> str:
    """Call Hugging Face Space /generate endpoint."""
    print("🌐 [HF] Calling Hugging Face Space...")
    try:
        res = requests.post(
            HF_API_URL,
            data={"seed": abc_text, "length": 100},  # form fields, not JSON
            timeout=180
        )
        res.raise_for_status()
        j = res.json()
        if "generated" in j:
            print(f"✅ [HF] Received generated ABC length={len(j['generated'])}")
            return j["generated"]
        raise RuntimeError(f"Unexpected response: {j}")
    except Exception as e:
        print(f"❌ [HF] Call failed: {e}")
        raise RuntimeError(f"Hugging Face call failed: {e}")


def sanitize_abc(abc_text: str) -> str:
    """
    Simple sanitization to avoid music21 parsing errors:
    - Remove empty lines
    - Remove duplicate TimeSignature (M:) and KeySignature (K:) lines
    """
    lines = abc_text.splitlines()
    sanitized = []
    seen_headers = set()
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        if line_strip.startswith("M:") or line_strip.startswith("K:"):
            if line_strip in seen_headers:
                continue
            seen_headers.add(line_strip)
        sanitized.append(line_strip)
    return "\n".join(sanitized)


def abc_to_midi(abc_path: Path, midi_path: Path):
    print(f"🎼 [MIDI] Converting {abc_path} -> {midi_path}")
    score = converter.parse(str(abc_path), format="abc")
    mf = midi.translate.music21ObjectToMidiFile(score)
    mf.open(str(midi_path), "wb")
    mf.write()
    mf.close()
    print("✅ [MIDI] Conversion success")


def midi_to_wav_with_fluidsynth(midi_path: Path, wav_path: Path, soundfont_path: Path) -> bool:
    if not soundfont_path.exists():
        print("⚠️ [Fluidsynth] SoundFont not found, skipping.")
        return False
    cmd = [
        "fluidsynth", "-ni", str(soundfont_path), str(midi_path),
        "-F", str(wav_path), "-r", "44100"
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("✅ [Fluidsynth] WAV created")
        return wav_path.exists()
    except Exception as e:
        print("❌ [Fluidsynth] failed:", e)
        return False


def midi_to_wav_with_ffmpeg(midi_path: Path, wav_path: Path) -> bool:
    cmd = ["ffmpeg", "-y", "-i", str(midi_path), str(wav_path)]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("✅ [FFmpeg] WAV created")
        return wav_path.exists()
    except Exception as e:
        print("❌ [FFmpeg] failed:", e)
        return False


@app.get("/list")
def list_tunes():
    out = []
    for t in TUNES:
        orig_path = ORIG_DIR / t["orig_audio"]
        orig_url = f"/static/original/{t['orig_audio']}" if orig_path.exists() else None
        out.append({"id": t["id"], "title": t["title"], "orig_audio_url": orig_url})
    return out


@app.get("/abc/{tune_id}")
def get_abc(tune_id: int):
    t = find_tune_entry(tune_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tune not found")
    abc_file = TUNES_DIR / t["abc"]
    if not abc_file.exists():
        raise HTTPException(status_code=404, detail="ABC file missing on server")
    return FileResponse(str(abc_file), media_type="text/plain", filename=abc_file.name)


@app.get("/original/{tune_id}")
def get_original_audio(tune_id: int):
    t = find_tune_entry(tune_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tune not found")
    path = ORIG_DIR / t["orig_audio"]
    if not path.exists():
        raise HTTPException(status_code=404, detail="Original audio missing")
    return FileResponse(str(path), media_type="audio/wav", filename=path.name)


@app.get("/generate/{tune_id}")
def generate(tune_id: int):
    print(f"\n➡️ [Generate] Starting for tune_id={tune_id}")

    t = find_tune_entry(tune_id)
    if not t:
        print("❌ Tune not found")
        raise HTTPException(status_code=404, detail="Tune not found")

    abc_path = TUNES_DIR / t["abc"]
    if not abc_path.exists():
        print("❌ ABC file missing")
        raise HTTPException(status_code=404, detail="ABC file missing")

    with open(abc_path, "r", encoding="utf-8") as f:
        abc_text = f.read()
    print(f"📄 [Generate] Loaded ABC length={len(abc_text)}")

    # Call Hugging Face
    try:
        generated_abc = call_hf_space(abc_text)
        generated_abc = sanitize_abc(generated_abc)
        print(f"💾 [Generate] Sanitized generated ABC length={len(generated_abc)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hugging Face Space call failed: {e}")

    uid = uuid.uuid4().hex
    gen_abc_path = GEN_DIR / f"{tune_id}_{uid}.abc"
    gen_midi_path = GEN_DIR / f"{tune_id}_{uid}.mid"
    gen_wav_path = GEN_DIR / f"{tune_id}_{uid}.wav"

    with open(gen_abc_path, "w", encoding="utf-8") as f:
        f.write(generated_abc)
    print(f"💾 [Generate] Saved generated ABC -> {gen_abc_path}")

    # Convert to MIDI
    try:
        abc_to_midi(gen_abc_path, gen_midi_path)
    except Exception as e:
        print(f"❌ ABC->MIDI failed: {e}")
        # Fallback: return original WAV instead of crashing
        orig_path = ORIG_DIR / t["orig_audio"]
        if orig_path.exists():
            print(f"⚠️ Returning original WAV due to ABC->MIDI failure -> {orig_path}")
            return FileResponse(str(orig_path), media_type="audio/wav", filename=orig_path.name)
        raise HTTPException(status_code=500, detail=f"ABC->MIDI failed: {e}")

    # Convert to WAV
    ok = False
    if SOUNDFONT_PATH.exists():
        print("🎹 [Generate] Trying Fluidsynth...")
        ok = midi_to_wav_with_fluidsynth(gen_midi_path, gen_wav_path, SOUNDFONT_PATH)
    if not ok:
        print("🎧 [Generate] Trying FFmpeg fallback...")
        ok = midi_to_wav_with_ffmpeg(gen_midi_path, gen_wav_path)

    if not ok or not gen_wav_path.exists():
        print("❌ MIDI->WAV synthesis failed")
        # Fallback: return original WAV if generated WAV fails
        orig_path = ORIG_DIR / t["orig_audio"]
        if orig_path.exists():
            print(f"⚠️ Returning original WAV due to WAV synthesis failure -> {orig_path}")
            return FileResponse(str(orig_path), media_type="audio/wav", filename=orig_path.name)
        raise HTTPException(status_code=500, detail="MIDI->WAV synthesis failed (need fluidsynth or ffmpeg support)")

    print(f"✅ [Generate] Returning WAV -> {gen_wav_path}\n")
    return FileResponse(str(gen_wav_path), media_type="audio/wav", filename=gen_wav_path.name)
