// script.js
// Fetch tune list, render cards, and perform generate/original playback.

const grid = document.getElementById("grid");
const status = document.getElementById("status");
const origPlayerDiv = document.getElementById("orig-player");
const genPlayerDiv = document.getElementById("gen-player");

function setStatus(text) {
  status.innerText = text || "";
}

async function fetchTuneList() {
  setStatus("Loading tunes...");
  try {
    const res = await fetch("/list");
    const tunes = await res.json();
    renderGrid(tunes);
    setStatus("");
  } catch (e) {
    setStatus("Failed to load tunes: " + e.message);
  }
}

function renderGrid(tunes) {
  grid.innerHTML = "";
  tunes.forEach((t) => {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `<div class="title">${t.title}</div><div class="sub">ID: ${t.id}</div>`;
    card.onclick = () => onSelectTune(t);
    grid.appendChild(card);
  });
}

function onSelectTune(tune) {
  // small animation using anime.js
  anime({
    targets: ".card",
    scale: [1, 0.98],
    duration: 200,
    easing: "easeInOutQuad",
  });
  // highlight selected card visually
  anime({
    targets: event.currentTarget || event.target,
    scale: [1, 1.03, 1],
    duration: 650,
    easing: "easeOutElastic(1, .6)",
  });

  // show original audio if available
  if (tune.orig_audio_url) {
    origPlayerDiv.innerHTML = `<audio controls src="${tune.orig_audio_url}"></audio>`;
  } else {
    origPlayerDiv.innerHTML = "<div class='sub'>Original audio not available</div>";
  }

  // clear generated area
  genPlayerDiv.innerHTML = "<div class='sub'>Click Generate to produce continuation</div>";

  // show generate button
  setStatus("");
  showGenerateButton(tune.id);
}

function showGenerateButton(tuneId) {
  setStatus("");
  const btn = document.createElement("button");
  btn.innerText = "Generate continuation";
  btn.style.padding = "10px 14px";
  btn.style.borderRadius = "8px";
  btn.style.border = "none";
  btn.style.cursor = "pointer";
  btn.onclick = () => generateTune(tuneId, btn);
  genPlayerDiv.innerHTML = "";
  genPlayerDiv.appendChild(btn);
}

async function generateTune(tuneId, btn) {
  btn.disabled = true;
  btn.innerText = "Generating…";
  setStatus("Sending ABC to model and synthesizing audio (this may take a few seconds)...");
  try {
    const res = await fetch(`/generate/${tuneId}`);
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(`Server error: ${txt}`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    genPlayerDiv.innerHTML = `<audio controls autoplay src="${url}"></audio>`;

    // small visual pulse
    anime({
      targets: genPlayerDiv,
      scale: [1, 1.03, 1],
      duration: 700,
      easing: "easeOutElastic(1, .6)",
    });

    setStatus("Generated audio ready.");
  } catch (e) {
    setStatus("Error generating audio: " + e.message);
    genPlayerDiv.innerHTML = `<div class="sub">Generation failed</div>`;
  } finally {
    btn.disabled = false;
    btn.innerText = "Generate continuation";
  }
}

// start
fetchTuneList();
