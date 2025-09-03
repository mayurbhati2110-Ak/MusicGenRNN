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
from typing import List
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from music21 import converter, midi

# ---------- CONFIG ----------
BASE_DIR = Path(__file__).resolve().parent
TUNES_DIR = BASE_DIR / "tunes"                 # .abc files (input)
STATIC_DIR = BASE_DIR / "static"               # for original & generated audio
ORIG_DIR = STATIC_DIR / "original"
GEN_DIR = STATIC_DIR / "generated"
SOUNDFONT_DIR = BASE_DIR / "soundfonts"
SOUNDFONT_PATH = SOUNDFONT_DIR / "FluidR3_GM.sf2"  # place a .sf2 here for fluidsynth

HF_API_URL = "https://mayurbhati2110-MusicGenRNN.hf.space/run/predict"  # <-- REPLACE with your Space API URL
# For a public space you usually don't need a token. If your space needs it, set HF_API_TOKEN below.
HF_API_TOKEN = ""  # optional

# Make sure directories exist
ORIG_DIR.mkdir(parents=True, exist_ok=True)
GEN_DIR.mkdir(parents=True, exist_ok=True)
TUNES_DIR.mkdir(parents=True, exist_ok=True)
SOUNDFONT_DIR.mkdir(parents=True, exist_ok=True)

# ---------- Tune registry ----------
# We expect tunes: tunes/tune1.abc ... tune10.abc and original wavs in static/original/tune1.wav etc.
# If you prefer other names, update this list accordingly.
TUNES = [
    {"id": 1, "title": "Tune 1", "abc": "tune1.abc", "orig_audio": "tune1.wav"},
    {"id": 2, "title": "Tune 2", "abc": "tune2.abc", "orig_audio": "tune2.wav"},
    {"id": 3, "title": "Tune 3", "abc": "tune3.abc", "orig_audio": "tune3.wav"},
    {"id": 4, "title": "Tune 4", "abc": "tune4.abc", "orig_audio": "tune4.wav"},
    {"id": 5, "title": "Tune 5", "abc": "tune5.abc", "orig_audio": "tune5.wav"},
    {"id": 6, "title": "Tune 6", "abc": "tune6.abc", "orig_audio": "tune6.wav"},
    {"id": 7, "title": "Tune 7", "abc": "tune7.abc", "orig_audio": "tune7.wav"},
    {"id": 8, "title": "Tune 8", "abc": "tune8.abc", "orig_audio": "tune8.wav"},
    {"id": 9, "title": "Tune 9", "abc": "tune9.abc", "orig_audio": "tune9.wav"},
    {"id": 10, "title": "Tune 10", "abc": "tune10.abc", "orig_audio": "tune10.wav"},
]

# ---------- FastAPI app ----------
app = FastAPI(title="MusicGen Backend")

# mount static files at /static
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def find_tune_entry(tune_id: int):
    for t in TUNES:
        if t["id"] == tune_id:
            return t
    return None


def call_hf_space(abc_text: str) -> str:
    """
    Call Hugging Face Space predict endpoint.
    Most Spaces expose /run/predict (returns JSON with 'data' list).
    If your Space returns a different JSON, adapt this parser.
    """
    headers = {"Content-Type": "application/json"}
    if HF_API_TOKEN:
        headers["Authorization"] = f"Bearer {HF_API_TOKEN}"

    payload = {"data": [abc_text]}
    res = requests.post(HF_API_URL, json=payload, headers=headers, timeout=60)
    if res.status_code != 200:
        raise RuntimeError(f"Hugging Face Space returned {res.status_code}: {res.text}")

    j = res.json()
    # Many spaces return {"data": [<output>], ...}
    if isinstance(j, dict):
        if "data" in j and isinstance(j["data"], list) and len(j["data"]) > 0:
            return j["data"][0]
        # fallback keys
        if "generated_text" in j:
            return j["generated_text"]
        if "abc" in j:
            return j["abc"]
    # fallback: try raw text
    if isinstance(j, list) and len(j) > 0 and isinstance(j[0], str):
        return j[0]

    raise RuntimeError("Could not parse Hugging Face Space response JSON.")


