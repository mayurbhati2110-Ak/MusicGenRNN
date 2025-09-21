// script.js
const API_BASE = "https://musicgen-rnn.onrender.com";

const grid = document.getElementById("grid");
const status = document.getElementById("status");

function setStatus(text) {
  status.innerText = text || "";
}

// Create full-screen popup container for generated audio
let popupContainer = document.createElement("div");
popupContainer.id = "audio-popup";
popupContainer.style.cssText = `
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 80%;
  height: 80%;
  background: #1c1c1c;
  color: #fff;
  padding: 24px;
  border-radius: 16px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.7);
  z-index: 9999;
  display: none;
  flex-direction: column;
  justify-content: center;
  align-items: center;
`;
document.body.appendChild(popupContainer);

// Overlay background
let overlay = document.createElement("div");
overlay.id = "audio-overlay";
overlay.style.cssText = `
  position: fixed;
  top: 0; left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0,0,0,0.6);
  z-index: 9998;
  display: none;
`;
document.body.appendChild(overlay);

// Fetch list of tunes
async function fetchTuneList() {
  setStatus("Loading tunes...");
  try {
    const res = await fetch(`${API_BASE}/list`);
    if (!res.ok) throw new Error(await res.text());
    const tunes = await res.json();
    renderGrid(tunes);
    setStatus("");
  } catch (e) {
    setStatus("Failed to load tunes: " + e.message);
  }
}

// Render cards with audio + generate button
function renderGrid(tunes) {
  grid.innerHTML = "";
  tunes.forEach((t) => {
    const card = document.createElement("div");
    card.className = "card";

    let audioHtml = "";
    if (t.orig_audio_url) {
      audioHtml = `<audio controls src="${API_BASE}${t.orig_audio_url}"></audio>`;
    } else {
      audioHtml = `<div class="sub">Original audio not available</div>`;
    }

    card.innerHTML = `
      <div class="title">${t.title}</div>
      <div class="sub">ID: ${t.id}</div>
      ${audioHtml}
      <div class="gen-btn-container">
        <button class="gen-btn" data-id="${t.id}">Generate AI Continuation</button>
      </div>
    `;

    const btn = card.querySelector(".gen-btn");
    btn.onclick = () => generateTunePopup(t.id, btn);

    grid.appendChild(card);
  });
}

// Generate AI audio and show in full-screen popup
async function generateTunePopup(tuneId, btn) {
  btn.disabled = true;
  btn.innerText = "Generating…";

  setStatus("Sending ABC to model and synthesizing audio (this may take a few seconds)...");

  try {
    const res = await fetch(`${API_BASE}/generate/${tuneId}`);
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(`Server error: ${txt}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);

    overlay.style.display = "block";
    popupContainer.style.display = "flex";
    popupContainer.innerHTML = `
      <div style="margin-bottom: 16px; font-size: 1.5rem; font-weight:bold;">Generated Audio</div>
      <audio id="popup-audio" controls autoplay style="
        width: 100%;
        height: 70%;
        background: #333;
        border-radius: 12px;
        outline: none;
      " src="${url}"></audio>
      <button id="close-popup" style="
        margin-top: 24px;
        background: #ff7f50;
        border: none;
        padding: 12px 24px;
        color: #fff;
        border-radius: 8px;
        cursor: pointer;
        font-size: 1rem;
      ">Close</button>
    `;

    const audioEl = document.getElementById("popup-audio");

    // Close actions
    document.getElementById("close-popup").onclick = () => {
      audioEl.pause();
      popupContainer.style.display = "none";
      overlay.style.display = "none";
      popupContainer.innerHTML = "";
    };

    overlay.onclick = () => {
      audioEl.pause();
      popupContainer.style.display = "none";
      overlay.style.display = "none";
      popupContainer.innerHTML = "";
    };

    setStatus("Generated audio ready.");
  } catch (e) {
    setStatus("Error generating audio: " + e.message);
  } finally {
    btn.disabled = false;
    btn.innerText = "Generate AI Continuation";
  }
}

// Start
fetchTuneList();
