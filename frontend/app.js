const API_BASE = window.location.origin;
// A page owns its conversation; separate tabs and reloads start fresh.
let conversationId = null;
let chatInFlight = false;
// Keep citations with the displayed answer, independent of later server lookups.
let lastCitations = [];

function conversationHeaders() {
  return conversationId ? { "X-Conversation-ID": conversationId } : {};
}

const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const chatMessages = document.getElementById("chat-messages");
const rebuildBtn = document.getElementById("rebuild-btn");
const sourcesList = document.getElementById("sources-list");
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
  if (rebuildBtn) {
    rebuildBtn.disabled = !enabled;
  }
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

function showLoadingMessage(text = "Antwort wird gesucht...") {
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
  if (typeof htmlContent === "string") {
    dialogBody.innerHTML = htmlContent;
  } else {
    dialogBody.replaceChildren(htmlContent);
  }
  dialogBody.scrollTop = 0;

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
    throw new Error("Der Chat ist momentan nicht erreichbar.");
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
      `Anfrage fehlgeschlagen (${response.status})`;

    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return data;
}

async function checkBackend() {
  try {
    await safeFetch(`${API_BASE}/health`);

    setBackendStatus("status-ok", "Chat ist bereit.");
    setChatEnabled(true);
    setActionButtonsEnabled(true);

    return true;
  } catch (error) {
    setBackendStatus(
      "status-error",
      "Der Chat ist momentan nicht erreichbar. Bitte versuche es später erneut."
    );

    setChatEnabled(false);
    setActionButtonsEnabled(false);

    sourcesList.innerHTML =
      `<p class="muted sources-empty">Lehrvideoquellen können derzeit nicht angezeigt werden.</p>`;

    return false;
  }
}

function createSourceDetail(source) {
  const card = document.createElement("article");
  card.className = "source-card";

  const area = document.createElement("p");
  area.className = "source-area";
  const areaNumber = source.subject_area_number ? ` ${source.subject_area_number}` : "";
  area.textContent = `Fachbereich${areaNumber} · ${source.subject_area_name || "Nicht zugeordnet"}`;

  const module = document.createElement("h4");
  module.className = "source-module";
  module.textContent = `Modul ${source.module_number} · ${source.module_name}`;

  const video = document.createElement("p");
  video.className = "source-video";
  video.textContent = `Video ${source.video_number} · ${source.video_name}`;

  const time = document.createElement("p");
  time.className = "source-time";
  time.textContent = `Zeitstelle: ${source.time_range || "Nicht angegeben"}`;

  const quote = document.createElement("blockquote");
  quote.className = "source-quote";
  quote.textContent = source.text_preview || source.text || "";

  card.append(area, module, video, time, quote);
  return card;
}

function createSourcesList(sources) {
  const list = document.createDocumentFragment();

  for (const source of sources) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "source-card";
    card.style.width = "100%";
    card.style.textAlign = "left";
    card.style.cursor = "pointer";
    card.style.color = "inherit";
    card.setAttribute("aria-label", `Lehrvideoquelle öffnen: Modul ${source.module_number}, Video ${source.video_number}`);

    const area = document.createElement("p");
    area.className = "source-area";
    const areaNumber = source.subject_area_number ? ` ${source.subject_area_number}` : "";
    area.textContent = `Fachbereich${areaNumber} · ${source.subject_area_name || "Nicht zugeordnet"}`;

    const module = document.createElement("h4");
    module.className = "source-module";
    module.textContent = `Modul ${source.module_number} · ${source.module_name}`;

    const video = document.createElement("p");
    video.className = "source-video";
    video.textContent = `Video ${source.video_number} · ${source.video_name}`;

    card.append(area, module, video);
    card.addEventListener("click", () => {
      openDialog("Lehrvideoquelle", createSourceDetail(source));
    });

    list.appendChild(card);
  }

  return list;
}

function renderSources() {
  if (lastCitations === null) {
    sourcesList.innerHTML =
      `<p class="muted sources-empty">Die Lehrvideoquellen konnten dieser Antwort nicht zugeordnet werden.</p>`;
    return;
  }

  if (lastCitations.length === 0) {
    sourcesList.innerHTML =
      `<p class="muted sources-empty">Für die letzte Antwort wurden keine Lehrvideoquellen angegeben.</p>`;
    return;
  }

  sourcesList.replaceChildren(createSourcesList(lastCitations));
  sourcesList.scrollTop = 0;
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
  } catch (error) {
    openDialog("Fehler", `<div>${escapeHtml(error.message)}</div>`);
  } finally {
    setActionButtonsEnabled(true);
  }
}

async function sendMessage(message) {
  if (chatInFlight) return;
  chatInFlight = true;
  addMessage("user", message);
  chatInput.value = "";
  setChatEnabled(false);
  showLoadingMessage();

  try {
    const data = await safeFetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...conversationHeaders(),
      },
      body: JSON.stringify({ message }),
    });

    conversationId = data.conversation_id;
    lastCitations = Array.isArray(data.citations) ? data.citations : null;
    removeLoadingMessage();
    addMessage("bot", data.answer || "Es wurde keine Antwort geliefert.");
    renderSources();
  } catch (error) {
    if (error.status === 404 && conversationId) {
      conversationId = null;
      lastCitations = [];
      renderSources();
      error.message = "Deine Sitzung ist abgelaufen. Die nächste Nachricht beginnt einen neuen Chat ohne den bisherigen Kontext.";
    }
    removeLoadingMessage();
    addMessage(
      "bot",
      error.message || "Die Anfrage konnte nicht verarbeitet werden."
    );
  } finally {
    chatInFlight = false;
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

if (rebuildBtn) {
  rebuildBtn.addEventListener("click", rebuildIndex);
}

async function init() {
  setChatEnabled(false);
  setActionButtonsEnabled(false);

  const backendAvailable = await checkBackend();

  if (backendAvailable) {
    chatInput.focus();
  }
}

init();
