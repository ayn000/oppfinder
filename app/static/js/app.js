/* OppFinder - front vanilla JS (aucune dépendance, aucun build) */
"use strict";

const state = {
  user: null,
  alerts: [],
  currentAlertId: null,
  jobs: [],
  providers: [],
  zones: [],
  chatEnabled: false,
  editingAlertId: null,
  editingAlert: null,
  chat: { job: null, messages: [], streaming: false },
};

const $ = (sel) => document.querySelector(sel);

/* ---------------- API helper ---------------- */
async function api(path, options = {}) {
  const opts = { credentials: "same-origin", headers: {}, ...options };
  if (opts.body !== undefined && typeof opts.body !== "string") {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  const res = await fetch(path, opts);
  if (res.status === 401 && path !== "/api/auth/login") {
    showLogin();
    throw new Error("Non authentifié");
  }
  if (!res.ok) {
    let detail = `Erreur ${res.status}`;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

/* ---------------- utils ---------------- */
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

function mdLite(text) {
  // rendu markdown minimal et sûr : échappe tout, puis gras / italique / titres / listes
  let html = esc(text);
  html = html.replace(/^### (.*)$/gm, "<strong>$1</strong>");
  html = html.replace(/^## (.*)$/gm, "<strong>$1</strong>");
  html = html.replace(/^# (.*)$/gm, "<strong>$1</strong>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/(^|\s)\*([^*\n]+)\*(?=\s|$|[.,;:!?])/g, "$1<em>$2</em>");
  html = html.replace(/^[-•] /gm, "• ");
  return html;
}

function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  if (isNaN(d)) return "";
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" });
}

function fmtDateTime(iso) {
  if (!iso) return "jamais";
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  if (isNaN(d)) return "jamais";
  return d.toLocaleDateString("fr-FR", { day: "numeric", month: "short" }) +
    " à " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

const CONTRACT_LABELS = { cdi: "CDI", cdd: "CDD", stage: "Stage", alternance: "Alternance" };

function zoneLabel(code) {
  const z = state.zones.find((z) => z.code === code);
  return z ? z.label : code;
}
const SOURCE_LABELS = {
  france_travail: "France Travail",
  adzuna: "Adzuna",
  remotive: "Remotive",
  arbeitnow: "Arbeitnow",
};

/* ---------------- vues ---------------- */
function showLogin() {
  $("#view-app").classList.add("hidden");
  $("#view-login").classList.remove("hidden");
  $("#login-username").focus();
}

async function showApp() {
  $("#view-login").classList.add("hidden");
  $("#view-app").classList.remove("hidden");
  $("#me-name").textContent = state.user.display_name || state.user.username;
  const [providerInfo, chatStatus] = await Promise.all([
    api("/api/providers"),
    api("/api/chat/status"),
  ]);
  state.providers = providerInfo.providers;
  state.zones = providerInfo.zones;
  state.chatEnabled = chatStatus.enabled;
  await loadAlerts();
}

/* ---------------- alertes ---------------- */
async function loadAlerts(selectId = null) {
  state.alerts = await api("/api/alerts");
  renderAlertList();
  const target = selectId ?? state.currentAlertId ?? (state.alerts[0] && state.alerts[0].id);
  if (target && state.alerts.some((a) => a.id === target)) {
    await selectAlert(target);
  } else {
    state.currentAlertId = null;
    $("#alert-view").classList.add("hidden");
    $("#empty-state").classList.remove("hidden");
  }
}

function renderAlertList() {
  const nav = $("#alert-list");
  nav.innerHTML = "";
  for (const a of state.alerts) {
    const div = document.createElement("div");
    div.className = "alert-item" + (a.id === state.currentAlertId ? " active" : "") + (a.is_active ? "" : " inactive");
    div.innerHTML = `
      <div class="alert-name"><span>${esc(a.name)}</span><span class="count">${a.job_count}</span></div>
      <div class="alert-kw">${esc(a.keywords.join(", "))}</div>`;
    div.addEventListener("click", () => selectAlert(a.id));
    nav.appendChild(div);
  }
}

async function selectAlert(id) {
  state.currentAlertId = id;
  renderAlertList();
  const alert = state.alerts.find((a) => a.id === id);
  if (!alert) return;
  $("#empty-state").classList.add("hidden");
  $("#alert-view").classList.remove("hidden");
  $("#alert-title").textContent = alert.name;

  const chips = $("#alert-chips");
  chips.innerHTML = alert.keywords.map((k) => `<span class="chip">${esc(k)}</span>`).join("");
  if (alert.contract_type) chips.innerHTML += `<span class="chip neutral">${CONTRACT_LABELS[alert.contract_type] || alert.contract_type}</span>`;
  if (alert.zone && alert.zone !== "fr") chips.innerHTML += `<span class="chip neutral">🌍 ${esc(zoneLabel(alert.zone))}</span>`;
  if (alert.location) chips.innerHTML += `<span class="chip neutral">📍 ${esc(alert.location)}</span>`;

  const zone = alert.zone || "fr";
  const srcNames = (alert.sources ||
    state.providers
      .filter((p) => p.available && (!p.zones || p.zones.includes(zone)))
      .map((p) => p.name))
    .map((s) => SOURCE_LABELS[s] || s).join(", ");
  $("#alert-meta").textContent =
    `Dernière mise à jour : ${fmtDateTime(alert.last_refreshed_at)} | Sources : ${srcNames}` +
    (alert.is_active ? "" : " | alerte en pause");

  await loadJobs();
}

/* ---------------- annonces ---------------- */
async function loadJobs() {
  if (!state.currentAlertId) return;
  const includeHidden = $("#filter-hidden").checked;
  state.jobs = await api(`/api/alerts/${state.currentAlertId}/jobs?include_hidden=${includeHidden}`);
  renderJobs();
}

function renderJobs() {
  const list = $("#job-list");
  const search = $("#filter-search").value.trim().toLowerCase();
  const favOnly = $("#filter-fav").checked;

  let jobs = state.jobs;
  if (favOnly) jobs = jobs.filter((j) => j.is_favorite);
  if (search) {
    jobs = jobs.filter((j) =>
      (j.title + " " + j.company + " " + j.location).toLowerCase().includes(search));
  }

  $("#job-count").textContent = `${jobs.length} annonce${jobs.length > 1 ? "s" : ""}`;
  list.innerHTML = "";

  if (!jobs.length) {
    list.innerHTML = `<div class="list-empty">Aucune annonce pour le moment.<br>
      Les annonces sont mises à jour automatiquement toutes les 24 h. Tu peux aussi cliquer sur "Rafraîchir".</div>`;
    return;
  }

  for (const j of jobs) {
    const scoreClass = j.score >= 70 ? "high" : j.score >= 40 ? "mid" : "";
    const card = document.createElement("div");
    card.className = "job-card" + (j.is_hidden ? " hidden-job" : "");
    card.innerHTML = `
      <div class="score ${scoreClass}" title="Correspondance avec tes mots-clés">${Math.round(j.score)}</div>
      <div class="job-main">
        <div class="job-title"><a href="${esc(j.url)}" target="_blank" rel="noopener noreferrer">${esc(j.title)}</a></div>
        <div class="job-sub">
          ${j.company ? `<span>🏢 ${esc(j.company)}</span>` : ""}
          ${j.location ? `<span>📍 ${esc(j.location)}</span>` : ""}
          <span class="tag">${esc(SOURCE_LABELS[j.source] || j.source)}</span>
          ${j.contract_type ? `<span class="tag contract">${esc(CONTRACT_LABELS[j.contract_type] || j.contract_type)}</span>` : ""}
          ${j.published_at ? `<span>${fmtDate(j.published_at)}</span>` : ""}
        </div>
      </div>
      <div class="job-actions">
        ${state.chatEnabled ? `<button class="icon-btn ai" data-act="chat" title="Conseils IA sur cette offre">IA</button>` : ""}
        <button class="icon-btn ${j.is_favorite ? "fav-on" : ""}" data-act="fav" title="Favori">${j.is_favorite ? "★" : "☆"}</button>
        <button class="icon-btn" data-act="hide" title="${j.is_hidden ? "Ré-afficher" : "Masquer"}">${j.is_hidden ? "👁" : "✕"}</button>
      </div>`;
    card.querySelectorAll("[data-act]").forEach((btn) => {
      btn.addEventListener("click", () => onJobAction(btn.dataset.act, j));
    });
    list.appendChild(card);
  }
}

async function onJobAction(action, job) {
  if (action === "chat") return openChat(job);
  const path = action === "fav" ? `/api/jobs/${job.id}/favorite` : `/api/jobs/${job.id}/hide`;
  const updated = await api(path, { method: "POST" });
  const idx = state.jobs.findIndex((j) => j.id === job.id);
  if (idx >= 0) state.jobs[idx] = updated;
  if (action === "hide" && updated.is_hidden && !$("#filter-hidden").checked) {
    state.jobs.splice(idx, 1);
  }
  renderJobs();
}

/* ---------------- chat IA ---------------- */
function openChat(job) {
  state.chat = { job, messages: [], streaming: false };
  $("#chat-job-title").textContent = job.title + (job.company ? " - " + job.company : "");
  $("#chat-messages").innerHTML = `<div class="chat-hint">Demande-moi une analyse de l'offre, des conseils
    pour adapter ton CV, une aide pour la lettre de motivation ou les questions d'entretien probables.</div>`;
  $("#chat-panel").classList.remove("hidden");
  $("#chat-text").focus();
}

function closeChat() {
  $("#chat-panel").classList.add("hidden");
  state.chat = { job: null, messages: [], streaming: false };
}

function appendMsg(role, content) {
  const div = document.createElement("div");
  div.className = `msg ${role}`;
  div.innerHTML = mdLite(content);
  $("#chat-messages").appendChild(div);
  div.scrollIntoView({ block: "end" });
  return div;
}

async function sendChat() {
  const textarea = $("#chat-text");
  const content = textarea.value.trim();
  if (!content || state.chat.streaming || !state.chat.job) return;

  const hint = document.querySelector(".chat-hint");
  if (hint) hint.remove();

  textarea.value = "";
  state.chat.messages.push({ role: "user", content });
  appendMsg("user", content);

  state.chat.streaming = true;
  $("#chat-send").disabled = true;
  const bubble = appendMsg("assistant", "...");

  let full = "";
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: state.chat.job.id, messages: state.chat.messages }),
    });
    if (!res.ok) {
      let detail = `Erreur ${res.status}`;
      try { detail = (await res.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      full += decoder.decode(value, { stream: true });
      bubble.innerHTML = mdLite(full);
      bubble.scrollIntoView({ block: "end" });
    }
    state.chat.messages.push({ role: "assistant", content: full || "(réponse vide)" });
  } catch (err) {
    bubble.innerHTML = mdLite(`⚠️ ${err.message}`);
    state.chat.messages.pop(); // retire le message user pour pouvoir réessayer
  } finally {
    state.chat.streaming = false;
    $("#chat-send").disabled = false;
    textarea.focus();
  }
}

/* ---------------- modale alerte ---------------- */
function renderSourceOptions(zone, alert = null) {
  const box = $("#f-sources");
  box.innerHTML = "";
  for (const p of state.providers) {
    const zoneOk = !p.zones || p.zones.includes(zone);
    const usable = p.available && zoneOk;
    const checked = usable && (
      alert
        ? (alert.sources === null ? true : alert.sources.includes(p.name))
        : true
    );
    let note = "";
    if (!p.available) note = `<span class="unavailable">(clé API non configurée, voir tuto.md)</span>`;
    else if (!zoneOk) note = `<span class="unavailable">(non disponible pour cette zone)</span>`;
    box.insertAdjacentHTML("beforeend", `
      <label class="source-opt">
        <input type="checkbox" name="source" value="${esc(p.name)}"
          ${checked ? "checked" : ""} ${usable ? "" : "disabled"}>
        ${esc(p.label)} ${note}
      </label>`);
  }
}

function openModal(alert = null) {
  state.editingAlertId = alert ? alert.id : null;
  state.editingAlert = alert;
  $("#modal-title").textContent = alert ? "Modifier l'alerte" : "Nouvelle alerte";
  $("#f-name").value = alert ? alert.name : "";
  $("#f-keywords").value = alert ? alert.keywords.join(", ") : "";
  $("#f-location").value = alert ? alert.location : "";
  $("#f-contract").value = alert ? alert.contract_type : "";
  $("#form-error").classList.add("hidden");

  const zoneSelect = $("#f-zone");
  zoneSelect.innerHTML = state.zones
    .map((z) => `<option value="${esc(z.code)}">${esc(z.label)}</option>`)
    .join("");
  zoneSelect.value = alert && alert.zone ? alert.zone : "fr";

  renderSourceOptions(zoneSelect.value, alert);
  $("#modal-backdrop").classList.remove("hidden");
  $("#f-name").focus();
}

function closeModal() {
  $("#modal-backdrop").classList.add("hidden");
  state.editingAlertId = null;
  state.editingAlert = null;
}

async function saveAlert(e) {
  e.preventDefault();
  const keywords = $("#f-keywords").value.split(",").map((k) => k.trim()).filter(Boolean);
  const sources = [...document.querySelectorAll('input[name="source"]:checked')].map((i) => i.value);
  const payload = {
    name: $("#f-name").value.trim(),
    keywords,
    location: $("#f-location").value.trim(),
    contract_type: $("#f-contract").value,
    zone: $("#f-zone").value || "fr",
    sources: sources.length ? sources : null,
    is_active: true,
  };
  const errBox = $("#form-error");
  if (!payload.name || !keywords.length) {
    errBox.textContent = "Un nom et au moins un mot-clé sont requis.";
    errBox.classList.remove("hidden");
    return;
  }
  const btn = $("#btn-save-alert");
  btn.disabled = true;
  try {
    let saved;
    if (state.editingAlertId) {
      saved = await api(`/api/alerts/${state.editingAlertId}`, { method: "PUT", body: payload });
    } else {
      saved = await api("/api/alerts", { method: "POST", body: payload });
    }
    closeModal();
    await loadAlerts(saved.id);
  } catch (err) {
    errBox.textContent = err.message;
    errBox.classList.remove("hidden");
  } finally {
    btn.disabled = false;
  }
}

/* ---------------- actions entête ---------------- */
async function refreshCurrentAlert() {
  if (!state.currentAlertId) return;
  const btn = $("#btn-refresh");
  btn.disabled = true;
  btn.innerHTML = `<span class="spin">⟳</span> En cours...`;
  try {
    await api(`/api/alerts/${state.currentAlertId}/refresh`, { method: "POST" });
    await loadAlerts(state.currentAlertId);
  } catch (err) {
    window.alert("Échec du rafraîchissement : " + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = "⟳ Rafraîchir";
  }
}

async function deleteCurrentAlert() {
  const alert = state.alerts.find((a) => a.id === state.currentAlertId);
  if (!alert) return;
  if (!window.confirm(`Supprimer l'alerte "${alert.name}" et toutes ses annonces ?`)) return;
  await api(`/api/alerts/${alert.id}`, { method: "DELETE" });
  state.currentAlertId = null;
  closeChat();
  await loadAlerts();
}

/* ---------------- init ---------------- */
async function init() {
  // login
  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const errBox = $("#login-error");
    errBox.classList.add("hidden");
    $("#login-submit").disabled = true;
    try {
      state.user = await api("/api/auth/login", {
        method: "POST",
        body: {
          username: $("#login-username").value,
          password: $("#login-password").value,
        },
      });
      $("#login-password").value = "";
      await showApp();
    } catch (err) {
      errBox.textContent = err.message;
      errBox.classList.remove("hidden");
    } finally {
      $("#login-submit").disabled = false;
    }
  });

  $("#btn-logout").addEventListener("click", async () => {
    await api("/api/auth/logout", { method: "POST" });
    state.user = null;
    showLogin();
  });

  $("#btn-new-alert").addEventListener("click", () => openModal());
  $("#btn-empty-new").addEventListener("click", () => openModal());
  $("#btn-edit-alert").addEventListener("click", () => {
    const alert = state.alerts.find((a) => a.id === state.currentAlertId);
    if (alert) openModal(alert);
  });
  $("#btn-delete-alert").addEventListener("click", deleteCurrentAlert);
  $("#btn-refresh").addEventListener("click", refreshCurrentAlert);
  $("#alert-form").addEventListener("submit", saveAlert);
  $("#f-zone").addEventListener("change", () =>
    renderSourceOptions($("#f-zone").value, state.editingAlert));
  $("#btn-cancel-modal").addEventListener("click", closeModal);
  $("#modal-backdrop").addEventListener("click", (e) => {
    if (e.target === $("#modal-backdrop")) closeModal();
  });

  $("#filter-search").addEventListener("input", renderJobs);
  $("#filter-fav").addEventListener("change", renderJobs);
  $("#filter-hidden").addEventListener("change", loadJobs);

  $("#btn-close-chat").addEventListener("click", closeChat);
  $("#chat-form").addEventListener("submit", (e) => { e.preventDefault(); sendChat(); });
  $("#chat-text").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });

  // session existante ?
  try {
    state.user = await api("/api/auth/me");
    await showApp();
  } catch (_) {
    showLogin();
  }
}

document.addEventListener("DOMContentLoaded", init);
