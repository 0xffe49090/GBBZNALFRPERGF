
"use strict";

const ext = globalThis.browser ?? globalThis.chrome;

function callApi(fn, context, ...args) {
  try {
    const result = fn.apply(context, args);
    if (result && typeof result.then === "function") return result;
    return new Promise((resolve, reject) => {
      const error = ext.runtime && ext.runtime.lastError;
      if (error) reject(new Error(error.message));
      else resolve(result);
    });
  } catch (error) {
    return Promise.reject(error);
  }
}

async function storageGet(keys) {
  const result = ext.storage.local.get(keys);
  return result && typeof result.then === "function"
    ? result
    : new Promise((resolve, reject) => {
        ext.storage.local.get(keys, value => {
          const error = ext.runtime.lastError;
          error ? reject(new Error(error.message)) : resolve(value);
        });
      });
}

async function storageSet(value) {
  const result = ext.storage.local.set(value);
  return result && typeof result.then === "function"
    ? result
    : new Promise((resolve, reject) => {
        ext.storage.local.set(value, () => {
          const error = ext.runtime.lastError;
          error ? reject(new Error(error.message)) : resolve();
        });
      });
}

async function getDynamicRules() {
  const result = ext.declarativeNetRequest.getDynamicRules();
  return result && typeof result.then === "function"
    ? result
    : new Promise((resolve, reject) => {
        ext.declarativeNetRequest.getDynamicRules(rules => {
          const error = ext.runtime.lastError;
          error ? reject(new Error(error.message)) : resolve(rules);
        });
      });
}

async function updateDynamicRules(update) {
  const result = ext.declarativeNetRequest.updateDynamicRules(update);
  return result && typeof result.then === "function"
    ? result
    : new Promise((resolve, reject) => {
        ext.declarativeNetRequest.updateDynamicRules(update, () => {
          const error = ext.runtime.lastError;
          error ? reject(new Error(error.message)) : resolve();
        });
      });
}
