"use strict";

async function loadFactPack(file=null) {
  if(busy)return;
  if($("product").value && !confirm("Replace the input facts? Existing drafts stay available in this tab."))return;
  setBusy(true);error("");
  try {
    let data;
    if(file){if(file.size>32000)throw new Error("Fact-pack JSON must be at most 32 KB.");data=await jsonRequest("/api/fact-packs/prepare",JSON.parse(await file.text()));}
    else {const response=await fetch(`/api/fact-packs/${encodeURIComponent($("fact-pack").value)}`);if(!response.ok)throw new Error("The fact pack could not be loaded.");data=await response.json();}
    packContext=data;$("media-note").value="";$("writing-goal").value="release";
    const fields={product:data.product.name,description:data.product.description,audience:data.audience,release:data.release_label,voice:data.voice_reference,cta:data.cta_text,changes:data.changes.map(c=>c.text).join("\n")};
    for(const [id,value] of Object.entries(fields))$(id).value=value;
    applyPrepared(fields.changes,data);
    $("pack-status").textContent=`${data.pack_id} / ${data.pack_version} · review facts, sources and the voice brief; confirmation required.`;
    $("example-label").hidden=true;$("status").textContent="Facts loaded. Review the selected notes before generating.";
  } catch(e){error(e.message);$("status").textContent="Input and previous drafts were not replaced.";}
  finally {setBusy(false);$("pack-file").value="";}
}
$("load-pack").addEventListener("click",()=>loadFactPack());
$("pack-file").addEventListener("change",()=>{const file=$("pack-file").files[0];if(file)loadFactPack(file);});

function renderSavedButtons(){
  $("saved-drafts").replaceChildren();$("saved-drafts").hidden=drafts.size<2;
  const products=new Set([...drafts.values()].map(s=>s.data.context.product));
  const active=contextKey(result.presentation?.format||"devlog",result.context);
  for(const [key,state] of drafts){
    const button=document.createElement("button");button.type="button";
    const fmt=state.data.presentation?.format||"devlog";
    const ambiguous=[...drafts.values()].filter(v=>v.data.context.product===state.data.context.product && (v.data.presentation?.format||"devlog")===fmt).length>1;
    button.textContent=(products.size>1?state.data.context.product+" · ":"")+formatNames[fmt]+(ambiguous?" · "+(state.data.context.release_label||"Unversioned"):"");
    button.disabled=busy;button.setAttribute("aria-pressed",String(key===active));
    button.addEventListener("click",()=>{if(busy)return;saveCurrent();const latest=drafts.get(key);render(latest.data,latest);});
    $("saved-drafts").append(button);
  }
}

