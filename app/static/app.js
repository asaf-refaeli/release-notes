// Every value from the API reaches the page through textContent, never as HTML.

const form = document.querySelector("#release-form");
const button = document.querySelector("#create-button");
const errorBox = document.querySelector("#error");
const tbody = document.querySelector("#releases");
const empty = document.querySelector("#empty");
const versionLabel = document.querySelector("#app-version");

// 404/409 send detail as a string; 422 sends a list, one item per invalid field.
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

function showError(message) {
  errorBox.textContent = message;
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

function cell(text) {
  const td = document.createElement("td");
  td.textContent = text;
  return td;
}

function renderRelease(release) {
  const badge = document.createElement("span");
  badge.className = "badge " + release.status.toLowerCase();
  badge.textContent = release.status;
  const statusCell = document.createElement("td");
  statusCell.append(badge);

  const row = document.createElement("tr");
  row.append(
    cell(release.version),
    statusCell,
    cell(release.description),
    cell(new Date(release.created_at).toLocaleString()),
  );
  return row;
}

async function loadReleases() {
  try {
    const response = await fetch("/api/releases");
    if (!response.ok) {
      showError(errorMessage(await readJson(response)));
      return;
    }
    const releases = await response.json();
    tbody.replaceChildren(...releases.map(renderRelease));
    empty.hidden = releases.length > 0;
  } catch {
    showError("Cannot reach the server");
  }
}

async function createRelease(event) {
  event.preventDefault();
  showError("");
  // Disabled until the answer arrives, so a double-click sends one request.
  button.disabled = true;
  try {
    const response = await fetch("/api/releases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.fromEntries(new FormData(form))),
    });
    if (response.ok) {
      form.reset();
      await loadReleases();
    } else {
      showError(errorMessage(await readJson(response)));
    }
  } catch {
    showError("Cannot reach the server");
  } finally {
    button.disabled = false;
  }
}

form.addEventListener("submit", createRelease);
loadVersion();
loadReleases();
