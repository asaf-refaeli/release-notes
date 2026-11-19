// Every value from the API reaches the page through textContent, never as HTML.

const tbody = document.querySelector("#releases");
const empty = document.querySelector("#empty");
const newButton = document.querySelector("#new-button");
const panel = document.querySelector("#panel");
const panelPlaceholder = document.querySelector("#panel-placeholder");
const panelContent = document.querySelector("#panel-content");
const panelVersion = document.querySelector("#panel-version");
const panelStatus = document.querySelector("#panel-status");
const panelDescription = document.querySelector("#panel-description");
const historyEvents = document.querySelector("#history-events");
const dialog = document.querySelector("#release-dialog");
const form = document.querySelector("#release-form");
const dialogTitle = document.querySelector("#dialog-title");
const versionInput = document.querySelector("#version");
const descriptionInput = document.querySelector("#description");
const versionError = document.querySelector("#version-error");
const descriptionError = document.querySelector("#description-error");
const formError = document.querySelector("#form-error");
const cancelButton = document.querySelector("#cancel-button");
const saveButton = document.querySelector("#save-button");
const toast = document.querySelector("#toast");
const versionLabel = document.querySelector("#app-version");

// Same rule as the API (schemas.py); checked here only to give a friendly message.
const VERSION_PATTERN = /^[0-9]+\.[0-9]+\.[0-9]+$/;
const MESSAGES = {
  versionMissing: "Enter a version number, for example 1.4.0.",
  versionFormat: "Use three numbers separated by dots, for example 1.4.0.",
  descriptionInvalid: "Keep the description under 5,000 characters, without special control characters.",
};
// The API's event types stay as they are; these are the words people read.
const EVENT_TEXT = {
  CREATED: ["Created", "Release created."],
  UPDATED: ["Edited", "Release edited."],
  PUBLISHED: ["Published", "Release published."],
  ARCHIVED: ["Archived", "Release archived."],
};

let editing = null; // the draft open in the dialog, or null when creating
let selectedId = null; // the release shown in the panel
let toastTimer = null;

// ---------- small helpers ----------

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function formatDate(iso) {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function formatDay(iso) {
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString(undefined, { timeStyle: "short" });
}

function badge(status) {
  return element("span", "badge " + status.toLowerCase(), status.toLowerCase());
}

// 400/404/409 send detail as a string; 422 sends a list, one item per invalid field.
function errorMessage(body) {
  if (typeof body?.detail === "string") return body.detail;
  if (Array.isArray(body?.detail)) return body.detail.map((item) => item.msg).join("; ");
  return "Request failed";
}

// A 500 has a plain-text body, so parsing it as JSON fails.
async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

// One toast at a time; a new one replaces the old and restarts the 5 s timer.
function showToast(message, kind) {
  toast.textContent = message;
  toast.className = kind;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.hidden = true;
  }, 5000);
}

async function loadVersion() {
  try {
    const response = await fetch("/api/version");
    if (!response.ok) throw new Error();
    const body = await response.json();
    versionLabel.textContent = body.version;
  } catch {
    versionLabel.textContent = "unknown";
  }
}

// ---------- the table ----------

// Disabled while its request runs, so a double-click sends one request.
function actionButton(label, className, onClick) {
  const button = element("button", "small " + className, label);
  button.type = "button";
  button.addEventListener("click", async (event) => {
    event.stopPropagation(); // otherwise the row behind the button opens too
    button.disabled = true;
    try {
      await onClick();
    } finally {
      button.disabled = false;
    }
  });
  return button;
}

// Two fixed slots: Edit on the left, the lifecycle step always on the right.
// Colour on buttons means importance (blue = the main step); colour on badges means status.
function rowActions(release) {
  const slots = element("div", "slots");
  if (release.status === "DRAFT") {
    slots.append(
      actionButton("Edit", "secondary", () => openDialog(release)),
      actionButton("Publish", "primary next", () => runAction(release, "publish")),
    );
  } else if (release.status === "PUBLISHED") {
    slots.append(actionButton("Archive", "archive next", () => runAction(release, "archive")));
  }
  const cell = element("td");
  cell.append(slots);
  return cell;
}

