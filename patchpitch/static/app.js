"use strict";
const $ = id => document.getElementById(id);
let changes = [], previewText = null, previewTimer, result = null, currentMarkdown = "", edited = false, busy = false;
function error(message) { $("error").textContent = message; $("error").hidden = !message; }
async function jsonRequest(path, body) {
  const response = await fetch(path, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) throw new Error(data.error?.message || (typeof data.detail === "string" ? data.detail : "Check the input lengths, selected changes, and confirmation."));
  return data;
}
async function prepare() {
  const text = $("changes").value;
  if (text === previewText) return;
  if (!text.trim()) {changes = []; $("change-preview").replaceChildren(); previewText = text; return;}
  const data = await jsonRequest("/api/prepare", {text});
  if (text !== $("changes").value) return;
  previewText = text; changes = data.changes;
  $("confirmed").checked = false;
  $("change-preview").replaceChildren();
  for (const change of changes) {
    const row = document.createElement("label"); row.className = "change-row" + (change.include ? "" : " excluded");
    const check = document.createElement("input"); check.type = "checkbox"; check.checked = change.include; check.setAttribute("aria-label", `Include ${change.id}`);
    check.addEventListener("change", () => {change.include = check.checked; row.classList.toggle("excluded", !check.checked); $("confirmed").checked = false;});
    const label = document.createElement("span"), id = document.createElement("span"); id.className = "source-id"; id.textContent = change.id;
    label.append(id, document.createTextNode(change.text));
    if (change.reason) {const reason = document.createElement("span");reason.className = "reason";reason.textContent = change.reason + " · excluded by default";label.append(reason);}
    row.append(check, label); $("change-preview").append(row);
  }
}
$("changes").addEventListener("input", () => {clearTimeout(previewTimer); $("confirmed").checked = false; previewTimer = setTimeout(() => prepare().catch(e => error(e.message)), 250);});
$("example").addEventListener("click", async () => {
  if (edited && !confirm("Replace the input with the illustrative example? Your current draft will stay visible.")) return;
  try {
    const response=await fetch("/static/example.json");
    if(!response.ok) throw new Error("The example could not be loaded. Your current input is still here.");
    const data=await response.json();
    const fields={product:data.product.name,description:data.product.description,audience:data.audience,release:data.release_label,changes:data.changes.map(c=>c.text).join("\n"),cta:data.cta_text};
    for(const [id,value] of Object.entries(fields)) $(id).value=value;
    $("example-label").textContent=`Example input · ${data.product.name} ${data.release_label} · review the selected facts before generating.`;
    $("example-label").hidden=false;error("");await prepare();
  } catch(e) {error(e.message);}
});
function setBusy(value) {
  busy = value; $("generate").disabled = value; $("example").disabled = value;
  for (const control of $("pitch-form").querySelectorAll("input,textarea")) control.disabled = value;
}
function render(data) {
  result = data; currentMarkdown = data.markdown; edited = false;
  $("empty-state").hidden = true; $("result").hidden = false; $("result-tools").hidden = false;
  $("editor").hidden = true; $("editor-label").hidden = true; $("draft-view").hidden = false; $("edited-label").hidden = true; $("edit").textContent = "Edit draft";
  $("timing").textContent = `${data.meta.model} · ${data.meta.elapsed_seconds.toFixed(1)}s · generated locally`;
  $("draft-view").replaceChildren();
  const title = document.createElement("h3"); title.textContent = data.draft.title.text;
  const intro = document.createElement("p"); intro.textContent = data.draft.intro.text;
  const list = document.createElement("ul"); for (const block of data.draft.highlights) {const item = document.createElement("li");item.textContent = block.text;list.append(item);}
  $("draft-view").append(title,intro,list);
  if (data.draft.note) {const note = document.createElement("p");note.textContent = "Note: " + data.draft.note.text;$("draft-view").append(note);}
  if ($("cta").value.trim()) {const cta = document.createElement("p");cta.textContent = $("cta").value.trim();$("draft-view").append(cta);}
  $("warnings").replaceChildren(); $("warnings").hidden = !data.warnings.length;
  for (const warning of data.warnings) {const p=document.createElement("p");p.textContent=warning;$("warnings").append(p);}
  $("source-list").replaceChildren();
  for (const mapping of data.source_map) {const section=document.createElement("section"), heading=document.createElement("h4");heading.textContent=mapping.block;section.append(heading);
    for (const id of mapping.source_ids) {const p=document.createElement("p");p.textContent=`${id} — ${data.sources[id]}`;section.append(p);}$("source-list").append(section);}
}
$("pitch-form").addEventListener("submit", async event => {
  event.preventDefault(); if (busy) return;
  error("");
  try {
    await prepare();
    if (!$("confirmed").checked) throw new Error("Review the selected changes and confirm they belong in this announcement.");
    if (edited && !confirm("Generate a new draft and replace your edited text? Copy or download it first if you want to keep it.")) return;
    const body = {product:{name:$("product").value,description:$("description").value},audience:$("audience").value,release_label:$("release").value,changes:changes.map(({id,text,include}) => ({id,text,include})),cta_text:$("cta").value,confirmed:true};
    setBusy(true); const start = performance.now(); $("status").textContent="Writing with local Gemma… 0.0s";
    const timer = setInterval(() => $("status").textContent=`Writing with local Gemma… ${((performance.now()-start)/1000).toFixed(1)}s`, 200);
    try {const data = await jsonRequest("/api/pitch",body);render(data);$("status").textContent="Your draft is ready to review. Nothing has been published.";}
    finally {clearInterval(timer);setBusy(false);}
  } catch (e) {error(e.message);$("status").textContent="Your input and any previous draft are still here.";}
});
$("edit").addEventListener("click", () => {
  if (!result) return;
  $("editor").value=currentMarkdown;$("editor").hidden=false;$("editor-label").hidden=false;$("draft-view").hidden=true;$("edited-label").hidden=false;$("edit").textContent="Editing Markdown";edited=true;$("editor").focus();
});
$("editor").addEventListener("input", () => {currentMarkdown=$("editor").value;edited=true;});
$("copy").addEventListener("click", async () => {try {await navigator.clipboard.writeText(currentMarkdown);$("status").textContent="Markdown copied. Ready for your final review.";} catch {error("Clipboard unavailable. Use Download Markdown or copy from Edit draft.");}});
$("download").addEventListener("click", () => {const url=URL.createObjectURL(new Blob([currentMarkdown],{type:"text/markdown;charset=utf-8"}));const link=document.createElement("a");link.href=url;link.download="patchpitch-announcement.md";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$("status").textContent="Markdown downloaded. Nothing has been published.";});
fetch("/api/health").then(r=>r.json()).then(data => {$("model-status").textContent=data.ollama==="ready" ? `${data.model} · local` : "Ollama needs attention · local";}).catch(()=>{$("model-status").textContent="Local connection unavailable";});
