const API_BASE = window.location.origin;

const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const chatMessages = document.getElementById("chat-messages");

const reloadVideosBtn = document.getElementById("reload-videos-btn");
const showSourcesBtn = document.getElementById("show-sources-btn");
const rebuildBtn = document.getElementById("rebuild-btn");

const videosList = document.getElementById("videos-list");
const backendStatus = document.getElementById("backend-status");

const infoDialog = document.getElementById("info-dialog");
const dialogTitle = document.getElementById("dialog-title");
const dialogBody = document.getElementById("dialog-body");
const closeDialogBtn = document.getElementById("close-dialog-btn");

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function setBackendStatus(kind, text) {
  backendStatus.textContent = text;
  backendStatus.className = `status-box ${kind}`;
}

function setChatEnabled(enabled) {
  chatInput.disabled = !enabled;
  sendBtn.disabled = !enabled;
}

function setActionButtonsEnabled(enabled) {
  reloadVideosBtn.disabled = !enabled;
  showSourcesBtn.disabled = !enabled;
  rebuildBtn.disabled = !enabled;
}

function addMessage(role, text) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  wrapper.appendChild(bubble);
  chatMessages.appendChild(wrapper);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showLoadingMessage(text = "Antwort wird geladen...") {
  removeLoadingMessage();

  const wrapper = document.createElement("div");
  wrapper.className = "message bot";
  wrapper.id = "loading-message";

  const bubble = document.createElement("div");
  bubble.className = "bubble loading";
  bubble.textContent = text;

  wrapper.appendChild(bubble);
  chatMessages.appendChild(wrapper);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeLoadingMessage() {
  const loading = document.getElementById("loading-message");

  if (loading) {
    loading.remove();
  }
}

function openDialog(title, htmlContent) {
  dialogTitle.textContent = title;
  dialogBody.innerHTML = htmlContent;

  if (typeof infoDialog.showModal === "function") {
    if (!infoDialog.open) {
      infoDialog.showModal();
    }
  } else {
    alert(`${title}\n\n${dialogBody.textContent}`);
  }
}

function closeDialog() {
  if (infoDialog.open) {
    infoDialog.close();
  }
}

async function safeFetch(url, options = {}) {
  let response;

  try {
    response = await fetch(url, options);
  } catch (error) {
    throw new Error("Das Backend ist nicht erreichbar.");
  }

  let data = null;

  try {
    data = await response.json();
  } catch (error) {
    data = null;
  }

  if (!response.ok) {
    const message =
      (data && (data.detail || data.message)) ||
      `HTTP-Fehler ${response.status}`;

    throw new Error(message);
  }

  return data;
}

async function checkBackend() {
  try {
    await safeFetch(`${API_BASE}/health`);

    setBackendStatus("status-ok", "Backend verbunden.");
    setChatEnabled(true);
    setActionButtonsEnabled(true);

    return true;
  } catch (error) {
    setBackendStatus(
      "status-error",
      "Backend nicht erreichbar. Bitte prüfe die Serververbindung."
    );

    setChatEnabled(false);
    setActionButtonsEnabled(false);

    videosList.innerHTML =
      `<p class="muted">Lehrvideos können derzeit nicht geladen werden.</p>`;

    return false;
  }
}

async function loadVideos() {
  videosList.innerHTML = `<p class="muted">Lehrvideos werden geladen...</p>`;

  try {
    const videos = await safeFetch(`${API_BASE}/videos`);

    if (!Array.isArray(videos) || videos.length === 0) {
      videosList.innerHTML = `<p class="muted">Keine Lehrvideos gefunden.</p>`;
      return;
    }

    videosList.innerHTML = "";

    videos.forEach((video) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "video-card";

      card.innerHTML = `
        <strong>
          Modul ${escapeHtml(video.module_number)} - ${escapeHtml(video.module_name)}
        </strong>
        <br>
        <span>
          Video ${escapeHtml(video.video_number)} - ${escapeHtml(video.video_name)}
        </span>
      `;

      card.addEventListener("click", async () => {
        try {
          const detail = await safeFetch(`${API_BASE}/videos/${video.id}`);

          openDialog(
            `Modul ${detail.module_number} - ${detail.module_name} | Video ${detail.video_number} - ${detail.video_name}`,
            `<div>${escapeHtml(detail.content_preview || "")}</div>`
          );
        } catch (error) {
          openDialog("Fehler", `<div>${escapeHtml(error.message)}</div>`);
        }
      });

      videosList.appendChild(card);
    });
  } catch (error) {
    videosList.innerHTML =
      `<p class="muted">Fehler beim Laden der Lehrvideos.</p>`;

    openDialog("Fehler", `<div>${escapeHtml(error.message)}</div>`);
  }
}

