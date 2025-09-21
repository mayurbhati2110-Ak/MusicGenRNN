"""
FastAPI backend for AI music generation pipeline (pure Python rough version).

- Serves list of tunes and original WAVs
- Sends chosen tune's ABC to Hugging Face Space (public) and receives generated ABC
- Converts ABC -> rough MIDI -> WAV
- Returns WAV to frontend
"""

import os
import uuid
import re
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from midi2audio import FluidSynth
from mido import Message, MidiFile, MidiTrack, bpm2tempo

# ---------- CONFIG ----------
BASE_DIR = Path(__file__).resolve().parent
TUNES_DIR = BASE_DIR / "tunes"
STATIC_DIR = BASE_DIR / "static"
ORIG_DIR = STATIC_DIR / "original"
GEN_DIR = STATIC_DIR / "generated"
SOUNDFONT_PATH = BASE_DIR / "soundfonts" / "FluidR3_GM.sf2"


HF_API_URL = "https://mayurbhati2110-MusicGenRNN.hf.space/generate"

# Create directories
ORIG_DIR.mkdir(parents=True, exist_ok=True)
GEN_DIR.mkdir(parents=True, exist_ok=True)
TUNES_DIR.mkdir(parents=True, exist_ok=True)

# ---------- Tunes ----------
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ---------- Helpers ----------
def find_tune_entry(tune_id: int):
    for t in TUNES:
        if t["id"] == tune_id:
            return t
    return None


def call_hf_space(abc_text: str) -> str:
    print("🌐 [HF] Calling Hugging Face Space...")
    try:
        res = requests.post(HF_API_URL, data={"seed": abc_text, "length": 100}, timeout=180)
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
    # Remove illegal characters and ensure L: is present
    abc_text = re.sub(r'[^A-Ga-gzZ0-9\/\[\]#b|: \n]', '', abc_text)
    if "L:" not in abc_text:
        abc_text = "L:1/8\n" + abc_text
    return abc_text


def abc_to_midi_simple(abc_text: str, midi_path: Path) -> bool:
    """
    Rough ABC -> MIDI conversion: converts letters A-G to MIDI notes
    Ignores timing and advanced notation; produces playable MIDI
    """
    note_base = {"C": 60, "D": 62, "E": 64, "F": 65, "G": 67, "A": 69, "B": 71}
    midi_file = MidiFile()
    track = MidiTrack()
    midi_file.tracks.append(track)
    track.append(Message('program_change', program=0, time=0))
    tempo = bpm2tempo(120)
    track.append(Message('note_on', note=60, velocity=0, time=0))  # dummy

    for c in abc_text.upper():
        if c in note_base:
            track.append(Message('note_on', note=note_base[c], velocity=64, time=0))
            track.append(Message('note_off', note=note_base[c], velocity=64, time=240))
    try:
        midi_file.save(str(midi_path))
        return midi_path.exists()
    except Exception as e:
        print("❌ abc_to_midi_simple failed:", e)
        return False


def midi_to_wav(midi_path: Path, wav_path: Path, sf_path: Path) -> bool:
    if not sf_path.exists():
        print("⚠️ SoundFont missing")
        return False
    try:
        fs = FluidSynth(str(sf_path))
        fs.midi_to_audio(str(midi_path), str(wav_path))
        return wav_path.exists()
    except Exception as e:
        print("❌ MIDI->WAV failed:", e)
        return False


# ---------- API Endpoints ----------
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
        raise HTTPException(status_code=404, detail="ABC file missing")
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
        raise HTTPException(status_code=404, detail="Tune not found")
    abc_path = TUNES_DIR / t["abc"]
    if not abc_path.exists():
        raise HTTPException(status_code=404, detail="ABC file missing")

    with open(abc_path, "r", encoding="utf-8") as f:
        abc_text = f.read()
    print(f"📄 [Generate] Loaded ABC length={len(abc_text)}")

    try:
        generated_abc = call_hf_space(abc_text)
        generated_abc = sanitize_abc(generated_abc)
        print(f"💾 [Generate] Sanitized ABC length={len(generated_abc)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hugging Face Space call failed: {e}")

    uid = uuid.uuid4().hex
    gen_midi_path = GEN_DIR / f"{tune_id}_{uid}.mid"
    gen_wav_path = GEN_DIR / f"{tune_id}_{uid}.wav"

    # Convert ABC -> rough MIDI
    if not abc_to_midi_simple(generated_abc, gen_midi_path):
        orig_path = ORIG_DIR / t["orig_audio"]
        print("⚠️ Returning original audio due to ABC->MIDI failure")
        return FileResponse(str(orig_path), media_type="audio/wav", filename=orig_path.name)

    # Convert MIDI -> WAV
    if not midi_to_wav(gen_midi_path, gen_wav_path, SOUNDFONT_PATH):
        orig_path = ORIG_DIR / t["orig_audio"]
        print("⚠️ Returning original audio due to MIDI->WAV failure")
        return FileResponse(str(orig_path), media_type="audio/wav", filename=orig_path.name)

    print(f"✅ [Generate] Returning WAV -> {gen_wav_path}\n")
    return FileResponse(str(gen_wav_path), media_type="audio/wav", filename=gen_wav_path.name)
