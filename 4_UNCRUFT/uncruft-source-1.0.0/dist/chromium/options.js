"use strict";
const DEFAULT_CONFIG = {"enabled": true, "globalRemove": ["utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id", "utm_name", "utm_reader", "gclid", "dclid", "gbraid", "wbraid", "gclsrc", "msclkid", "twclid", "yclid", "fbclid", "igshid", "ttclid", "li_fat_id", "mc_cid", "mc_eid", "mkt_tok", "vero_conv", "vero_id", "oly_anon_id", "oly_enc_id", "_hsenc", "_hsmi", "hsCtaTracking", "hsa_acc", "hsa_ad", "hsa_cam", "hsa_grp", "hsa_kw", "hsa_mt", "hsa_net", "hsa_src", "hsa_tgt", "pk_campaign", "pk_kwd", "pk_keyword", "pk_source", "pk_medium", "pk_content", "sc_campaign", "sc_channel", "sc_content", "sc_medium", "sc_outcome", "sc_geo", "sc_country", "s_cid", "s_kwcid", "ef_id", "epik", "irclickid", "wickedid", "zanpid", "sscid", "affid", "aff_id", "affiliate", "aff_sub", "aff_sub2", "aff_sub3", "afftrack", "clickref", "click_ref", "clickid", "click_id", "campaignid", "adgroupid", "adid", "adset_id", "creative", "creative_id", "placement", "network", "trk", "trkCampaign", "trkContact", "trkModule", "trkMsg", "trk_sid", "tracking_id", "trackingid", "vero_campaign", "vero_email", "dm_i", "soc_src", "soc_trk", "soc_pid", "ncid", "icid", "icampaign", "icreative", "ref_src", "ref_url", "referrer", "refid", "sourceid", "source_id", "_ga", "_gl", "ga_campaign", "ga_content", "ga_medium", "ga_source", "fb_action_ids", "fb_action_types", "fb_source", "mibextid", "spm", "scm", "sp_atk", "xptdk", "igsh", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "embeds_referring_euri", "embeds_referring_origin"], "domainRemove": {"amazon.com": ["_encoding", "ref", "ref_", "refRID", "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_p", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "content-id", "ascsubtag", "tag", "linkCode", "camp", "creative", "creativeASIN", "crid", "keywords", "sprefix"], "amazon.ca": ["_encoding", "ref", "ref_", "refRID", "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_p", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "content-id", "ascsubtag", "tag", "linkCode", "camp", "creative", "creativeASIN", "crid", "keywords", "sprefix"], "amazon.co.uk": ["_encoding", "ref", "ref_", "refRID", "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_p", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "content-id", "ascsubtag", "tag", "linkCode", "camp", "creative", "creativeASIN", "crid", "keywords", "sprefix"], "amazon.de": ["_encoding", "ref", "ref_", "refRID", "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_p", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "content-id", "ascsubtag", "tag", "linkCode", "camp", "creative", "creativeASIN", "crid", "keywords", "sprefix"], "amazon.fr": ["_encoding", "ref", "ref_", "refRID", "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_p", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "content-id", "ascsubtag", "tag", "linkCode", "camp", "creative", "creativeASIN", "crid", "keywords", "sprefix"], "amazon.es": ["_encoding", "ref", "ref_", "refRID", "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_p", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "content-id", "ascsubtag", "tag", "linkCode", "camp", "creative", "creativeASIN", "crid", "keywords", "sprefix"], "amazon.it": ["_encoding", "ref", "ref_", "refRID", "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_p", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "content-id", "ascsubtag", "tag", "linkCode", "camp", "creative", "creativeASIN", "crid", "keywords", "sprefix"], "amazon.co.jp": ["_encoding", "ref", "ref_", "refRID", "pd_rd_w", "pd_rd_wg", "pd_rd_r", "pd_rd_i", "pd_rd_p", "pf_rd_m", "pf_rd_p", "pf_rd_r", "pf_rd_s", "pf_rd_t", "pf_rd_i", "content-id", "ascsubtag", "tag", "linkCode", "camp", "creative", "creativeASIN", "crid", "keywords", "sprefix"], "youtube.com": ["si", "feature"], "youtu.be": ["si", "feature"]}, "domainExceptions": {}, "removeAllDomains": [], "cleanSubframes": false};
const elements = {
  enabled: document.querySelector("#enabled"), globalRemove: document.querySelector("#globalRemove"),
  domainRemove: document.querySelector("#domainRemove"), domainExceptions: document.querySelector("#domainExceptions"),
  removeAllDomains: document.querySelector("#removeAllDomains"), cleanSubframes: document.querySelector("#cleanSubframes"),
  testUrl: document.querySelector("#testUrl"), testOutput: document.querySelector("#testOutput"),
  status: document.querySelector("#status"), importFile: document.querySelector("#importFile")
};
const lines = value => value.split(/\r?\n/).map(x => x.trim()).filter(Boolean);
function readForm() {
  return normalizeConfig({
    enabled: elements.enabled.checked, globalRemove: lines(elements.globalRemove.value),
    domainRemove: JSON.parse(elements.domainRemove.value || "{}"),
    domainExceptions: JSON.parse(elements.domainExceptions.value || "{}"),
    removeAllDomains: lines(elements.removeAllDomains.value), cleanSubframes: elements.cleanSubframes.checked
  });
}
function writeForm(config) {
  config = normalizeConfig(config);
  elements.enabled.checked = config.enabled;
  elements.globalRemove.value = config.globalRemove.join("\n");
  elements.domainRemove.value = JSON.stringify(config.domainRemove, null, 2);
  elements.domainExceptions.value = JSON.stringify(config.domainExceptions, null, 2);
  elements.removeAllDomains.value = config.removeAllDomains.join("\n");
  elements.cleanSubframes.checked = config.cleanSubframes;
}
function showStatus(message, type = "") {
  elements.status.textContent = message;
  elements.status.className = `status ${type}`;
}
async function sendApplyMessage() {
  const result = ext.runtime.sendMessage({ type: "apply-rules" });
  if (result && typeof result.then === "function") return result;
  return new Promise((resolve, reject) => {
    ext.runtime.sendMessage({ type: "apply-rules" }, response => {
      const error = ext.runtime.lastError;
      error ? reject(new Error(error.message)) : resolve(response);
    });
  });
}
async function save() {
  try {
    const config = readForm();
    compileRules(config);
    await storageSet({ config });
    const response = await sendApplyMessage();
    if (!response?.ok) throw new Error(response?.error || "Rule update failed.");
    showStatus(`Applied ${response.count} dynamic rules.`, "ok");
  } catch (error) { showStatus(error.message, "error"); }
}
function test(mode) {
  try {
    const result = mode === "sharing"
      ? cleanUrlForSharing(elements.testUrl.value, readForm())
      : cleanUrl(elements.testUrl.value, readForm());
    elements.testOutput.textContent = result.removed.length
      ? `${result.cleaned}\n\nRemoved: ${result.removed.join(", ")}`
      : `${result.cleaned}\n\nNo matching parameters.`;
  } catch (error) { elements.testOutput.textContent = `Error: ${error.message}`; }
}
async function exportConfig() {
  const blob = new Blob([JSON.stringify(readForm(), null, 2)], {type:"application/json"});
  const url = URL.createObjectURL(blob); const link = document.createElement("a");
  link.href = url; link.download = "uncruft-config.json"; link.click(); URL.revokeObjectURL(url);
}
async function importConfig(file) {
  try { writeForm(normalizeConfig(JSON.parse(await file.text()))); showStatus("Imported. Save to apply.", "ok"); }
  catch (error) { showStatus(`Import failed: ${error.message}`, "error"); }
}
document.querySelector("#save").addEventListener("click", save);
document.querySelector("#testButton").addEventListener("click", () => test("navigation"));
document.querySelector("#shareTestButton").addEventListener("click", () => test("sharing"));
document.querySelector("#export").addEventListener("click", exportConfig);
document.querySelector("#import").addEventListener("click", () => elements.importFile.click());
elements.importFile.addEventListener("change", e => e.target.files[0] && importConfig(e.target.files[0]));
document.querySelector("#reset").addEventListener("click", () => {
  if (confirm("Reset to bundled defaults?")) { writeForm(DEFAULT_CONFIG); showStatus("Defaults loaded. Save to apply."); }
});
(async () => {
  const stored = await storageGet(["config","compiledRuleCount","lastCompiledAt"]);
  writeForm(stored.config ?? DEFAULT_CONFIG);
  showStatus(`${stored.compiledRuleCount ?? 0} active dynamic rules.`);
  test("navigation");
})();