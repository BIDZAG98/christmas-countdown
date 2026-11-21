const REFRESH_INTERVAL = 5 * 60 * 1000;
const primaryRing = document.getElementById("primary-ring");
const primaryPercent = document.getElementById("primary-percent");
const primaryWindow = document.getElementById("primary-window");
const primaryReset = document.getElementById("primary-reset");
const secondaryCard = document.getElementById("secondary-card");
const liveState = document.getElementById("live-state");
const updated = document.getElementById("updated");
const errorMessage = document.getElementById("error");
const refreshButton = document.getElementById("refresh");
let refreshTimer;
let countdownTimer;
let currentUsage;

function windowName(seconds, fallback) {
  if (!seconds) return fallback;
  const hours = seconds / 3600;
  if (hours >= 24 && hours % 24 === 0) {
    const days = hours / 24;
    return `${days}-${days === 1 ? "day" : "day"} window`;
  }
  if (hours >= 1 && hours % 1 === 0) return `${hours}-hour window`;
  const minutes = Math.round(seconds / 60);
  return `${minutes}-minute window`;
}

function resetLabel(resetAt) {
  if (!resetAt) return "Reset time unavailable";
  const seconds = Math.max(0, Math.floor((resetAt - Date.now()) / 1000));
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const time = days ? `${days}d ${hours}h` : hours ? `${hours}h ${minutes}m` : `${minutes}m`;
  return `Resets in ${time}`;
}

function setWindow(prefix, window, fallback) {
  const percent = Math.round(Math.max(0, Math.min(100, window.usedPercent)));
  if (prefix === "primary") {
    primaryRing.style.setProperty("--turn", `${percent * 3.6}deg`);
    primaryRing.setAttribute("aria-label", `Codex usage: ${percent}% used`);
    primaryPercent.textContent = `${percent}%`;
    primaryWindow.textContent = windowName(window.windowSeconds, fallback);
    primaryReset.textContent = resetLabel(window.resetAt);
  } else {
    document.getElementById("secondary-window").textContent = windowName(window.windowSeconds, fallback);
    document.getElementById("secondary-percent").textContent = `${percent}% used`;
    document.getElementById("secondary-bar").style.width = `${percent}%`;
    document.getElementById("secondary-reset").textContent = resetLabel(window.resetAt);
  }
}

function renderUsage(data) {
  currentUsage = data;
  if (data.primary) setWindow("primary", data.primary, "Primary usage window");
  else if (data.secondary) setWindow("primary", data.secondary, "Usage window");

  if (data.secondary) {
    secondaryCard.hidden = false;
    setWindow("secondary", data.secondary, "Additional usage window");
  } else {
    secondaryCard.hidden = true;
  }

  liveState.classList.remove("is-error");
  liveState.classList.add("is-live");
  liveState.innerHTML = "<i></i> Live";
  errorMessage.hidden = true;
  updated.textContent = `Updated ${new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(data.updatedAt)}`;
  document.getElementById("title").textContent = "Codex is ready.";
}

function showError(message) {
  liveState.classList.remove("is-live");
  liveState.classList.add("is-error");
  liveState.innerHTML = "<i></i> Needs attention";
  errorMessage.textContent = message;
  errorMessage.hidden = false;
  if (!currentUsage) {
    primaryWindow.textContent = "Usage unavailable";
    document.getElementById("title").textContent = "Can’t reach your usage.";
    updated.textContent = "No successful refresh yet";
  } else {
    updated.textContent += " · showing last successful refresh";
  }
}

async function refreshUsage() {
  refreshButton.disabled = true;
  refreshButton.textContent = "Refreshing…";
  try {
    const response = await fetch("/api/usage", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load usage.");
    renderUsage(data);
  } catch (error) {
    showError(error instanceof Error ? error.message : "Could not load usage.");
  } finally {
    refreshButton.disabled = false;
    refreshButton.textContent = "Refresh now";
  }
}

refreshButton.addEventListener("click", () => {
  clearTimeout(refreshTimer);
  refreshUsage().finally(scheduleRefresh);
});

function scheduleRefresh() {
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => refreshUsage().finally(scheduleRefresh), REFRESH_INTERVAL);
}

function updateCountdowns() {
  if (!currentUsage) return;
  if (currentUsage.primary) primaryReset.textContent = resetLabel(currentUsage.primary.resetAt);
  if (currentUsage.secondary) document.getElementById("secondary-reset").textContent = resetLabel(currentUsage.secondary.resetAt);
}

refreshUsage().finally(scheduleRefresh);
countdownTimer = setInterval(updateCountdowns, 30_000);
window.addEventListener("beforeunload", () => {
  clearInterval(countdownTimer);
  clearTimeout(refreshTimer);
});
