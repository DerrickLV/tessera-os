"use strict";

// Same-origin. The session cookie is issued SameSite=Lax, so a browser will
// not attach it to a cross-origin request -- pointing this at another host
// produces a sign-in that appears to succeed and 401s on every call after.
// The empty prefix keeps every fetch relative to wherever the portal is served.
const API = "";
const element = id => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    character => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[character],
  );
}

async function request(path, options = {}) {
  const response = await fetch(API + path, {
    ...options,
    credentials: "include",
    headers: {Accept: "application/json", ...(options.headers || {})},
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      message = (await response.json()).detail || message;
    } catch {
      // Preserve the status-only message when the server did not return JSON.
    }
    throw Object.assign(new Error(message), {status: response.status});
  }
  return response.json();
}

async function loadDocuments(projectId, button) {
  button.disabled = true;
  const target = button.nextElementSibling;
  target.textContent = "Loading…";
  try {
    const documents = await request(
      `/v1/projects/${encodeURIComponent(projectId)}/documents`,
    );
    target.innerHTML = documents.length
      ? documents.map(document => `<div class="doc"><b>${escapeHtml(document.title)}</b><span class="meta">${escapeHtml(document.source_id)} · ${escapeHtml(document.modified_at || "date unavailable")}</span></div>`).join("")
      : "No approved documents in this project yet.";
  } catch (error) {
    target.textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function boot() {
  element("signIn").href = API + "/v1/auth/microsoft/start";
  try {
    const session = await request("/v1/session");
    element("loading").style.display = "none";
    element("workspace").style.display = "block";
    element("welcome").textContent = `Welcome, ${session.display_name}.`;
    element("projects").innerHTML = session.projects.map(project => `<article class="card"><div class="eyebrow">Project</div><h2>${escapeHtml(project.name)}</h2><p>${escapeHtml(project.summary || "Approved SharePoint workspace")}</p><button class="open-project" data-project-id="${escapeHtml(project.id)}">View approved documents</button><div class="docs"></div></article>`).join("");
    document.querySelectorAll(".open-project").forEach(button => {
      button.addEventListener("click", () => loadDocuments(button.dataset.projectId, button));
    });
  } catch (error) {
    element("loading").style.display = "none";
    element("login").style.display = "block";
    if (error.status !== 401) element("loginError").textContent = error.message;
  }
}

element("logout").addEventListener("click", () => {
  window.location.assign(API + "/v1/auth/logout");
});
boot();
