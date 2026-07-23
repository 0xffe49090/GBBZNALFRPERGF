"use strict";
let currentTab;
let navigationResult;
let sharingResult;
let originalUrl;

function log(event, details = {}) {
  console.info(`[Uncruft] ${event}`, details);
  try {
    ext.runtime.sendMessage({ type: "popup-log", event, details });
  } catch (_) {}
}

function showStatus(message, isError = false) {
  const element = document.querySelector("#status");
  element.textContent = message;
  element.className = isError ? "status error" : "status ok";
}

async function queryActiveTab() {
  const result = ext.tabs.query({ active: true, currentWindow: true });
  if (result && typeof result.then === "function") return result;
  return new Promise((resolve, reject) => {
    ext.tabs.query({ active: true, currentWindow: true }, tabs => {
      const error = ext.runtime.lastError;
      error ? reject(new Error(error.message)) : resolve(tabs);
    });
  });
}

async function updateTab(tabId, url) {
  const result = ext.tabs.update(tabId, { url });
  if (result && typeof result.then === "function") return result;
  return new Promise((resolve, reject) => {
    ext.tabs.update(tabId, { url }, tab => {
      const error = ext.runtime.lastError;
      error ? reject(new Error(error.message)) : resolve(tab);
    });
  });
}

async function sendMessage(message) {
  try {
    const result = ext.runtime.sendMessage(message);
    if (result && typeof result.then === "function") return result;
  } catch (_) {
    // Fall through to callback form.
  }
  return new Promise((resolve, reject) => {
    ext.runtime.sendMessage(message, response => {
      const error = ext.runtime.lastError;
      error ? reject(new Error(error.message)) : resolve(response);
    });
  });
}

async function copyText(text) {
  if (!text) throw new Error("There is no URL to copy.");

  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
  } catch (error) {
    log("Clipboard API failed; trying fallback", { error: error.message });
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("The browser rejected the clipboard operation.");
}

(async () => {
  try {
    [currentTab] = await queryActiveTab();
    if (!currentTab?.url) throw new Error("No readable URL is available for this tab.");

    const [{ config }, stateResponse] = await Promise.all([
      storageGet(["config"]),
      sendMessage({ type: "get-navigation-state", tabId: currentTab.id }).catch(() => null)
    ]);

    const state = stateResponse?.state;
    originalUrl = state?.cleaned === currentTab.url ? state.original : currentTab.url;
    navigationResult = cleanUrl(originalUrl, config);
    sharingResult = cleanUrlForSharing(originalUrl, config);

    document.querySelector("#url").textContent = sharingResult.cleaned;
    document.querySelector("#removed").textContent = sharingResult.removed.length
      ? `Share cleanup removes: ${sharingResult.removed.join(", ")}`
      : "No matching parameters.";
    document.querySelector("#summary").textContent = sharingResult.removed.length
      ? `${sharingResult.removed.length} parameter(s) matched.`
      : "Current URL is already clean.";
    document.querySelector("#navigate").disabled = navigationResult.cleaned === currentTab.url;

    log("Popup initialized", {
      tabId: currentTab.id,
      current: currentTab.url,
      original: originalUrl,
      clean: sharingResult.cleaned,
      removed: sharingResult.removed
    });
  } catch (error) {
    document.querySelector("#summary").textContent = error.message;
    showStatus(error.message, true);
    log("Popup initialization failed", { error: error.message });
  }
})();

document.querySelector("#navigate").addEventListener("click", async () => {
  try {
    if (!currentTab || !navigationResult) throw new Error("No clean URL is available.");
    await updateTab(currentTab.id, navigationResult.cleaned);
    log("Navigate clean", { from: currentTab.url, to: navigationResult.cleaned });
    window.close();
  } catch (error) {
    showStatus(error.message, true);
    log("Navigate clean failed", { error: error.message });
  }
});

document.querySelector("#copy").addEventListener("click", async () => {
  try {
    await copyText(sharingResult?.cleaned);
    showStatus("Clean link copied.");
    log("Copied clean link", { url: sharingResult.cleaned, removed: sharingResult.removed });
  } catch (error) {
    showStatus(error.message, true);
    log("Copy clean failed", { error: error.message });
  }
});

document.querySelector("#copyOriginal").addEventListener("click", async () => {
  try {
    await copyText(originalUrl);
    showStatus("Original URL copied.");
    log("Copied original URL", { url: originalUrl });
  } catch (error) {
    showStatus(error.message, true);
    log("Copy original failed", { error: error.message });
  }
});

document.querySelector("#options").addEventListener("click", () => {
  log("Opened settings");
  ext.runtime.openOptionsPage();
});
