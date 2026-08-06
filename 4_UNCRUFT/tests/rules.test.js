"use strict";
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const path=require("node:path");
const context={URL,console}; vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname,"../src/rules.js"),"utf8"),context);
const config={enabled:true,globalRemove:["utm_source","utm_medium","fbclid","gclid"],domainRemove:{"amazon.com":["ref_","pd_rd_w","content-id"],"youtube.com":["si","feature"]},domainExceptions:{},removeAllDomains:[],cleanSubframes:false};
const cases=[
 ["UTM cleanup","https://example.com/a?id=42&utm_source=x&utm_medium=y","https://example.com/a?id=42"],
 ["negative control","https://example.com/a?q=x&page=2","https://example.com/a?q=x&page=2"],
 ["repeated parameters","https://example.com/a?utm_source=x&utm_source=y&id=1","https://example.com/a?id=1"],
 ["fragment preservation","https://example.com/a?fbclid=x&q=y#z","https://example.com/a?q=y#z"],
 ["Amazon cleanup","https://amazon.com/x?ref_=a&pd_rd_w=b&content-id=c","https://amazon.com/x"],
 ["YouTube cleanup","https://youtube.com/watch?v=a&si=b&feature=shared","https://youtube.com/watch?v=a"]
];
for(const [name,input,expected] of cases)test(name,()=>assert.equal(context.cleanUrl(input,config).cleaned,expected));
test("domain exceptions",()=>{const c={...config,domainExceptions:{"example.com":["utm_source"]}};assert.equal(context.cleanUrl("https://example.com/?utm_source=x&fbclid=y",c).cleaned,"https://example.com/?utm_source=x");});
test("remove all",()=>{const c={...config,removeAllDomains:["example.com"]};assert.equal(context.cleanUrl("https://example.com/?id=1&q=x",c).cleaned,"https://example.com/");});
test("sharing cleanup",()=>assert.equal(context.cleanUrlForSharing("https://amazon.com/s?k=ring&qid=1&sr=2",config).cleaned,"https://amazon.com/s?k=ring"));
