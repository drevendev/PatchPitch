"use strict";
const $ = id => document.getElementById(id);
let changes = [], previewText = null, previewTimer, result = null, currentMarkdown = "", edited = false, busy = false;
const drafts = new Map();
let currentTags = [];
let packContext = null, socialPosts = [], unloadProtected = false;
const isSocial = format => ["x_single","x_thread"].includes(format);
const formatNames = {devlog:"Devlog",community:"Community post",short:"Short post",x_single:"X Single",x_thread:"X Thread"};
const formatHints = {devlog:"The full story, with every selected topic.",community:"A few useful changes, in a post for your community.",short:"One useful thought. 280 characters including your CTA and tags.",x_single:"One concrete thought. Edit, check sources and verify in X.",x_thread:"A connected story. Each card stays independently editable."};
$("format").addEventListener("change", () => {const social=isSocial($("format").value);$("format-hint").textContent=formatHints[$("format").value];$("tag-count-hint").textContent=social?"off for X":$("format").value==="short" ? "up to 1" : "up to 3";$("social-options").hidden=!social;$("post-count-row").hidden=$("format").value!=="x_thread";$("auto-tags").disabled=social;});
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
    const failure = new Error(data.error?.message || (typeof data.detail === "string" ? data.detail : fields || "Review the selected changes and confirmation."));
    failure.code=data.error?.code || "request_failed";failure.httpStatus=response.status;failure.evidence=data.evidence ?? null;
    throw failure;
  }
  return data;
}
async function prepare() {
  const text = $("changes").value;
  if (text === previewText) return;
  if (!text.trim()) {changes = []; $("change-preview").replaceChildren(); $("selection-panel").hidden=true; previewText = text; return;}
  const data = await jsonRequest("/api/prepare", {text});
  if (text !== $("changes").value) return;
  applyPrepared(text, data);
}
function applyPrepared(text, data) {
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
    const ref=packContext?.source_references?.find(r=>r.api_id===change.id);
    if(ref){const source=document.createElement("p");source.textContent=`${ref.stable_id} · ${ref.source_ref}`;original.append(source);if(ref.source_url){const a=document.createElement("a");a.href=ref.source_url;a.textContent="Inspect source ↗";a.target="_blank";a.rel="noopener noreferrer";original.append(a);}}
    row.append(top,original);
    if (change.reason) {const reason=document.createElement("p");reason.className="reason";reason.textContent=change.reason+" · excluded by default";row.append(reason);}
    $("change-preview").append(row);
  }
  selectionCount();
}
$("changes").addEventListener("input", () => {clearTimeout(previewTimer);packContext=null;$("pack-status").textContent="Manually edited notes. Review provenance and confirm the new selection."; $("confirmed").checked = false; previewTimer = setTimeout(() => prepare().catch(e => error(e.message)), 250);});
$("example").addEventListener("click", async () => {
  if (busy) return;
  if (edited && !confirm("Replace the input with the illustrative example? Your current draft will stay visible.")) return;
  setBusy(true); $("status").textContent="Loading the example…";
  try {
    const response=await fetch("/static/example.json");
    if(!response.ok) throw new Error("The example could not be loaded. Your current input is still here.");
    const data=await response.json();
    const fields={product:data.product.name,description:data.product.description,audience:data.audience,release:data.release_label,voice:data.voice_reference || "",changes:data.changes.map(c=>c.text).join("\n"),cta:data.cta_text};
    // Reserve loading through preparation, then replace the input atomically.
    // A failed fetch/prepare leaves the current form and draft untouched.
    const prepared=await jsonRequest("/api/prepare", {text:fields.changes});
    packContext=null;
    for(const [id,value] of Object.entries(fields)) $(id).value=value;
    applyPrepared(fields.changes, prepared);
    $("example-label").textContent=`Code-patch input · ${data.product.name} ${data.release_label} · review the selected facts before generating.`;
    $("example-label").hidden=false;error("");
    $("status").textContent="Example loaded. Review the selected facts before generating.";
  } catch(e) {error(e.message);$("status").textContent="Your input and any previous draft are still here.";}
  finally {setBusy(false);}
});
function setBusy(value) {
  busy = value; $("generate").disabled = value; $("example").disabled = value;
  $("pitch-form").setAttribute("aria-busy", String(value));
  for (const control of $("pitch-form").querySelectorAll("input,textarea,select")) control.disabled = value;
  for (const control of document.querySelectorAll("#edit,#editor,#tag-chips button,#saved-drafts button")) control.disabled=value;
  for (const control of document.querySelectorAll("#load-pack,#fact-pack,#pack-file,#social-posts button,#social-posts textarea,#social-posts input")) control.disabled=value || control.dataset.boundaryDisabled==="true";
  if(!value && isSocial($("format").value)) $("auto-tags").disabled=true;
}
$("generate").addEventListener("click",()=>{closeDisclosure($("selection-panel"));});
function saveCurrent() {
  if (result) {
    result.context ||= {product:$("product").value,release_label:$("release").value,generated_at:new Date().toISOString()};
    drafts.set(contextKey(result.presentation?.format || "devlog",result.context), {data:result,markdown:currentMarkdown,tags:[...currentTags],edited,editing:!$("editor").hidden,posts:structuredClone(socialPosts)});
    $("storage-hint").hidden=false;
    if(!unloadProtected){window.addEventListener("beforeunload",warnUnload);unloadProtected=true;}
  }
}
function warnUnload(event){if(!drafts.size && !generationRecords.length)return;event.preventDefault();event.returnValue=true;}
function contextKey(format,context={product:$("product").value,release_label:$("release").value}){return JSON.stringify([context.product,context.release_label,format]);}
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
  if(isSocial(data.presentation?.format)){renderSocial(data,saved);return;}
  result = data; currentMarkdown = saved?.markdown ?? data.markdown; edited = saved?.edited ?? false;
  socialPosts=[];$("social-posts").hidden=true;$("edit").hidden=false;$("copy").textContent="Copy Markdown";$("download").textContent="Download Markdown ↓";
  currentTags=[...(saved?.tags ?? data.draft.hashtags ?? [])];
  $("empty-state").hidden = true; $("result").hidden = false; $("result-tools").hidden = false;
  $("editor").hidden = true; $("editor-label").hidden = true; $("draft-view").hidden = false; $("edited-label").hidden = true; $("edit").textContent = "Edit draft";
  $("timing").textContent = `${data.meta.returned_model ?? data.meta.model ?? "Model identity unknown"} · ${data.meta.elapsed_seconds.toFixed(1)}s · generated locally`;
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
  renderSavedButtons();
}
$("pitch-form").addEventListener("submit", async event => {
  event.preventDefault(); if (busy) return;
  let submittedBody=null, started=null;
  setBusy(true); error("");
  try {
    await prepare();
    if (!$("confirmed").checked) throw new Error("Review the selected changes and confirm they belong in this announcement.");
    saveCurrent();
    if (drafts.get(contextKey($("format").value))?.edited && !confirm("Generate a new draft and replace your edited text? Copy or download it first if you want to keep it.")) return;
    const body = {product:{name:$("product").value,description:$("description").value},audience:$("audience").value,release_label:$("release").value,voice_reference:$("voice").value,changes:changes.map(({id,text,include}) => ({id,text,include})),cta_text:$("cta").value,format:$("format").value,style:$("style").value,auto_tags:$("auto-tags").checked,confirmed:true};
    const social=isSocial(body.format);
    if(social){Object.assign(body,{auto_tags:false,intent:$("intent").value,post_count:Number($("post-count").value)});if(packContext)for(const k of ["source_references","pack_id","pack_version","pack_sha256"])body[k]=packContext[k];}
    setBusy(true); const start = performance.now(); $("status").textContent="Writing with local Gemma… 0.0s";
    submittedBody=body;started=start;
    const timer = setInterval(() => $("status").textContent=`Writing with local Gemma… ${((performance.now()-start)/1000).toFixed(1)}s`, 200);
    try {const data = await jsonRequest(social?"/api/social":"/api/pitch",body);rememberGeneration(body,{response:data},start);data.media_note=$("media-note").value;render(data);$("status").textContent="Your draft is ready to review. Nothing has been published.";}
    finally {clearInterval(timer);}
  } catch (e) {if(submittedBody)rememberGeneration(submittedBody,{error:e},started);error(e.message);$("status").textContent="Your input and any previous draft are still here. Review this attempt below or retry manually.";}
  finally {setBusy(false);}
});
function openEditor() {
  if (!result || busy) return;
  $("editor").value=currentMarkdown;$("editor").hidden=false;$("editor-label").hidden=false;$("draft-view").hidden=true;$("edited-label").hidden=false;$("edit").textContent="Editing Markdown";edited=true;$("editor").focus();
  $("tag-tools").hidden=true;
}
$("edit").addEventListener("click",openEditor);
$("editor").addEventListener("input", () => {if(busy)return;currentMarkdown=$("editor").value;edited=true;characterCount();saveCurrent();});
$("copy").addEventListener("click", () => copyText(isSocial(result?.presentation?.format)?socialPlain():currentMarkdown));
$("download").addEventListener("click", () => {const url=URL.createObjectURL(new Blob([currentMarkdown],{type:"text/markdown;charset=utf-8"}));const link=document.createElement("a");link.href=url;link.download=exportName(result);link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$("status").textContent="Markdown downloaded. Nothing has been published.";});
fetch("/api/health").then(r=>r.json()).then(data => {$("model-status").textContent=data.ollama==="ready" ? `${data.model} · local` : "Ollama needs attention · local";}).catch(()=>{$("model-status").textContent="Local connection unavailable";});
