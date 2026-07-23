
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
