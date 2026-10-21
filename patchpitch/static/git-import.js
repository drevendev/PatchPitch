"use strict";

let gitState={inspection:null,preview:null,facts:null,record:null};
let publicationMarkers={};
const gitFieldIds=["git-repo","git-mode","git-count","git-base","git-head","git-path"];
function gitControls(){return Object.fromEntries(gitFieldIds.map(id=>[id,$(id).value]));}
function hasGitContent(){return Boolean($("git-repo").value||gitState.inspection||gitState.record||Object.keys(publicationMarkers).length);}
function gitSelection(){return [...document.querySelectorAll("#git-files input:checked")].map(e=>e.value);}
function syncGitButtons(){
  $("git-preview").disabled=busy||!gitState.inspection||!gitSelection().length;
  $("git-reviewed").disabled=busy||!gitState.preview;
  $("git-extract").disabled=busy||!gitState.preview||!$("git-reviewed").checked;
  $("git-apply").disabled=busy||!gitState.facts;
  $("git-download-record").disabled=busy||!gitState.record;
  $("record-publication").disabled=busy||!result?.context?.source_context?.repository_id;
}
function invalidateGitPreview(){gitState.preview=null;gitState.facts=null;$("git-reviewed").checked=false;$("git-diffs").replaceChildren();$("git-candidates").replaceChildren();syncGitButtons();}
for(const id of gitFieldIds)$(id).addEventListener("input",()=>{gitState.inspection=null;$("git-files").replaceChildren();invalidateGitPreview();$("git-summary").textContent="Inspect this range to review its committed changes.";});