function exportName(data){
  const slug=value=>{let s=String(value||"").normalize("NFKC").toLowerCase().replace(/[^\p{L}\p{N}-]+/gu,"-").replace(/^-+|-+$/g,"").slice(0,55);if(/^(con|prn|aux|nul|com[1-9]|lpt[1-9])$/i.test(s))s="draft-"+s;return s||"draft";};
  const context=data?.context||{};
  const stamp=new Date(context.generated_at||Date.now()).toISOString().replace(/[-:]/g,"").replace(/\.\d+Z$/,"Z");
  return [slug(context.product||"patchpitch"),slug(context.release_label||"unversioned"),slug(data?.presentation?.format||"announcement"),stamp].join("-")+".md";
}
async function copyText(text){
  try {await navigator.clipboard.writeText(text);$("status").textContent="Copied. Review the final text before publishing.";}
  catch {error("Clipboard unavailable. Select text in the editor and copy manually, or use Download Markdown.");}
}
function socialPlain(){return socialPosts.length===1?socialPosts[0].text:socialPosts.map((p,i)=>`${i+1}/${socialPosts.length}\n${p.text}`).join("\n\n");}
function socialMarkdown(){return socialPosts.map((p,i)=>`## Post ${i+1} of ${socialPosts.length}\n\n${p.text}`+(p.media_note?`\n\nMedia note (not post text): ${p.media_note}`:"")).join("\n\n---\n\n")+"\n";}
function saveSocial(){
  currentMarkdown=socialMarkdown();
  result.source_map=socialPosts.map(p=>({block:p.id,source_ids:[...p.source_ids]}));
  const used=new Set(socialPosts.flatMap(p=>p.source_ids));
  result.omitted_source_ids=Object.keys(result.sources).filter(id=>!used.has(id));
  $("edited-label").hidden=!edited;saveCurrent();
}
function renderSocial(data,saved=null){
  result=data;edited=saved?.edited??false;currentTags=[];
  socialPosts=structuredClone(saved?.posts??data.draft.posts.map((p,i)=>({...p,media_note:i===0?data.media_note||"":"",edited:false,local_record_id:data.local_record_id})));
  for(const id of ["empty-state","draft-view","tag-tools","editor","editor-label","character-count","edit"])$(id).hidden=true;
  for(const id of ["result","result-tools","social-posts"])$(id).hidden=false;
  $("timing").textContent=`${data.meta.returned_model??data.meta.model??"Model identity unknown"} · ${data.meta.elapsed_seconds.toFixed(1)}s · local`;
  $("output-preset").textContent=`${data.context.product} · ${data.context.release_label || "Unversioned"} · ${data.presentation.format_label} / ${data.presentation.style_label}`;
  $("copy").textContent=socialPosts.length===1?"Copy post":"Copy whole thread";$("download").textContent="Download Markdown ↓";
  renderSocialWarnings();
  renderSocialCards();renderSocialSources();saveSocial();renderSavedButtons();if(typeof syncGitButtons==="function")syncGitButtons();
}
function renderSocialSources(){renderSourceSnapshot(result.source_snapshot || []);}
function renderSourceSnapshot(snapshots){
  $("source-list").replaceChildren();
  for(const snapshot of snapshots){
    const section=document.createElement("section");section.id="source-"+snapshot.api_id;
    const h=document.createElement("h4");h.textContent=`${snapshot.api_id} → ${snapshot.stable_id} · ${snapshot.include?"selected":"excluded"}`;
    const p=document.createElement("p");p.textContent=snapshot.text;
    const ref=document.createElement("p");ref.textContent=snapshot.source_ref;
    section.append(h,p,ref);
    if(snapshot.source_url){const a=document.createElement("a");a.href=snapshot.source_url;a.textContent="Inspect provenance ↗";a.target="_blank";a.rel="noopener noreferrer";section.append(a);}
    $("source-list").append(section);
  }
}
function renderSocialCards(){
  $("social-posts").replaceChildren();
  socialPosts.forEach((post,index)=>{
    const card=document.createElement("section");card.className="social-card";card.dataset.postId=post.id;
    const label=document.createElement("label");label.htmlFor="text-"+post.id;label.textContent=`Post ${index+1} of ${socialPosts.length} · ${post.id}`;
    const textarea=document.createElement("textarea");textarea.id="text-"+post.id;textarea.className="social-text";textarea.value=post.text;textarea.disabled=busy;textarea.maxLength=2200;
    const count=document.createElement("p");count.className="helper social-count";count.setAttribute("aria-live","polite");
    const updateCount=()=>{const c=socialLength(post.text);count.textContent=`~${c.characters} / 280 · estimate · ${c.over_limit?"over limit — edit before publishing":"verify in X"}`;count.classList.toggle("over-limit",c.over_limit);};updateCount();
    textarea.addEventListener("input",()=>{if(busy)return;post.text=textarea.value;post.edited=true;edited=true;updateCount();saveSocial();});
    const refs=document.createElement("p");refs.className="helper";refs.textContent="Generated sources: "+post.source_ids.join(", ")+" · recheck after edits.";
    const actions=document.createElement("div");actions.className="card-actions";
    function button(text,fn,disabled=false){const b=document.createElement("button");b.type="button";b.textContent=text;b.className="secondary";b.dataset.boundaryDisabled=String(disabled);b.disabled=busy||disabled;b.addEventListener("click",fn);actions.append(b);return b;}
    button("Copy this post",async()=>{try{await checkSocialExport();await copyText(post.text);}catch(e){error(e.message);}});
    const move=delta=>{if(busy)return;const target=index+delta;[socialPosts[index],socialPosts[target]]=[socialPosts[target],socialPosts[index]];edited=true;renderSocialCards();saveSocial();$("text-"+post.id).focus();};
    if(socialPosts.length>1){button("Move up",()=>move(-1),index===0);button("Move down",()=>move(1),index===socialPosts.length-1);}
    button("Regenerate this post",()=>regeneratePost(post.id));
    button("Review sources",()=>{$("sources").open=true;$("source-"+post.source_ids[0])?.scrollIntoView({block:"nearest",behavior:"instant"});$("sources").querySelector("summary").focus();});
    const mediaLabel=document.createElement("label");mediaLabel.htmlFor="media-"+post.id;mediaLabel.className="helper";mediaLabel.textContent="Media note · outside post text";
    const media=document.createElement("input");media.id="media-"+post.id;media.value=post.media_note||"";media.maxLength=500;media.disabled=busy;
    media.addEventListener("input",()=>{if(busy)return;post.media_note=media.value;edited=true;saveSocial();});
    card.append(label,textarea,count,refs,actions,mediaLabel,media);$("social-posts").append(card);
  });
}
async function regeneratePost(id){
  if(busy||!confirm("Replace this post with a new draft? The other posts and their edits will stay unchanged."))return;
  const post=socialPosts.find(p=>p.id===id),previousResult=result;
  const request=structuredClone(result.input_snapshot);
  request.operation="regenerate";request.target_post_id=id;
  request.thread_context=socialPosts.map(p=>({id:p.id,text:p.text,source_ids:p.source_ids}));
  // Keep a CTA only on the card where the author currently has that exact CTA.
  request.cta_text=request.cta_text&&post.text.endsWith("\n\n"+request.cta_text)?request.cta_text:"";
  setBusy(true);error("");$("status").textContent=`Rewriting ${id} with local Gemma…`;
  const started=performance.now();
  try{
    const data=await jsonRequest("/api/social",request);
    rememberGeneration(request,{response:data},started);
    if(result!==previousResult)throw new Error("Draft changed; the new response was not applied.");
    const replacement=data.draft.posts[0];
    Object.assign(post,{...replacement,edited:false,local_record_id:data.local_record_id});
    (result.regenerations ||= []).push(data);
    result.source_map=socialPosts.map(p=>({block:p.id,source_ids:[...p.source_ids]}));
    const used=new Set(socialPosts.flatMap(p=>p.source_ids));
    result.omitted_source_ids=Object.keys(result.sources).filter(id=>!used.has(id));
    result.current_warnings=data.warnings.map(w=>`${id} rewrite: ${w}`);
    renderSocialWarnings();
    edited=true;renderSocialCards();saveSocial();$("status").textContent=`${id} regenerated. Other cards unchanged. Review the new wording and verify in X.`;
  }catch(e){rememberGeneration(request,{error:e},started);error(e.message);$("status").textContent="All previous posts, media notes and edits remain unchanged. Review this attempt below or retry manually.";}
  finally{setBusy(false);renderSocialCards();$("text-"+id)?.focus();}
}

