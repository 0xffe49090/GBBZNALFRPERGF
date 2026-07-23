
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


"use strict";

const RULE_ID_MIN = 1000;
const RULE_ID_MAX = 4999;

function normalizeParam(value) {
  return String(value ?? "").trim();
}

function normalizeDomain(value) {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/^\*\./, "")
    .replace(/\.$/, "");
}

function unique(values, normalizer = value => value) {
  const seen = new Set();
  const output = [];
  for (const raw of values ?? []) {
    const value = normalizer(raw);
    if (!value || seen.has(value)) continue;
    seen.add(value);
    output.push(value);
  }
  return output;
}

function normalizeDomainMap(value) {
  const output = {};
  if (!value || typeof value !== "object" || Array.isArray(value)) return output;
  for (const [rawDomain, rawParams] of Object.entries(value)) {
    const domain = normalizeDomain(rawDomain);
    if (!domain || !Array.isArray(rawParams)) continue;
    output[domain] = unique(rawParams, normalizeParam);
  }
  return output;
}

function normalizeConfig(value) {
  return {
    enabled: value?.enabled !== false,
    globalRemove: unique(value?.globalRemove, normalizeParam),
    domainRemove: normalizeDomainMap(value?.domainRemove),
    domainExceptions: normalizeDomainMap(value?.domainExceptions),
    removeAllDomains: unique(value?.removeAllDomains, normalizeDomain),
    cleanSubframes: value?.cleanSubframes === true
  };
}

function chunk(values, size = 1000) {
  const output = [];
  for (let index = 0; index < values.length; index += size) {
    output.push(values.slice(index, index + size));
  }
  return output;
}

function buildRemoveRule(id, params, condition) {
  return {
    id,
    priority: 1,
    action: {
      type: "redirect",
      redirect: {
        transform: {
          queryTransform: { removeParams: params }
        }
      }
    },
    condition
  };
}

function compileRules(rawConfig) {
  const config = normalizeConfig(rawConfig);
  if (!config.enabled) return [];

  const resourceTypes = config.cleanSubframes
    ? ["main_frame", "sub_frame"]
    : ["main_frame"];

  const rules = [];
  let id = RULE_ID_MIN;
  const exceptionDomains = Object.keys(config.domainExceptions);
  const removeAllSet = new Set(config.removeAllDomains);
  const globallyExcluded = unique([...exceptionDomains, ...config.removeAllDomains], normalizeDomain);

  for (const params of chunk(config.globalRemove)) {
    if (!params.length) continue;
    const condition = {
      regexFilter: "^https?://",
      resourceTypes
    };
    if (globallyExcluded.length) condition.excludedRequestDomains = globallyExcluded;
    rules.push(buildRemoveRule(id++, params, condition));
  }

  for (const domain of exceptionDomains) {
    if (removeAllSet.has(domain)) continue;
    const keep = new Set(config.domainExceptions[domain]);
    const params = config.globalRemove.filter(param => !keep.has(param));
    const merged = unique([...(params ?? []), ...(config.domainRemove[domain] ?? [])], normalizeParam);
    for (const group of chunk(merged)) {
      if (!group.length) continue;
      rules.push(buildRemoveRule(id++, group, {
        requestDomains: [domain],
        resourceTypes
      }));
    }
  }

  for (const [domain, domainParams] of Object.entries(config.domainRemove)) {
    if (removeAllSet.has(domain) || exceptionDomains.includes(domain)) continue;
    for (const params of chunk(domainParams)) {
      if (!params.length) continue;
      rules.push(buildRemoveRule(id++, params, {
        requestDomains: [domain],
        resourceTypes
      }));
    }
  }

  for (const domain of config.removeAllDomains) {
    rules.push({
      id: id++,
      priority: 2,
      action: {
        type: "redirect",
        redirect: {
          transform: {
            queryTransform: { removeAll: true }
          }
        }
      },
      condition: {
        requestDomains: [domain],
        resourceTypes
      }
    });
  }

  if (id > RULE_ID_MAX + 1) {
    throw new Error(`Configuration generated too many rules (${rules.length}).`);
  }
  return rules;
}

function hostnameMatches(hostname, domain) {
  return hostname === domain || hostname.endsWith(`.${domain}`);
}

function cleanUrl(rawUrl, rawConfig) {
  const config = normalizeConfig(rawConfig);
  const url = new URL(rawUrl);
  if (!/^https?:$/.test(url.protocol) || !config.enabled) {
    return { original: rawUrl, cleaned: rawUrl, removed: [] };
  }

  const hostname = url.hostname.toLowerCase();
  const removed = [];

  const removeAll = config.removeAllDomains.some(domain => hostnameMatches(hostname, domain));
  if (removeAll) {
    for (const key of [...url.searchParams.keys()]) removed.push(key);
    url.search = "";
    return { original: rawUrl, cleaned: url.href, removed };
  }

  const exceptionEntry = Object.entries(config.domainExceptions)
    .find(([domain]) => hostnameMatches(hostname, domain));
  const keep = new Set(exceptionEntry?.[1] ?? []);
  const candidates = new Set(config.globalRemove.filter(param => !keep.has(param)));

  for (const [domain, params] of Object.entries(config.domainRemove)) {
    if (hostnameMatches(hostname, domain)) {
      for (const param of params) candidates.add(param);
    }
  }

  for (const key of [...url.searchParams.keys()]) {
    if (candidates.has(key)) {
      url.searchParams.delete(key);
      removed.push(key);
    }
  }

  return { original: rawUrl, cleaned: url.href, removed };
}