async function loadSources() {
  try {
    const sources = await safeFetch(`${API_BASE}/sources`);

    if (!Array.isArray(sources) || sources.length === 0) {
      openDialog(
        "Letzte Quellenstellen",
        "<div>Noch keine Quellenstellen vorhanden.</div>"
      );

      return;
    }

    const html = sources
      .map(
        (source) => `
          <div class="source-card">
            <div class="source-meta">
              Modul ${escapeHtml(source.module_number)} - ${escapeHtml(source.module_name)}
              |
              Video ${escapeHtml(source.video_number)} - ${escapeHtml(source.video_name)}
              |
              ${escapeHtml(source.time_range)}
            </div>

            <div>
              Relevanz: ${escapeHtml(source.score)}
            </div>

            <div style="margin-top: 8px;">
              ${escapeHtml(source.text_preview || "")}
            </div>
          </div>
        `
      )
      .join("");

    openDialog("Letzte Quellenstellen", html);
  } catch (error) {
    openDialog("Fehler", `<div>${escapeHtml(error.message)}</div>`);
  }
}

async function rebuildIndex() {
  const confirmed = window.confirm(
    "Möchtest du die Lehrvideoquellen neu einlesen und den Suchindex neu aufbauen?"
  );

  if (!confirmed) {
    return;
  }

  setActionButtonsEnabled(false);

  try {
    const rebuildToken = window.REBUILD_TOKEN || "";

    if (!rebuildToken) {
      openDialog("Nicht verfügbar", "<div>Der Neuaufbau des Suchindex ist für die öffentliche Version deaktiviert.</div>");
      return;
    }

    const result = await safeFetch(`${API_BASE}/rebuild`, {
      method: "POST",
      headers: {
        "X-Rebuild-Token": rebuildToken,
      },
    });

    openDialog(
      "Neuaufbau",
      `<div>${escapeHtml(result.message || "Neuaufbau abgeschlossen.")}</div>`
    );

    await loadVideos();
  } catch (error) {
    openDialog("Fehler", `<div>${escapeHtml(error.message)}</div>`);
  } finally {
    setActionButtonsEnabled(true);
  }
}

async function sendMessage(message) {
  addMessage("user", message);
  chatInput.value = "";
  setChatEnabled(false);
  showLoadingMessage();

  try {
    const data = await safeFetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message }),
    });

    removeLoadingMessage();
    addMessage("bot", data.answer || "Es wurde keine Antwort geliefert.");
  } catch (error) {
    removeLoadingMessage();
    addMessage(
      "bot",
      error.message || "Die Anfrage konnte nicht verarbeitet werden."
    );
  } finally {
    setChatEnabled(true);
    chatInput.focus();
  }
}

closeDialogBtn.addEventListener("click", closeDialog);

infoDialog.addEventListener("click", (event) => {
  if (event.target === infoDialog) {
    closeDialog();
  }
});

chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const message = chatInput.value.trim();

  if (!message) {
    return;
  }

  await sendMessage(message);
});

reloadVideosBtn.addEventListener("click", loadVideos);
showSourcesBtn.addEventListener("click", loadSources);
rebuildBtn.addEventListener("click", rebuildIndex);

async function init() {
  setChatEnabled(false);
  setActionButtonsEnabled(false);

  const backendAvailable = await checkBackend();

  if (backendAvailable) {
    await loadVideos();
    chatInput.focus();
  }
}

init();