function renderSocialWarnings(){
  $("warnings").replaceChildren();
  const warnings=["Estimated X lengths — verify in the X composer. Source links are review aids, not proof of factual accuracy."];
  if(result.regenerations?.length){
    warnings.push("Other cards and manual edits have not been revalidated. Earlier warnings below describe their original attempts.");
    warnings.push(...(result.current_warnings||[]));
    for(const w of result.warnings||[])warnings.push("Original generation (historical): "+w);
    for(const [i,attempt] of result.regenerations.slice(0,-1).entries())for(const w of attempt.warnings||[])warnings.push(`Earlier rewrite ${i+1} (historical): ${w}`);
  }else warnings.push(...(result.warnings||[]));
  if(result.omitted_source_ids?.length)warnings.push("Selected sources not referenced: "+result.omitted_source_ids.join(", ")+". Check necessary caveats.");
  for(const warning of warnings){const p=document.createElement("p");p.textContent=warning;$("warnings").append(p);}
  $("warnings").hidden=false;
}

function showCatalog(){
  $("x-catalog-status").textContent=xCatalog?`${xCatalog.id} / ${xCatalog.version} · ${xCatalog.tags.length} candidates. Dated evidence and relevance are checked for every post.`:"Load a catalog with dated observations to prepare six relevant tags per X post.";
}
$("x-catalog").addEventListener("change",async()=>{
  const file=$("x-catalog").files[0];if(!file||busy)return;
  setBusy(true);error("");
  try{if(file.size>1000000)throw new Error("X catalogs must be at most 1 MB.");const candidate=JSON.parse(await file.text());await jsonRequest("/api/hashtags/validate",candidate);xCatalog=candidate;$("legacy-x").checked=false;$("confirmed").checked=false;showCatalog();protectSession();}
  catch(e){error(e.message);}finally{setBusy(false);$("x-catalog").value="";}
});
async function checkSocialExport(){
  if(result?.input_snapshot?.hashtag_policy!=="x-six-v1")return;
  await jsonRequest("/api/hashtags/check",{input_snapshot:result.input_snapshot,posts:socialPosts});
}
showCatalog();