async function inspectGit(){
  if(busy)return;
  setBusy(true);error("");
  try{
    const mode=$("git-mode").value;
    const body={repo_path:$("git-repo").value,mode:mode==="published"?"recent":mode,count:Number($("git-count").value),base:$("git-base").value,head:$("git-head").value,path_filter:$("git-path").value};
    if(mode==="published")body.count=1;
    let data=await jsonRequest("/api/git/inspect",body);
    if(mode==="published"){
      const marker=publicationMarkers[data.repository_id];
      if(!marker)throw new Error("No manual publication marker is saved for this repository. Choose a recent or explicit range first.");
      data=await jsonRequest("/api/git/inspect",{...body,mode:"range",base:marker.head});
    }
    gitState.inspection=data;invalidateGitPreview();
    protectSession();
    renderGitInspection(data);
    $("status").textContent="Git range inspected without inference. Select eligible files, then review their diffs.";
  }catch(e){error(e.message);}
  finally{setBusy(false);}
}
function gitRequest(){
  return {repo_path:$("git-repo").value,base:gitState.inspection.base,head:gitState.inspection.head,files:gitSelection(),path_filter:gitState.inspection.path_filter};
}
async function previewGit(){
  if(busy||!gitState.inspection)return;
  setBusy(true);error("");
  try{
    const data=await jsonRequest("/api/git/preview",gitRequest());
    if(gitState.preview?.preview_sha256!==data.preview_sha256){gitState.facts=null;$("git-candidates").replaceChildren();}
    gitState.preview=data;$("git-reviewed").checked=false;
    renderGitDiffs(data);
    $("status").textContent="Selected diffs are ready for your review. No inference has run.";
  }catch(e){error(e.message);}
  finally{setBusy(false);}
}
async function extractGit(){
  if(busy||!gitState.preview||!$("git-reviewed").checked)return;
  if(gitState.facts && !confirm("Replace the current fact candidates? Download the session first to keep your edits."))return;
  const body={...gitRequest(),reviewed:true,preview_sha256:gitState.preview.preview_sha256};
  setBusy(true);error("");$("status").textContent="Proposing facts from the reviewed diffs with local Gemma…";
  const started=performance.now();
  const timer=setInterval(()=>{$("status").textContent=`Proposing facts with local Gemma… ${((performance.now()-started)/1000).toFixed(1)}s`;},250);
  try{
    const data=await jsonRequest("/api/git/facts",body);
    gitState.facts=data.facts.map(f=>({...f,current_text:f.text,include:false}));
    gitState.record={schema_version:1,kind:"patchpitch_git_review",source_context:data.source_context,evidence:data.evidence,response:data,status:"accepted_by_application"};
    renderGitCandidates();renderGitRecord();
    $("status").textContent="Fact candidates are ready. Read their cited diffs, edit the text and explicitly choose what to use.";
  }catch(e){gitState.record={schema_version:1,kind:"patchpitch_git_review",source_context:gitState.preview.source_context,evidence:gitState.preview.evidence,error:{code:e.code,message:e.message},response:e.evidence??null,status:"failed"};renderGitRecord();error(e.message);$("status").textContent="Fact extraction failed. Your previous candidates, input and writing drafts remain available; retry explicitly.";}
  finally{clearInterval(timer);setBusy(false);}
}
function renderGitRecord(){
  $("git-record").hidden=!gitState.record;
  $("git-record-raw").textContent=gitState.record?JSON.stringify(gitState.record,null,2):"";
}
function renderGitCandidates(){
  $("git-candidates").replaceChildren();
  for(const [index,fact] of gitState.facts.entries()){
    const card=document.createElement("section");card.className="git-candidate";
    const label=document.createElement("label"),check=document.createElement("input");check.type="checkbox";check.checked=fact.include;check.setAttribute("aria-label",`Use fact ${index+1}`);check.addEventListener("change",()=>{fact.include=check.checked;});label.append(check,document.createTextNode(` Fact ${index+1} · ${fact.kind} · ${fact.evidence_ids.join(", ")}`));
    const text=document.createElement("textarea");text.value=fact.current_text;text.maxLength=800;text.setAttribute("aria-label",`Review fact ${index+1}`);text.addEventListener("input",()=>{fact.current_text=text.value;});
    const refs=document.createElement("p");refs.className="helper";refs.textContent=fact.evidence_ids.map(id=>gitState.preview.evidence.find(e=>e.id===id)?.path).join(" · ");
    card.append(label,text,refs);$("git-candidates").append(card);
  }
}
function applyGitFacts(){
  if(busy||!gitState.facts)return;
  error("");
  const facts=gitState.facts;
  if(!facts.some(f=>f.include)){error("Choose at least one fact after reviewing it.");return;}
  if(facts.some(f=>!f.current_text.trim())||facts.reduce((n,f)=>n+Array.from(f.current_text).length,0)>6000){error("Use nonempty facts and at most 6,000 total characters.");return;}
  if($("changes").value&&!confirm("Replace the current input notes with these reviewed Git facts? Existing drafts stay available."))return;
  const context=gitState.preview.source_context;
  if(!$("product").value)$("product").value=context.repository;
  if(!$("description").value)$("description").value="A software project under development.";
  if(!$("audience").value)$("audience").value="People following this project's development";
  $("release").value=`Development ${context.head.slice(0,12)}`;$("writing-goal").value="development";$("format").value="devlog";$("format").dispatchEvent(new Event("change"));$("media-note").value="";
  const prepared=facts.map((f,i)=>({id:`C${String(i+1).padStart(2,"0")}`,text:f.current_text,include:f.include,reason:f.kind==="uncertain"?"Model inference — review against code":""}));
  const refs=facts.map((f,i)=>({api_id:prepared[i].id,stable_id:`G${String(i+1).padStart(2,"0")}`,source_url:"",
    source_ref:`Git ${context.base||"empty tree"}..${context.head}; ${f.evidence_ids.map(id=>id+" "+gitState.preview.evidence.find(e=>e.id===id).path).join("; ")}`.slice(0,600)}));
  packContext={product:{name:$("product").value,description:$("description").value},audience:$("audience").value,release_label:$("release").value,voice_reference:$("voice").value,cta_text:$("cta").value,changes:prepared,source_references:refs,pack_id:"",pack_version:"",pack_sha256:"",source_context:context,review_required:true};
  $("changes").value=prepared.map(c=>c.text).join("\n");applyPrepared($("changes").value,{changes:prepared});
  $("pack-status").textContent=`Reviewed Git selection · ${context.head.slice(0,12)} · committed work; publication and tests unverified.`;
  $("example-label").hidden=true;$("status").textContent="Git facts loaded. Review product context and confirm the selection to write your DevLog.";
}
function restoreGitControls(controls,markers,record=null,review=null){
  for(const id of gitFieldIds)$(id).value=controls[id]??({"git-mode":"recent","git-count":"10","git-head":"HEAD"}[id]||"");
  publicationMarkers=structuredClone(markers);gitState={inspection:null,preview:null,facts:null,record:structuredClone(record)};
  $("git-files").replaceChildren();$("git-diffs").replaceChildren();$("git-candidates").replaceChildren();$("git-reviewed").checked=false;
  if(review){
    gitState={inspection:structuredClone(review.inspection),preview:structuredClone(review.preview),facts:structuredClone(review.facts),record:structuredClone(review.record)};
    if(gitState.inspection)renderGitInspection(gitState.inspection,review.selected_files);
    if(gitState.preview)renderGitDiffs(gitState.preview);
    if(gitState.facts)renderGitCandidates();
  }
  if(!gitState.inspection)$("git-summary").textContent="Saved controls restored. Inspect explicitly to read Git again; existing draft sources stay attached.";renderGitRecord();syncGitButtons();
}
function recordPublication(){
  const context=result?.context?.source_context;
  if(busy||!context?.repository_id)return;
  let url;
  try{url=new URL($("published-url").value);if(!["http:","https:"].includes(url.protocol)||url.username||url.password)throw new Error();}
  catch{error("Enter the actual public URL of your manually published DevLog.");return;}
  if(!confirm(`Record ${context.head.slice(0,12)} as manually published? This updates the saved baseline in this tab and does not publish anything.`))return;
  publicationMarkers[context.repository_id]={head:context.head,url:url.href,published_at:new Date().toISOString()};
  $("status").textContent="Manual publication recorded. Download the session to keep this baseline for your next DevLog.";
}
$("git-inspect").addEventListener("click",inspectGit);$("git-preview").addEventListener("click",previewGit);
$("git-reviewed").addEventListener("change",syncGitButtons);$("git-extract").addEventListener("click",extractGit);
$("git-apply").addEventListener("click",applyGitFacts);$("record-publication").addEventListener("click",recordPublication);
$("git-download-record").addEventListener("click",()=>{if(gitState.record)downloadJSON(gitState.record,"patchpitch-git-review.json");});
syncGitButtons();