function renderRelease(release) {
  const versionCell = element("td");
  const chip = element("span", "chip", release.version);
  chip.title = release.version; // hover shows the full version when it is cut
  versionCell.append(chip);
  const statusCell = element("td");
  statusCell.append(badge(release.status));
  // Date on top, time under it: the column stays narrow.
  const createdCell = element("td", "date");
  createdCell.append(
    element("span", "day", formatDay(release.created_at)),
    element("span", "time", formatTime(release.created_at)),
  );

  const row = element("tr", release.id === selectedId ? "selected" : "");
  row.dataset.id = release.id;
  row.tabIndex = 0; // reachable with Tab, so the keyboard can open it too
  row.append(
    versionCell,
    element("td", "description", release.description),
    statusCell,
    createdCell,
    rowActions(release),
  );
  row.addEventListener("click", () => showRelease(release));
  row.addEventListener("keydown", (event) => {
    if (event.target !== row) return; // a key on one of the row's buttons
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault(); // Space would scroll the page
      showRelease(release);
    }
  });
  return row;
}

async function loadReleases() {
  try {
    const response = await fetch("/api/releases");
    if (!response.ok) {
      showLoadError(errorMessage(await readJson(response)));
      return;
    }
    const releases = await response.json();
    tbody.replaceChildren(...releases.map(renderRelease));
    empty.textContent = "No releases yet. Create the first one with New Release.";
    empty.hidden = releases.length > 0;
    // Refresh the panel with the new data, so it never shows an old status or history.
    const selected = releases.find((release) => release.id === selectedId);
    if (selected) await showRelease(selected);
  } catch {
    showLoadError("Cannot reach the server");
  }
}

function showLoadError(message) {
  tbody.replaceChildren();
  empty.textContent = "Could not load releases.";
  empty.hidden = false;
  showToast(message, "error");
}

// ---------- the panel: description and audit history ----------

async function showRelease(release) {
  // Another release: empty the timeline now, so a failed load never shows the old one.
  if (release.id !== selectedId) historyEvents.replaceChildren();
  selectedId = release.id;
  for (const row of tbody.rows) {
    row.classList.toggle("selected", row.dataset.id === String(release.id));
  }
  panel.classList.remove("empty");
  panelPlaceholder.hidden = true;
  panelContent.hidden = false;
  panelVersion.textContent = release.version;
  panelStatus.replaceChildren(badge(release.status));
  panelDescription.textContent = release.description || "No description yet.";
  panelDescription.classList.toggle("none", !release.description);
  await loadHistory(release);
}

function renderEvent(auditEvent) {
  const [title, text] = EVENT_TEXT[auditEvent.event_type] ?? [auditEvent.event_type, ""];
  const item = element("li");
  item.append(
    element("span", "dot " + auditEvent.event_type.toLowerCase()),
    element("span", "event-title", title),
    element("span", "event-time", formatDate(auditEvent.occurred_at)),
    element("span", "event-text", text),
  );
  return item;
}

async function loadHistory(release) {
  try {
    const response = await fetch(`/api/releases/${release.id}/events`);
    // Clicked another row while this was loading: its result, good or bad, no longer matters.
    if (release.id !== selectedId) return;
    if (!response.ok) {
      showToast(errorMessage(await readJson(response)), "error");
      return;
    }
    const events = await response.json();
    historyEvents.replaceChildren(...events.reverse().map(renderEvent)); // newest first
  } catch {
    if (release.id === selectedId) showToast("Cannot reach the server", "error");
  }
}

// ---------- the New/Edit dialog ----------

