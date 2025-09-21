// script.js
const API_BASE = "https://musicgen-rnn.onrender.com";

const grid = document.getElementById("grid");
const status = document.getElementById("status");

function setStatus(text) {
  status.innerText = text || "";
}

// Create popup container for generated audio
let popupContainer = document.createElement("div");
popupContainer.id = "audio-popup";
popupContainer.style.cssText = `
  position: fixed;
  bottom: 20px;
  right: 20px;
  background: #1c1c1c;
  color: #fff;
  padding: 16px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.5);
  z-index: 9999;
  display: none;
`;
document.body.appendChild(popupContainer);

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

// Generate AI audio and show in popup player
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

    // Show popup player
    popupContainer.innerHTML = `
      <div style="margin-bottom: 8px; font-weight:bold;">Generated Audio</div>
      <audio controls autoplay src="${url}"></audio>
      <button id="close-popup" style="
        margin-top: 8px;
        background: #ff7f50;
        border: none;
        padding: 6px 12px;
        color: #fff;
        border-radius: 6px;
        cursor: pointer;
      ">Close</button>
    `;
    popupContainer.style.display = "block";

    // Close button event
    document.getElementById("close-popup").onclick = () => {
      popupContainer.style.display = "none";
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

// start
fetchTuneList();

// Optional: Loading animation
window.showLoadingAnimation = function (container) {
  container.innerHTML = `
    <div class="loading">
      <span class="note">🎵</span>
      <span class="note">🎶</span>
      <span class="note">🎼</span>
    </div>
  `;

  anime({
    targets: container.querySelectorAll(".note"),
    translateY: [-5, 5],
    direction: "alternate",
    loop: true,
    easing: "easeInOutSine",
    duration: 600,
    delay: anime.stagger(200),
  });
};
