"use strict";
let currentTab, navigationResult, sharingResult;
async function queryActiveTab() {
  const r = ext.tabs.query({active:true,currentWindow:true});
  return r && typeof r.then === "function" ? r : new Promise((resolve,reject) => {
    ext.tabs.query({active:true,currentWindow:true}, tabs => {
      const e=ext.runtime.lastError; e ? reject(new Error(e.message)) : resolve(tabs);
    });
  });
}
async function updateTab(tabId,url) {
  const r=ext.tabs.update(tabId,{url});
  return r && typeof r.then === "function" ? r : new Promise((resolve,reject) => {
    ext.tabs.update(tabId,{url},tab => {
      const e=ext.runtime.lastError; e ? reject(new Error(e.message)) : resolve(tab);
    });
  });
}
(async () => {
  try {
    [currentTab]=await queryActiveTab();
    const {config}=await storageGet(["config"]);
    navigationResult=cleanUrl(currentTab.url,config);
    sharingResult=cleanUrlForSharing(currentTab.url,config);
    document.querySelector("#url").textContent=sharingResult.cleaned;
    document.querySelector("#removed").textContent=sharingResult.removed.length
      ? `Share cleanup removes: ${sharingResult.removed.join(", ")}` : "No matching parameters.";
    document.querySelector("#summary").textContent=sharingResult.removed.length
      ? `${sharingResult.removed.length} parameter(s) matched.` : "Current URL is already clean.";
    document.querySelector("#navigate").disabled=!navigationResult.removed.length;
  } catch(error) { document.querySelector("#summary").textContent=error.message; }
})();
document.querySelector("#navigate").addEventListener("click",async()=>{if(currentTab&&navigationResult)await updateTab(currentTab.id,navigationResult.cleaned);window.close();});
document.querySelector("#copy").addEventListener("click",async()=>{if(sharingResult){await navigator.clipboard.writeText(sharingResult.cleaned);document.querySelector("#status").textContent="Clean link copied.";}});
document.querySelector("#copyOriginal").addEventListener("click",async()=>{if(currentTab){await navigator.clipboard.writeText(currentTab.url);document.querySelector("#status").textContent="Original URL copied.";}});
document.querySelector("#options").addEventListener("click",()=>ext.runtime.openOptionsPage());