function openDialog(release) {
  editing = release;
  dialogTitle.textContent = release ? "Edit draft " + release.version : "New release";
  saveButton.textContent = release ? "Save changes" : "Create draft";
  versionInput.value = release ? release.version : "";
  descriptionInput.value = release ? release.description : "";
  dialog.showModal();
  versionInput.focus();
}

function setFieldError(input, box, message) {
  box.textContent = message;
  if (message) input.setAttribute("aria-invalid", "true");
  else input.removeAttribute("aria-invalid");
}

function clearErrors() {
  setFieldError(versionInput, versionError, "");
  setFieldError(descriptionInput, descriptionError, "");
  formError.textContent = "";
}

// Custom messages instead of the browser's "Please fill out this field".
function validateForm() {
  clearErrors();
  const version = versionInput.value.trim();
  if (!version) {
    setFieldError(versionInput, versionError, MESSAGES.versionMissing);
  } else if (!VERSION_PATTERN.test(version)) {
    setFieldError(versionInput, versionError, MESSAGES.versionFormat);
  } else {
    return true;
  }
  versionInput.focus();
  return false;
}

// A 422 lists the invalid fields: show each message under its field.
function showFormError(body) {
  if (!Array.isArray(body?.detail)) {
    formError.textContent = errorMessage(body);
    return;
  }
  for (const item of body.detail) {
    const field = item.loc?.at(-1);
    if (field === "version") setFieldError(versionInput, versionError, MESSAGES.versionFormat);
    else if (field === "description") setFieldError(descriptionInput, descriptionError, MESSAGES.descriptionInvalid);
    else formError.textContent = item.msg;
  }
}

async function saveRelease(event) {
  event.preventDefault();
  if (!validateForm()) return;
  const body = { version: versionInput.value.trim(), description: descriptionInput.value };
  // A textarea turns \r\n into \n, so compare with the same line breaks.
  const savedDescription = editing?.description.replaceAll("\r\n", "\n");
  if (editing && body.version === editing.version && body.description === savedDescription) {
    dialog.close(); // nothing to send; the API would not record an event either
    showToast("No changes to save", "info");
    return;
  }
  saveButton.disabled = true; // a double-click sends one request
  try {
    const response = await fetch(editing ? `/api/releases/${editing.id}` : "/api/releases", {
      method: editing ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      showFormError(await readJson(response)); // the dialog stays open, nothing typed is lost
      if (response.status === 409) await loadReleases(); // the list was out of date
      return;
    }
    const saved = await response.json();
    const message = editing ? `Draft ${saved.version} saved` : `Draft ${saved.version} created`;
    dialog.close();
    selectedId = saved.id;
    showToast(message, "success");
    await loadReleases();
  } catch {
    formError.textContent = "Cannot reach the server";
  } finally {
    saveButton.disabled = false;
  }
}

// ---------- publish and archive ----------

async function runAction(release, action) {
  try {
    const response = await fetch(`/api/releases/${release.id}/${action}`, { method: "POST" });
    if (!response.ok) {
      showToast(errorMessage(await readJson(response)), "error");
      if (response.status === 409) await loadReleases(); // the list was out of date
      return;
    }
    showToast(`${release.version} ${action === "publish" ? "published" : "archived"}`, "success");
    await loadReleases();
  } catch {
    showToast("Cannot reach the server", "error");
  }
}

// ---------- start ----------

newButton.addEventListener("click", () => openDialog(null));
cancelButton.addEventListener("click", () => dialog.close());
// Cancel, Esc, or after a save: leave nothing behind for the next open.
dialog.addEventListener("close", () => {
  editing = null;
  form.reset();
  clearErrors();
});
form.addEventListener("submit", saveRelease);
versionInput.addEventListener("input", () => setFieldError(versionInput, versionError, ""));
descriptionInput.addEventListener("input", () => setFieldError(descriptionInput, descriptionError, ""));
loadVersion();
loadReleases();
