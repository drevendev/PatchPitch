"use strict";
const $ = id => document.getElementById(id);
let changes = [], previewText = null, previewTimer, result = null, currentMarkdown = "", edited = false, busy = false;
const drafts = new Map();
let currentTags = [];
const formatNames = {devlog:"Devlog",community:"Community post",short:"Short post"};
const formatHints = {devlog:"The full story, with every selected topic.",community:"A few useful changes, in a post for your community.",short:"One useful thought. 280 characters including your CTA and tags."};
$("format").addEventListener("change", () => {$("format-hint").textContent=formatHints[$("format").value];$("tag-count-hint").textContent=$("format").value==="short" ? "up to 1" : "up to 3";});
// Animate disclosures in normal document flow, including rapid reversals.
// No captured image or text layer is scaled during a transition.
const disclosureAnimations = new WeakMap();
function closeDisclosure(details) {
  disclosureAnimations.get(details)?.animation.cancel();
  disclosureAnimations.delete(details);
  details.open = false; details.style.height = ""; details.style.overflow = "";
  if (details.id === "selection-panel") document.querySelector(".input-basics").inert = false;
  details.querySelector(":scope > summary")?.setAttribute("aria-expanded", "false");
}
document.addEventListener("click", event => {
  const summary = event.target.closest("summary");
  if (!summary || summary.parentElement.tagName !== "DETAILS") return;
  const details = summary.parentElement;
  event.preventDefault();
  const previous = disclosureAnimations.get(details);
  const opening = previous ? !previous.opening : !details.open;
  if (details.id === "selection-panel") document.querySelector(".input-basics").inert = opening;
  const start = details.getBoundingClientRect().height;
  if (previous) previous.animation.cancel();
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
    details.open = opening;
    details.style.height = ""; details.style.overflow = "";
    disclosureAnimations.delete(details);
    summary.setAttribute("aria-expanded", String(opening));
    return;
  }
  details.style.height = ""; details.style.overflow = "";
  details.open = opening;
  const end = details.getBoundingClientRect().height;
  details.open = true;
  details.style.overflow = "clip";
  summary.setAttribute("aria-expanded", String(opening));
  const animation = details.animate([{height:`${start}px`},{height:`${end}px`}], {
    duration:260, easing:"cubic-bezier(.22,.61,.36,1)", fill:"both"
  });
  const state = {animation, opening}; disclosureAnimations.set(details, state);
  animation.finished.then(() => {
    if (disclosureAnimations.get(details) !== state) return;
    details.open = opening;
    animation.cancel(); details.style.overflow = "";
    disclosureAnimations.delete(details);
  }).catch(() => {});
});
function selectionCount() {
  const included=changes.filter(change=>change.include).length;
  $("selection-count").textContent=`${included} selected · ${changes.length-included} excluded`;
}
function blockText(block) {return [block.text,...(block.retained_facts || [])].filter(Boolean).join(" ");}
function error(message) { $("error").textContent = message; $("error").hidden = !message; }
async function jsonRequest(path, body) {
  const response = await fetch(path, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  const data = await response.json();
  if (!response.ok) {
    const extraVoice=Array.isArray(data.detail) && data.detail.some(item=>item.type==="extra_forbidden" && item.loc?.some(part=>["voice_reference","format","style","auto_tags"].includes(part)));
    if(extraVoice) throw new Error("The local server is running an older version. Restart PatchPitch, then try again; your input is still here.");
    const fields=Array.isArray(data.detail) ? data.detail.map(item=>`${item.loc?.slice(1).join(" / ") || "Input"}: ${item.msg}`).join(" · ") : "";
    throw new Error(data.error?.message || (typeof data.detail === "string" ? data.detail : fields || "Review the selected changes and confirmation."));
  }
  return data;
}
async function prepare() {
  const text = $("changes").value;
  if (text === previewText) return;
  if (!text.trim()) {changes = []; $("change-preview").replaceChildren(); $("selection-panel").hidden=true; previewText = text; return;}
  const data = await jsonRequest("/api/prepare", {text});
  if (text !== $("changes").value) return;
  previewText = text; changes = data.changes;
  $("confirmed").checked = false;
  $("change-preview").replaceChildren();
  $("selection-panel").hidden=false;
  for (const change of changes) {
    const row = document.createElement("div"); row.className = "change-card" + (change.include ? "" : " excluded");
    const top=document.createElement("div");top.className="change-card-top";
    const toggle=document.createElement("label");toggle.className="change-toggle";
    const check = document.createElement("input"); check.type = "checkbox"; check.checked = change.include; check.setAttribute("aria-label", `Include ${change.id}`);
    const name=document.createElement("span");name.className="change-name";
    const id=document.createElement("span");id.className="source-id";id.textContent=change.id;
    const clean=change.text.replace(/\[(planned|internal|blocked|unknown)\]\s*/ig, "");
    const first=clean.split(/\.\s/)[0];const title=first.length>68 ? first.slice(0,65).trim()+"…" : first;
    name.append(id,document.createTextNode(title));
    const badge=document.createElement("span");badge.className="change-badge";badge.textContent=change.include ? "Included" : "Left out";
    check.addEventListener("change", () => {change.include = check.checked;row.classList.toggle("excluded", !check.checked);badge.textContent=check.checked ? "Included" : "Left out";$("confirmed").checked=false;selectionCount();});
    toggle.append(check);top.append(toggle,name,badge);
    const original=document.createElement("details");original.className="change-original";
    const summary=document.createElement("summary");summary.textContent="Read original note";
    const text=document.createElement("p");text.textContent=change.text;original.append(summary,text);
    row.append(top,original);
    if (change.reason) {const reason=document.createElement("p");reason.className="reason";reason.textContent=change.reason+" · excluded by default";row.append(reason);}
    $("change-preview").append(row);
  }
  selectionCount();
}
$("changes").addEventListener("input", () => {clearTimeout(previewTimer); $("confirmed").checked = false; previewTimer = setTimeout(() => prepare().catch(e => error(e.message)), 250);});
$("example").addEventListener("click", async () => {
  if (edited && !confirm("Replace the input with the illustrative example? Your current draft will stay visible.")) return;
  try {
    const response=await fetch("/static/example.json");
    if(!response.ok) throw new Error("The example could not be loaded. Your current input is still here.");
    const data=await response.json();
    const fields={product:data.product.name,description:data.product.description,audience:data.audience,release:data.release_label,voice:data.voice_reference || "",changes:data.changes.map(c=>c.text).join("\n"),cta:data.cta_text};
    for(const [id,value] of Object.entries(fields)) $(id).value=value;
    $("example-label").textContent=`Code-patch input · ${data.product.name} ${data.release_label} · review the selected facts before generating.`;
    $("example-label").hidden=false;error("");await prepare();
  } catch(e) {error(e.message);}
});
function setBusy(value) {
  busy = value; $("generate").disabled = value; $("example").disabled = value;
  $("pitch-form").setAttribute("aria-busy", String(value));
  for (const control of $("pitch-form").querySelectorAll("input,textarea,select")) control.disabled = value;
  for (const control of document.querySelectorAll("#edit,#editor,#tag-chips button,#saved-drafts button")) control.disabled=value;
}
$("generate").addEventListener("click",()=>{closeDisclosure($("selection-panel"));});
function saveCurrent() {
  if (result) drafts.set(result.presentation?.format || "devlog", {data:result,markdown:currentMarkdown,tags:[...currentTags],edited,editing:!$("editor").hidden});
}
function characterCount() {
  const limit=result?.presentation?.limit;
  $("character-count").hidden=!limit;
  const count=Array.from(currentMarkdown.trimEnd().replaceAll("&lt;","<").replaceAll("&gt;",">")).length;
  $("character-count").textContent=limit ? `${count} / ${limit} characters${count>limit ? " · over limit" : ""}` : "";
  $("character-count").classList.toggle("over-limit",Boolean(limit && count>limit));
}
function showTagChips() {
  $("tag-chips").replaceChildren();$("tag-tools").hidden=!currentTags.length || !$("editor").hidden;
  for (const tag of currentTags) {
    const chip=document.createElement("button");chip.type="button";chip.textContent=`${tag} ×`;chip.setAttribute("aria-label",`Remove ${tag}`);chip.disabled=busy;
    chip.addEventListener("click",()=>{
      if(busy)return;
      currentTags=currentTags.filter(t=>t!==tag);
      currentMarkdown=(result.body_markdown || result.markdown).trimEnd()+(currentTags.length ? "\n\n"+currentTags.join(" ") : "")+"\n";
      edited=true;$("edited-label").hidden=false;showTagChips();characterCount();saveCurrent();
    });
    $("tag-chips").append(chip);
  }
}
function render(data, saved=null) {
  result = data; currentMarkdown = saved?.markdown ?? data.markdown; edited = saved?.edited ?? false;
  currentTags=[...(saved?.tags ?? data.draft.hashtags ?? [])];
  $("empty-state").hidden = true; $("result").hidden = false; $("result-tools").hidden = false;
  $("editor").hidden = true; $("editor-label").hidden = true; $("draft-view").hidden = false; $("edited-label").hidden = true; $("edit").textContent = "Edit draft";
  $("timing").textContent = `${data.meta.model} · ${data.meta.elapsed_seconds.toFixed(1)}s · generated locally`;
  $("output-preset").textContent=data.presentation ? `${data.presentation.format_label} / ${data.presentation.style_label}` : "";
  $("draft-view").replaceChildren();
  if(data.presentation && data.presentation.format!=="devlog") {
    const prose=document.createElement("p");prose.className="post-prose";prose.textContent=data.draft.text;$("draft-view").append(prose);
  } else {
  const title = document.createElement("h3"); title.textContent = blockText(data.draft.title);
  const intro = document.createElement("p"); intro.textContent = blockText(data.draft.intro);
  const list = document.createElement("ul");
  for (const block of data.draft.highlights) {
    const item = document.createElement("li"), text = blockText(block);
    if (text.length > 380) {
      const disclosure=document.createElement("details"); disclosure.className="highlight";
      const heading=document.createElement("summary"), prose=document.createElement("span"), hint=document.createElement("span");
      prose.className="highlight-text";prose.textContent=text;
      hint.className="highlight-hint";hint.setAttribute("aria-hidden","true");
      heading.append(prose,hint);disclosure.append(heading);item.append(disclosure);
    } else item.textContent=text;
    list.append(item);
  }
  $("draft-view").append(title,intro,list);
  if (data.draft.details?.length) {
    const more=document.createElement("details");more.className="more-changes";
    const heading=document.createElement("summary");heading.textContent="Also in this update";
    const count=document.createElement("span");count.textContent=`${data.draft.details.length} more changes ＋`;heading.append(count);
    const details=document.createElement("ul");details.className="draft-details";
    for (const block of data.draft.details) {const item=document.createElement("li");item.textContent=blockText(block);details.append(item);}
    more.append(heading,details);$("draft-view").append(more);
  }
  if (data.draft.note) {const note = document.createElement("p");note.className="draft-note";note.textContent = blockText(data.draft.note);$("draft-view").append(note);}
  }
  if (data.presentation?.cta_text) {const cta = document.createElement("p");cta.className="draft-cta";cta.textContent = data.presentation.cta_text;$("draft-view").append(cta);}
  const warnings=data.warnings.filter(warning=>!(data.presentation?.format!=="devlog" && data.omitted_source_ids?.length && warning.startsWith("Selected facts not referenced")));
  $("warnings").replaceChildren(); $("warnings").hidden = !warnings.length;
  for (const warning of warnings) {const p=document.createElement("p");p.textContent=warning;$("warnings").append(p);}
  if(data.presentation?.format!=="devlog" && data.omitted_source_ids?.length) {
    const omitted=document.createElement("p");omitted.className="omission-note";omitted.textContent=`Not referenced in this ${data.presentation.format_label.toLowerCase()}: ${data.omitted_source_ids.join(", ")}. Short formats do not cover every detail; review the cited notes too.`;$("draft-view").append(omitted);
  }
  $("source-list").replaceChildren();
  const sourceUses=new Map();
  for (const mapping of data.source_map) for (const id of mapping.source_ids) {if(!sourceUses.has(id))sourceUses.set(id,[]);sourceUses.get(id).push(mapping.block);}
  for (const [id,uses] of sourceUses) {
    const section=document.createElement("section"), heading=document.createElement("h4");heading.textContent=`${id} · ${uses.join(" / ")}`;
    const original=document.createElement("details"), summary=document.createElement("summary"), text=document.createElement("p");summary.textContent="Read source note";text.textContent=data.sources[id];original.append(summary,text);section.append(heading,original);$("source-list").append(section);
  }
  if(saved?.editing) openEditor();
  $("edited-label").hidden=!edited;showTagChips();characterCount();saveCurrent();
  $("saved-drafts").replaceChildren();$("saved-drafts").hidden=drafts.size<2;
  for(const [format,state] of drafts) {
    const button=document.createElement("button");button.type="button";button.textContent=formatNames[format];button.disabled=busy;button.setAttribute("aria-pressed",String(format===(data.presentation?.format||"devlog")));
    button.addEventListener("click",()=>{if(busy)return;saveCurrent();const latest=drafts.get(format);render(latest.data,latest);});$("saved-drafts").append(button);
  }
}
$("pitch-form").addEventListener("submit", async event => {
  event.preventDefault(); if (busy) return;
  error("");
  try {
    await prepare();
    if (!$("confirmed").checked) throw new Error("Review the selected changes and confirm they belong in this announcement.");
    saveCurrent();
    if (drafts.get($("format").value)?.edited && !confirm("Generate a new draft and replace your edited text? Copy or download it first if you want to keep it.")) return;
    const body = {product:{name:$("product").value,description:$("description").value},audience:$("audience").value,release_label:$("release").value,voice_reference:$("voice").value,changes:changes.map(({id,text,include}) => ({id,text,include})),cta_text:$("cta").value,format:$("format").value,style:$("style").value,auto_tags:$("auto-tags").checked,confirmed:true};
    setBusy(true); const start = performance.now(); $("status").textContent="Writing with local Gemma… 0.0s";
    const timer = setInterval(() => $("status").textContent=`Writing with local Gemma… ${((performance.now()-start)/1000).toFixed(1)}s`, 200);
    try {const data = await jsonRequest("/api/pitch",body);render(data);$("status").textContent="Your draft is ready to review. Nothing has been published.";}
    finally {clearInterval(timer);setBusy(false);}
  } catch (e) {error(e.message);$("status").textContent="Your input and any previous draft are still here.";}
});
function openEditor() {
  if (!result || busy) return;
  $("editor").value=currentMarkdown;$("editor").hidden=false;$("editor-label").hidden=false;$("draft-view").hidden=true;$("edited-label").hidden=false;$("edit").textContent="Editing Markdown";edited=true;$("editor").focus();
  $("tag-tools").hidden=true;
}
$("edit").addEventListener("click",openEditor);
$("editor").addEventListener("input", () => {if(busy)return;currentMarkdown=$("editor").value;edited=true;characterCount();saveCurrent();});
$("copy").addEventListener("click", async () => {try {await navigator.clipboard.writeText(currentMarkdown);$("status").textContent="Markdown copied. Ready for your final review.";} catch {error("Clipboard unavailable. Use Download Markdown or copy from Edit draft.");}});
$("download").addEventListener("click", () => {const url=URL.createObjectURL(new Blob([currentMarkdown],{type:"text/markdown;charset=utf-8"}));const link=document.createElement("a");link.href=url;link.download="patchpitch-announcement.md";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$("status").textContent="Markdown downloaded. Nothing has been published.";});
fetch("/api/health").then(r=>r.json()).then(data => {$("model-status").textContent=data.ollama==="ready" ? `${data.model} · local` : "Ollama needs attention · local";}).catch(()=>{$("model-status").textContent="Local connection unavailable";});