function renderGitInspection(data,selected=[]){
  $("git-summary").textContent=`${data.repository} · ${data.base||"empty tree"} → ${data.head} · ${data.commit_count} commits · ${data.worktree_dirty?"working-tree changes excluded":"clean working tree"}. ${data.note}`;
  $("git-files").replaceChildren();
  const log=document.createElement("details"),summary=document.createElement("summary"),pre=document.createElement("pre");summary.textContent="Inspect commit subjects · context, not verified facts";pre.textContent=data.commits.map(c=>`${c.sha} ${c.subject}`).join("\n");log.append(summary,pre);$("git-files").append(log);
  for(const file of data.files){const row=document.createElement("label");row.className="git-file";
    if(file.eligible){const check=document.createElement("input");check.type="checkbox";check.value=file.path;check.checked=selected.includes(file.path);check.setAttribute("aria-label","Use file "+file.path);check.addEventListener("change",()=>{if(gitSelection().length>12){check.checked=false;error("Choose at most 12 files for one fact pass.");return;}invalidateGitPreview();});row.append(check);}
    row.append(document.createTextNode(file.path+(file.reason?" · omitted: "+file.reason:" · choose to inspect")));$("git-files").append(row);}
}

function renderGitDiffs(data){
  $("git-diffs").replaceChildren();
  for(const evidence of data.evidence){const details=document.createElement("details"),summary=document.createElement("summary"),pre=document.createElement("pre");summary.textContent=`${evidence.id} · ${evidence.path}`;pre.textContent=evidence.diff;details.append(summary,pre);$("git-diffs").append(details);}
  $("git-preview-note").textContent=`${data.source_context.omitted_files.length} files omitted from this selection. Only these displayed diffs will reach the local model. Review for private material; filename and credential checks are limited.`;
}

function gitReviewSnapshot(){return {...structuredClone(gitState),selected_files:gitSelection()};}