function cleanUrlForSharing(rawUrl, rawConfig) {
  const result = cleanUrl(rawUrl, rawConfig);
  const url = new URL(result.cleaned);
  const hostname = url.hostname.toLowerCase();
  const removed = [...result.removed];

  const shareOnlyByDomain = {
    "amazon.com": ["qid", "sr"],
    "amazon.ca": ["qid", "sr"],
    "amazon.co.uk": ["qid", "sr"],
    "amazon.de": ["qid", "sr"],
    "amazon.fr": ["qid", "sr"],
    "amazon.es": ["qid", "sr"],
    "amazon.it": ["qid", "sr"],
    "amazon.co.jp": ["qid", "sr"]
  };

  for (const [domain, params] of Object.entries(shareOnlyByDomain)) {
    if (!hostnameMatches(hostname, domain)) continue;
    for (const key of [...url.searchParams.keys()]) {
      if (params.includes(key)) {
        url.searchParams.delete(key);
        removed.push(key);
      }
    }
  }

  return {
    original: rawUrl,
    cleaned: url.href,
    removed: unique(removed, normalizeParam)
  };
}

const DEFAULT_CONFIG = {"enabled": true, "globalRemove": ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id", "utm_name", "utm_reader", "gclid", "dclid", "gbraid", "wbraid", "gclsrc", "msclkid", "twclid", "yclid", "fbclid", "igshid", "ttclid", "li_fat_id", "mc_cid", "mc_eid", "mkt_tok", "vero_conv", "vero_id", "oly_anon_id", "oly_enc_id", "_hsenc", "_hsmi", "hsCtaTracking", "hsa_acc", "hsa_ad", "hsa_cam", "hsa_grp", "hsa_kw", "hsa_mt", "hsa_net", "hsa_src", "hsa_tgt", "pk_campaign", "pk_kwd", "pk_keyword", "pk_source", "pk_medium", "pk_content", "sc_campaign", "sc_channel", "sc_content", "sc_medium", "sc_outcome", "sc_geo", "sc_country", "s_cid", "s_kwcid", "ef_id", "epik", "irclickid", "wickedid", "zanpid", "sscid", "affid", "aff_id", "affiliate", "aff_sub", "aff_sub2", "aff_sub3", "afftrack", "clickref", "click_ref", "clickid", "click_id", "campaignid", "adgroupid", "adid", "adset_id", "creative", "creative_id", "placement", "network", "trk", "trkCampaign", "trkContact", "trkModule", "trkMsg", "trk_sid", "tracking_id", "trackingid", "vero_campaign", "vero_email", "dm_i", "soc_src", "soc_trk", "soc_pid", "ncid", "icid", "icampaign", "icreative", "ref_src", "ref_url", "referrer", "refid", "sourceid", "source_id", "_ga", "_gl", "ga_campaign", "ga_content", "ga_medium", "ga_source", "fb_action_ids", "fb_action_types", "fb_source", "mibextid", "spm", "scm", "sp_atk", "xptdk", "igsh", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "embeds_referring_euri", "embeds_referring_origin"], "domainRemove": {"amazon.com": ["_encoding", "ref", "ref_", "refRID", "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_p", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "content-id", "ascsubtag", "tag", "linkCode", "camp", "creative", "creativeASIN", "crid", "keywords", "sprefix"], "amazon.ca": ["_encoding", "ref", "ref_", "refRID", "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_p", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "content-id", "ascsubtag", "tag", "linkCode", "camp", "creative", "creativeASIN", "crid", "keywords", "sprefix"], "amazon.co.uk": ["_encoding", "ref", "ref_", "refRID", "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_p", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "content-id", "ascsubtag", "tag", "linkCode", "camp", "creative", "creativeASIN", "crid", "keywords", "sprefix"], "amazon.de": ["_encoding", "ref", "ref_", "refRID", "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_p", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "content-id", "ascsubtag", "tag", "linkCode", "camp", "creative", "creativeASIN", "crid", "keywords", "sprefix"], "amazon.fr": ["_encoding", "ref", "ref_", "refRID", "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_p", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "content-id", "ascsubtag", "tag", "linkCode", "camp", "creative", "creativeASIN", "crid", "keywords", "sprefix"], "amazon.es": ["_encoding", "ref", "ref_", "refRID", "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_p", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "content-id", "ascsubtag", "tag", "linkCode", "camp", "creative", "creativeASIN", "crid", "keywords", "sprefix"], "amazon.it": ["_encoding", "ref", "ref_", "refRID", "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_p", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "content-id", "ascsubtag", "tag", "linkCode", "camp", "creative", "creativeASIN", "crid", "keywords", "sprefix"], "amazon.co.jp": ["_encoding", "ref", "ref_", "refRID", "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_p", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "content-id", "ascsubtag", "tag", "linkCode", "camp", "creative", "creativeASIN", "crid", "keywords", "sprefix"], "youtube.com": ["si", "feature"], "youtu.be": ["si", "feature"]}, "domainExceptions": {}, "removeAllDomains": [], "cleanSubframes": false};
let applyQueue = Promise.resolve();
const navigationState = new Map();

function logInfo(event, details = {}) {
  console.info(`[Uncruft] ${event}`, details);
}

function logError(event, error) {
  console.error(`[Uncruft] ${event}`, error);
}

async function sessionSet(value) {
  if (ext.storage?.session) {
    const result = ext.storage.session.set(value);
    if (result && typeof result.then === "function") await result;
  }
}

async function sessionGet(keys) {
  if (!ext.storage?.session) return {};
  const result = ext.storage.session.get(keys);
  if (result && typeof result.then === "function") return result;
  return new Promise((resolve, reject) => {
    ext.storage.session.get(keys, value => {
      const error = ext.runtime.lastError;
      error ? reject(new Error(error.message)) : resolve(value);
    });
  });
}

async function rememberNavigation(tabId, state) {
  navigationState.set(tabId, state);
  try {
    await sessionSet({ [`navigation-${tabId}`]: state });
  } catch (error) {
    logError("Could not persist tab navigation state", error);
  }
}

async function getNavigation(tabId) {
  if (navigationState.has(tabId)) return navigationState.get(tabId);
  try {
    const key = `navigation-${tabId}`;
    const stored = await sessionGet([key]);
    if (stored[key]) navigationState.set(tabId, stored[key]);
    return stored[key] ?? null;
  } catch (error) {
    logError("Could not read tab navigation state", error);
    return null;
  }
}

async function loadConfig() {
  const stored = await storageGet(["config"]);
  if (!stored.config) {
    await storageSet({ config: DEFAULT_CONFIG });
    logInfo("Installed bundled configuration", {
      globalParameters: DEFAULT_CONFIG.globalRemove.length,
      domainPolicies: Object.keys(DEFAULT_CONFIG.domainRemove).length
    });
    return normalizeConfig(DEFAULT_CONFIG);
  }
  return normalizeConfig(stored.config);
}

async function applyRulesNow(reason = "unspecified") {
  const config = await loadConfig();
  const existing = await getDynamicRules();
  const next = compileRules(config);
  await updateDynamicRules({
    removeRuleIds: existing.map(rule => rule.id),
    addRules: next
  });
  await storageSet({
    compiledRuleCount: next.length,
    lastCompiledAt: new Date().toISOString()
  });
  logInfo("Rules applied", {
    reason,
    previousRuleCount: existing.length,
    ruleCount: next.length,
    enabled: config.enabled
  });
  return next.length;
}

function applyRules(reason) {
  applyQueue = applyQueue
    .catch(() => undefined)
    .then(() => applyRulesNow(reason));
  return applyQueue;
}

ext.runtime.onInstalled.addListener(details => {
  applyRules(`runtime.onInstalled:${details.reason}`)
    .catch(error => logError("Install rule application failed", error));
});

if (ext.runtime.onStartup) {
  ext.runtime.onStartup.addListener(() => {
    applyRules("runtime.onStartup")
      .catch(error => logError("Startup rule application failed", error));
  });
}

if (ext.webNavigation?.onBeforeNavigate) {
  ext.webNavigation.onBeforeNavigate.addListener(async details => {
    if (details.frameId !== 0 || !/^https?:/i.test(details.url)) return;
    try {
      const config = await loadConfig();
      const result = cleanUrl(details.url, config);
      if (!result.removed.length || result.cleaned === details.url) return;
      const state = {
        original: details.url,
        cleaned: result.cleaned,
        removed: result.removed,
        observedAt: new Date().toISOString()
      };
      await rememberNavigation(details.tabId, state);
      logInfo("Navigation cleaned", {
        tabId: details.tabId,
        original: details.url,
        cleaned: result.cleaned,
        removed: result.removed
      });
    } catch (error) {
      logError("Navigation observation failed", error);
    }
  });
}

if (ext.tabs?.onRemoved) {
  ext.tabs.onRemoved.addListener(tabId => navigationState.delete(tabId));
}

ext.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "apply-rules") {
    applyRules("settings-save")
      .then(count => sendResponse({ ok: true, count }))
      .catch(error => sendResponse({ ok: false, error: error.message }));
    return true;
  }

  if (message?.type === "get-navigation-state") {
    getNavigation(message.tabId)
      .then(state => sendResponse({ ok: true, state }))
      .catch(error => sendResponse({ ok: false, error: error.message }));
    return true;
  }

  if (message?.type === "popup-log") {
    logInfo(message.event || "Popup event", message.details || {});
    sendResponse({ ok: true });
    return false;
  }

  return undefined;
});
