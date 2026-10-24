const state = { topics: [], settings: { dailyHours: 2 }, currentSection: "overview", editingId: null };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const authScreen = $("#auth-screen");
const appScreen = $("#app-screen");
let toastTimer;

async function api(path, options = {}) {
  const token = sessionStorage.getItem("studyflow_token");
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { "Authorization": `Bearer ${token}` } : {}),
    ...(options.headers || {})
  };
  const response = await fetch(path, {
    credentials: "include",
    headers,
    ...options
  });
  const data = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.error || "Something went wrong. Please try again.");
  return data;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);
}

function setMessage(element, message, success = false) {
  if (!element) return;
  element.textContent = message;
  element.classList.toggle("success", success);
}

function showToast(message, error = false) {
  const toast = $("#toast");
  if (!toast) return;
  toast.textContent = message;
  toast.classList.toggle("error", error);
  toast.classList.add("visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("visible"), 2700);
}

function localDate(date = new Date(), options = { weekday: "short", month: "short", day: "numeric" }) {
  try {
    return new Intl.DateTimeFormat(undefined, options).format(date);
  } catch {
    return String(date);
  }
}

function localISODate(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function deadlineDate(value, options = { month: "short", day: "numeric" }) {
  if (!value) return "—";
  try {
    const d = new Date(`${value}T12:00:00`);
    if (isNaN(d.getTime())) return value;
    return new Intl.DateTimeFormat(undefined, options).format(d);
  } catch {
    return value;
  }
}

function daysUntil(value) {
  if (!value) return 0;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const due = new Date(`${value}T00:00:00`);
  if (isNaN(due.getTime())) return 0;
  return Math.round((due - today) / 86400000);
}

function priorityColor(topic) {
  if (topic.priority === 3) return "#df8c78";
  if (topic.difficulty === 3) return "#8c84dc";
  return "#5bb7a2";
}

function dueText(topic) {
  const days = daysUntil(topic.deadline);
  if (days < 0) return "Past due";
  if (days === 0) return "Due today";
  if (days === 1) return "Due tomorrow";
  return `Due ${deadlineDate(topic.deadline)}`;
}

function switchAuthMode(mode) {
  const registering = mode === "register";
  $("#login-tab").classList.toggle("active", !registering);
  $("#register-tab").classList.toggle("active", registering);
  $("#login-tab").setAttribute("aria-selected", String(!registering));
  $("#register-tab").setAttribute("aria-selected", String(registering));
  $("#auth-title").textContent = registering ? "Make space to focus" : "Welcome back";
  $("#auth-subtitle").textContent = registering ? "Your next chapter starts with a plan." : "Pick up right where you left off.";
  $("#auth-eyebrow").textContent = registering ? "A FRESH START, AT YOUR OWN PACE" : "A LITTLE MORE FOCUS, A LOT LESS STRESS";
  $("#auth-submit span:first-child").textContent = registering ? "Create my account" : "Sign in to Studyflow";
  $("#password").autocomplete = registering ? "new-password" : "current-password";
  $("#password-hint").textContent = registering ? "At least 8 characters" : "";
  setMessage($("#auth-message"), "");
}

function setSection(section) {
  state.currentSection = section;
  const title = section === "topics" ? "My topics" : section === "plan" ? "Study plan" : "Overview";
  $("#breadcrumb-current").textContent = title;
  $$(".view-section").forEach((view) => view.classList.add("hidden"));
  $(`#${section}-section`).classList.remove("hidden");
  $$(".nav-link[data-section]").forEach((link) => {
    const active = link.dataset.section === section;
    link.classList.toggle("active", active);
    if (active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  window.location.hash = section === "overview" ? "overview" : section === "topics" ? "my-topics" : "my-plan";
  if (section === "plan") renderPlan().catch((error) => showToast(error.message, true));
}

async function showApp(email) {
  authScreen.classList.add("hidden");
  appScreen.classList.remove("hidden");
  $("#user-email").textContent = email;
  $("#user-avatar").textContent = (email[0] || "S").toUpperCase();
  $("#today-label").textContent = localDate(new Date(), { weekday: "long", month: "long", day: "numeric" }).toUpperCase();
  setSection("overview");
  try {
    await refreshData();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function refreshData() {
  const [topicData, settingsData] = await Promise.all([api("/api/topics"), api("/api/settings")]);
  state.topics = topicData.topics || [];
  state.settings = settingsData || { dailyHours: 2 };
  renderAll();
}

function renderAll() {
  renderOverview();
  renderTopics();
  $("#hours-per-day").value = state.settings.dailyHours;
  $("#nav-topic-count").textContent = state.topics.filter((topic) => !topic.completed).length;
  if (state.currentSection === "plan") renderPlan().catch((error) => showToast(error.message, true));
}

function renderOverview() {
  const activeTopics = state.topics.filter((topic) => !topic.completed);
  const upcoming = [...activeTopics].sort((a, b) => a.deadline.localeCompare(b.deadline));
  $("#stat-topics").textContent = activeTopics.length;
  $("#stat-hours").textContent = activeTopics.reduce((sum, topic) => sum + Number(topic.estimatedHours || 0), 0).toFixed(1).replace(/\.0$/, "");
  $("#stat-deadline").textContent = upcoming.length ? deadlineDate(upcoming[0].deadline) : "—";
  $("#stat-deadline-caption").textContent = upcoming.length ? `${upcoming[0].subject} · ${dueText(upcoming[0]).toLowerCase()}` : "add a deadline to get started";
  const focusList = $("#focus-list");
  const visible = upcoming.slice(0, 4);
  focusList.innerHTML = visible.length ? visible.map((topic) => `
    <div class="focus-item">
      <i class="focus-indicator" style="background:${priorityColor(topic)}"></i>
      <div class="focus-item-body"><span class="focus-title">${escapeHtml(topic.title)}</span><span class="focus-meta"><span class="subject-chip">${escapeHtml(topic.subject)}</span><span>${topic.estimatedHours} hrs</span></span></div>
      <span class="focus-due ${daysUntil(topic.deadline) <= 1 ? "urgent" : ""}">${escapeHtml(dueText(topic))}</span>
    </div>`).join("") : `<div class="empty-state"><div class="empty-icon">✳</div><h3>Nothing on your plate yet.</h3><p>Add a study topic whenever you're ready.</p><button class="button button-primary" data-open-topic>＋ Add a topic</button></div>`;
  renderWeekPreview(activeTopics);
}

function renderWeekPreview(topics) {
  const container = $("#week-preview");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const mondayOffset = (today.getDay() + 6) % 7;
  const monday = new Date(today);
  monday.setDate(today.getDate() - mondayOffset);
  container.innerHTML = Array.from({ length: 7 }, (_, index) => {
    const day = new Date(monday);
    day.setDate(monday.getDate() + index);
    const dayTopics = topics.filter((topic) => {
      const due = new Date(`${topic.deadline}T00:00:00`);
      return due >= day && due < new Date(day.getTime() + 86400000);
    });
    return `<div class="week-day ${day.getTime() === today.getTime() ? "is-today" : ""}"><div class="week-day-name">${localDate(day, { weekday: "narrow" })}</div><div class="week-day-date">${day.getDate()}</div>${dayTopics.length ? dayTopics.slice(0, 3).map(() => '<i class="day-event"></i>').join("") : '<div class="week-empty">—</div>'}</div>`;
  }).join("");
}

function renderTopics() {
  const active = [...state.topics].sort((a, b) => Number(a.completed) - Number(b.completed) || a.deadline.localeCompare(b.deadline));
  $("#topics-heading-count").textContent = `${active.length} ${active.length === 1 ? "topic" : "topics"}`;
  $("#topic-list").classList.toggle("hidden", !active.length);
  $("#topics-empty").classList.toggle("hidden", Boolean(active.length));
  $("#topic-list").innerHTML = active.map((topic) => `
    <article class="topic-card ${topic.completed ? "completed" : ""}">
      <div class="topic-main"><i class="focus-indicator" style="background:${priorityColor(topic)}"></i><div class="topic-main-text"><strong>${escapeHtml(topic.title)}</strong><span>${escapeHtml(topic.subject)}${topic.completed ? " · Completed" : ""}</span></div></div>
      <div class="topic-metric"><span class="topic-metric-label">ESTIMATE</span><span class="topic-metric-value">${topic.estimatedHours} hrs</span></div>
      <div class="topic-metric"><span class="topic-metric-label">DUE DATE</span><span class="topic-metric-value">${escapeHtml(deadlineDate(topic.deadline))}</span></div>
      <div class="topic-metric"><span class="topic-metric-label">PRIORITY</span><span class="topic-metric-value"><span class="difficulty-dots">${"●".repeat(topic.priority)}${"○".repeat(3 - topic.priority)}</span> ${["", "Low", "Medium", "High"][topic.priority]}</span></div>
      <div class="topic-actions"><button class="small-action" data-edit-topic="${escapeHtml(topic.id)}">Edit</button><button class="small-action" data-toggle-topic="${escapeHtml(topic.id)}">${topic.completed ? "Reopen" : "Done"}</button><button class="small-action danger" data-delete-topic="${escapeHtml(topic.id)}" aria-label="Delete ${escapeHtml(topic.title)}">×</button></div>
    </article>`).join("");
}

async function renderPlan() {
  if (!state.topics.length) {
    $("#plan-table-wrap").classList.add("hidden");
    $("#plan-summary").innerHTML = "";
    $("#plan-warnings").innerHTML = "";
    $("#plan-days").innerHTML = "";
    $("#plan-empty").classList.remove("hidden");
    return;
  }
  $("#plan-table-wrap").classList.remove("hidden");
  $("#plan-empty").classList.add("hidden");
  const result = await api("/api/plan");
  $("#plan-summary").innerHTML = `
    <div class="summary-pill"><span>TOPICS IN PLAN</span><strong>${result.summary.topics}</strong></div>
    <div class="summary-pill"><span>STUDY HOURS</span><strong>${result.summary.scheduledHours} <small>hrs</small></strong></div>
    <div class="summary-pill"><span>AVAILABLE TIME</span><strong>${result.summary.dailyHours} <small>hrs/day</small></strong></div>
    <div class="summary-pill"><span>NEEDS A LOOK</span><strong>${result.summary.unscheduledTopics}</strong></div>`;
  $("#plan-warnings").innerHTML = (result.warnings || []).map((warning) => `<div class="warning-item"><strong>${escapeHtml(warning.title)}</strong> — ${escapeHtml(warning.message)}</div>`).join("");
  $("#plan-days").innerHTML = (result.days || []).map((day) => {
    const today = day.date === localISODate();
    const sessions = (day.sessions || []).map((session, index) => `${session.breakBeforeMinutes ? `<div class="session-break">↘ ${session.breakBeforeMinutes} min reset</div>` : ""}<div class="session-item"><i class="session-color color-${index % 4}"></i><div class="session-details"><strong>${escapeHtml(session.title)}</strong><span>${escapeHtml(session.subject)}${session.isRevision ? " · Quick review" : ""}</span></div><span class="session-duration">${session.durationMinutes} min</span></div>`).join("");
    return `<div class="plan-day-row"><div class="plan-date"><strong>${escapeHtml(localDate(new Date(`${day.date}T12:00:00`), { weekday: "short", month: "short", day: "numeric" }))}</strong><span>${escapeHtml(day.date)}</span>${today ? '<span class="today-tag">TODAY</span>' : ""}</div><div class="plan-sessions">${sessions || '<div class="plan-empty-row">A lighter day — room to rest or catch up.</div>'}</div><div class="plan-total">${day.studyHours} hrs</div></div>`;
  }).join("");
}

function openTopicDialog(topic = null) {
  state.editingId = topic?.id ?? null;
  const form = $("#topic-form");
  form.reset();
  $("#topic-dialog-title").textContent = topic ? "Edit study topic" : "Add a study topic";
  $("#save-topic-button").textContent = topic ? "Save changes" : "Save topic";
  if (topic) {
    $("#topic-subject").value = topic.subject || "";
    $("#topic-title").value = topic.title || "";
    $("#topic-hours").value = topic.estimatedHours || "";
    $("#topic-deadline").value = topic.deadline || "";
    $("#topic-difficulty").value = topic.difficulty || 2;
    $("#topic-priority").value = topic.priority || 2;
    $("#topic-completed").checked = Boolean(topic.completed);
  }
  setMessage($("#topic-message"), "");
  $("#topic-dialog").showModal();
  $("#topic-subject").focus();
}

async function loadSession() {
  try {
    const { email } = await api("/api/me");
    await showApp(email);
  } catch {
    authScreen.classList.remove("hidden");
    appScreen.classList.add("hidden");
  }
}

$("#login-tab").addEventListener("click", () => switchAuthMode("login"));
$("#register-tab").addEventListener("click", () => switchAuthMode("register"));
$("#toggle-password").addEventListener("click", () => {
  const password = $("#password");
  const visible = password.type === "password";
  password.type = visible ? "text" : "password";
  $("#toggle-password").textContent = visible ? "Hide" : "Show";
  $("#toggle-password").setAttribute("aria-label", visible ? "Hide password" : "Show password");
});
$("#auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const registering = $("#register-tab").classList.contains("active");
  const button = $("#auth-submit");
  const email = $("#email").value.trim();
  const password = $("#password").value;
  setMessage($("#auth-message"), "");
  button.disabled = true;
  try {
    const account = await api(`/api/auth/${registering ? "register" : "login"}`, {
      method: "POST", body: JSON.stringify({ email, password })
    });
    if (account.token) {
      sessionStorage.setItem("studyflow_token", account.token);
    }
    await showApp(account.email);
  } catch (error) {
    setMessage($("#auth-message"), error.message);
  } finally {
    button.disabled = false;
  }
});

$$("[data-section]").forEach((link) => link.addEventListener("click", (event) => {
  event.preventDefault();
  const section = link.dataset.section;
  setSection(section === "topics" ? "topics" : section);
}));
$$("[data-go]").forEach((button) => button.addEventListener("click", () => setSection(button.dataset.go)));
$("#add-topic-top").addEventListener("click", () => openTopicDialog());
$("#add-topic-page").addEventListener("click", () => openTopicDialog());
$("#create-plan-button").addEventListener("click", () => setSection("plan"));
document.addEventListener("click", (event) => {
  if (event.target instanceof Element && event.target.closest("[data-open-topic]")) openTopicDialog();
});
$("#topic-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const topic = {
    subject: String(form.get("subject") || "").trim(),
    title: String(form.get("title") || "").trim(),
    estimatedHours: Number(form.get("estimatedHours")),
    deadline: String(form.get("deadline") || "").trim(),
    difficulty: Number(form.get("difficulty")),
    priority: Number(form.get("priority")),
    completed: $("#topic-completed").checked
  };
  const saveButton = $("#save-topic-button");
  saveButton.disabled = true;
  try {
    if (state.editingId) await api(`/api/topics/${encodeURIComponent(state.editingId)}`, { method: "PATCH", body: JSON.stringify(topic) });
    else await api("/api/topics", { method: "POST", body: JSON.stringify(topic) });
    $("#topic-dialog").close();
    await refreshData();
    showToast(state.editingId ? "Your topic was updated." : "Topic added. Your plan is ready to refresh.");
  } catch (error) {
    setMessage($("#topic-message"), error.message);
  } finally {
    saveButton.disabled = false;
  }
});
$("#topic-list").addEventListener("click", async (event) => {
  const editButton = event.target.closest("[data-edit-topic]");
  const toggleButton = event.target.closest("[data-toggle-topic]");
  const deleteButton = event.target.closest("[data-delete-topic]");
  try {
    if (editButton) openTopicDialog(state.topics.find((topic) => topic.id === editButton.dataset.editTopic));
    if (toggleButton) {
      const topic = state.topics.find((item) => item.id === toggleButton.dataset.toggleTopic);
      await api(`/api/topics/${encodeURIComponent(topic.id)}`, { method: "PATCH", body: JSON.stringify({ completed: !topic.completed }) });
      await refreshData();
      showToast(topic.completed ? "Topic reopened." : "Nice work — topic marked complete.");
    }
    if (deleteButton) {
      const topic = state.topics.find((item) => item.id === deleteButton.dataset.deleteTopic);
      let confirmed = true;
      try {
        confirmed = window.confirm(`Remove "${topic.title}" from your topics?`);
      } catch {
        confirmed = true;
      }
      if (confirmed) {
        await api(`/api/topics/${encodeURIComponent(topic.id)}`, { method: "DELETE" });
        await refreshData();
        showToast("Topic removed.");
      }
    }
  } catch (error) {
    showToast(error.message, true);
  }
});
$("#save-hours-button").addEventListener("click", async () => {
  const dailyHours = Number($("#hours-per-day").value);
  try {
    const result = await api("/api/settings", { method: "PUT", body: JSON.stringify({ dailyHours }) });
    state.settings = result;
    if (state.currentSection === "plan") await renderPlan();
    showToast("Your daily study time was updated.");
  } catch (error) {
    showToast(error.message, true);
  }
});
$("#replan-button").addEventListener("click", () => { showToast("Your draft uses your latest topics and priorities."); setSection("plan"); });
$("#rebuild-plan-button").addEventListener("click", async () => {
  try {
    await renderPlan();
    showToast("Your plan was refreshed.");
  } catch (error) {
    showToast(error.message, true);
  }
});
$("#logout-button").addEventListener("click", async () => {
  try {
    await api("/api/auth/logout", { method: "POST", body: "{}" });
    sessionStorage.removeItem("studyflow_token");
    state.topics = [];
    appScreen.classList.add("hidden");
    authScreen.classList.remove("hidden");
    $("#auth-form").reset();
    switchAuthMode("login");
  } catch (error) {
    showToast(error.message, true);
  }
});
$("#help-button").addEventListener("click", () => $("#help-dialog").showModal());
$$("[data-policy]").forEach((link) => link.addEventListener("click", (event) => {
  event.preventDefault();
  const termsSelected = link.getAttribute("href") === "#terms";
  $("#policy-title").textContent = termsSelected ? "Terms of use" : "Privacy at Studyflow";
  $("#terms-copy").classList.toggle("hidden", !termsSelected);
  $("#privacy-copy").classList.toggle("hidden", termsSelected);
  $("#policy-dialog").showModal();
}));
$$("[data-close-dialog]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));
$$("dialog").forEach((dialog) => dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close();
}));
window.addEventListener("hashchange", () => {
  const hash = window.location.hash;
  if (hash === "#my-topics") setSection("topics");
  else if (hash === "#my-plan") setSection("plan");
  else if (hash === "#overview") setSection("overview");
});
loadSession();
