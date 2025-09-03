// script.js
// Show original 10s audio + generate button for each tune.

// 🔗 Replace with your Render backend URL
const API_BASE = "https://musicgen-rnn.onrender.com";

const grid = document.getElementById("grid");
const status = document.getElementById("status");

function setStatus(text) {
  status.innerText = text || "";
}

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
        <button class="gen-btn" data-id="${t.id}">Generate from this audio</button>
      </div>
      <div class="generated-output" id="gen-output-${t.id}"></div>
    `;

    // add button event
    const btn = card.querySelector(".gen-btn");
    btn.onclick = () => generateTune(t.id, btn);

    grid.appendChild(card);
  });
}

// Call backend to generate continuation
async function generateTune(tuneId, btn) {
  btn.disabled = true;
  btn.innerText = "Generating…";

  const outputDiv = document.getElementById(`gen-output-${tuneId}`);
  window.showLoadingAnimation(outputDiv);
  setStatus("Sending ABC to model and synthesizing audio (this may take a few seconds)...");

  try {
    const res = await fetch(`${API_BASE}/generate/${tuneId}`);
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(`Server error: ${txt}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);

    outputDiv.innerHTML = `<audio controls autoplay src="${url}"></audio>`;

    // visual pulse animation
    anime({
      targets: outputDiv,
      scale: [1, 1.03, 1],
      duration: 700,
      easing: "easeOutElastic(1, .6)",
    });

    setStatus("Generated audio ready.");
  } catch (e) {
    setStatus("Error generating audio: " + e.message);
    outputDiv.innerHTML = `<div class="sub">Generation failed</div>`;
  } finally {
    btn.disabled = false;
    btn.innerText = "Generate from this audio";
  }
}

// start
fetchTuneList();