def abc_to_midi(abc_path: Path, midi_path: Path):
    """Convert ABC file to MIDI using music21."""
    score = converter.parse(str(abc_path), format="abc")
    mf = midi.translate.music21ObjectToMidiFile(score)
    mf.open(str(midi_path), "wb")
    mf.write()
    mf.close()


def midi_to_wav_with_fluidsynth(midi_path: Path, wav_path: Path, soundfont_path: Path) -> bool:
    """
    Use fluidsynth CLI to render MIDI -> WAV.
    Command:
      fluidsynth -ni <soundfont.sf2> <midifile.mid> -F <out.wav> -r 44100
    Returns True on success.
    """
    if not soundfont_path.exists():
        return False
    cmd = [
        "fluidsynth",
        "-ni",
        str(soundfont_path),
        str(midi_path),
        "-F",
        str(wav_path),
        "-r",
        "44100",
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return wav_path.exists()
    except Exception as e:
        print("fluidsynth failed:", e)
        return False


def midi_to_wav_with_ffmpeg(midi_path: Path, wav_path: Path) -> bool:
    """
    Try ffmpeg to convert MIDI->WAV.
    This sometimes requires timidity or a configured ffmpeg able to render MIDI.
    """
    cmd = ["ffmpeg", "-y", "-i", str(midi_path), str(wav_path)]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return wav_path.exists()
    except Exception as e:
        print("ffmpeg MIDI->WAV failed:", e)
        return False


@app.get("/list")
def list_tunes():
    """
    Return list of available tunes with IDs, titles and original audio URLs.
    """
    host_prefix = ""  # frontend will call relative /static/ URLs; keep empty for same origin
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
    """
    Full pipeline:
    - read tunes/<tune>.abc
    - send to HF Space
    - receive generated abc
    - write generated abc to GEN_DIR
    - convert generated abc -> midi -> wav
    - return generated wav (FileResponse)
    """
    t = find_tune_entry(tune_id)
    if not t:
        raise HTTPException(status_code=404, detail="Tune not found")

    abc_path = TUNES_DIR / t["abc"]
    if not abc_path.exists():
        raise HTTPException(status_code=404, detail="ABC file missing")

    with open(abc_path, "r", encoding="utf-8") as f:
        abc_text = f.read()

    # Call HF Space
    try:
        generated_abc = call_hf_space(abc_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hugging Face Space call failed: {e}")

    # Save generated abc
    uid = uuid.uuid4().hex
    gen_abc_path = GEN_DIR / f"{tune_id}_{uid}.abc"
    gen_midi_path = GEN_DIR / f"{tune_id}_{uid}.mid"
    gen_wav_path = GEN_DIR / f"{tune_id}_{uid}.wav"

    with open(gen_abc_path, "w", encoding="utf-8") as f:
        f.write(generated_abc)

    # ABC -> MIDI
    try:
        abc_to_midi(gen_abc_path, gen_midi_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ABC->MIDI failed: {e}")

    # MIDI -> WAV: try fluidsynth (preferred) then ffmpeg fallback
    ok = False
    if SOUNDFONT_PATH.exists():
        ok = midi_to_wav_with_fluidsynth(gen_midi_path, gen_wav_path, SOUNDFONT_PATH)
    if not ok:
        ok = midi_to_wav_with_ffmpeg(gen_midi_path, gen_wav_path)

    if not ok or not gen_wav_path.exists():
        raise HTTPException(status_code=500, detail="MIDI->WAV synthesis failed (need fluidsynth or ffmpeg support)")

    # Return generated wav
    return FileResponse(str(gen_wav_path), media_type="audio/wav", filename=gen_wav_path.name)
