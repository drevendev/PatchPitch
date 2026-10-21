"use strict";

let gitState={inspection:null,preview:null,facts:null,record:null};
let publicationMarkers={};
let gitExtracting=false, gitStopRequested=false;
const gitFieldIds=["git-repo","git-mode","git-count","git-base","git-head","git-path"];
function gitControls(){return Object.fromEntries(gitFieldIds.map(id=>[id,$(id).value]));}
function hasGitContent(){return Boolean($("git-repo").value||gitState.inspection||gitState.record||Object.keys(publicationMarkers).length);}
function gitSelection(){return [...document.querySelectorAll("#git-files input:checked")].map(e=>e.value);}
function currentGitRun(){return gitState.record?.schema_version===2 && gitState.record.preview_sha256===gitState.preview?.preview_sha256?gitState.record:null;}
function completedGitBatches(run=currentGitRun()){return new Set((run?.attempts||[]).filter(a=>a.status==="accepted").map(a=>a.batch_index));}
function gitFactsReady(){const run=currentGitRun();return Boolean(gitState.facts?.length && (run?run.status==="complete":gitState.record?.schema_version!==2));}
function syncGitButtons(){
  $("git-preview").disabled=busy||!gitState.inspection||!gitSelection().length;
  $("git-reviewed").disabled=busy||!gitState.preview;
  $("git-extract").disabled=busy||!gitState.preview?.chunking||!$("git-reviewed").checked;
  $("git-extract").textContent=currentGitRun() && currentGitRun().status!=="complete"?"Continue remaining batches":"Suggest facts with local Gemma";
  $("git-stop").disabled=!gitExtracting||gitStopRequested;
  $("git-apply").disabled=busy||!gitFactsReady();
  $("git-download-record").disabled=busy||!gitState.record;
  $("record-publication").disabled=busy||!result?.context?.source_context?.repository_id;
}
function invalidateGitPreview(){
  const run=currentGitRun();
  if(run && Array.isArray(gitState.facts))run.candidate_edits=structuredClone(gitState.facts);
  gitState.preview=null;gitState.facts=null;$("git-reviewed").checked=false;$("git-diffs").replaceChildren();$("git-candidates").replaceChildren();$("git-preview-note").textContent="";$("git-progress").textContent="";syncGitButtons();}
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
    const cached=gitState.record?.schema_version===2 && gitState.record.preview_sha256===data.preview_sha256
      && Array.isArray(gitState.record.candidate_edits);
    if(gitState.preview?.preview_sha256!==data.preview_sha256 && !cached){
      // Old sessions can acquire a request plan without losing edits when their
      // original single-file evidence and IDs are still exactly the same.
      const legacySame=gitState.record?.schema_version!==2 && JSON.stringify(gitState.preview?.evidence)===JSON.stringify(data.evidence)
        && gitState.preview?.source_context.base===data.source_context.base && gitState.preview?.source_context.head===data.source_context.head
        && gitState.preview?.source_context.repository_id===data.source_context.repository_id;
      if(!legacySame){
        if((gitState.facts?.length || gitState.record?.candidate_edits?.length) && !confirm("These diffs change candidate source references. Replace the current review? Download the session first to keep your edits."))return;
        gitState.facts=null;$("git-candidates").replaceChildren();
      }
    }
    if(cached){gitState.facts=structuredClone(gitState.record.candidate_edits);delete gitState.record.candidate_edits;}
    gitState.preview=data;$("git-reviewed").checked=false;
    renderGitDiffs(data);if(gitState.facts)renderGitCandidates();renderGitRecord();
    $("status").textContent=`Selected diffs are ready for review in ${data.evidence.length} parts and ${data.chunking.batches.length} model request(s). No inference has run.`;
  }catch(e){error(e.message);}
  finally{setBusy(false);}
}
async function extractGit(){
  if(busy||!gitState.preview?.chunking||!$("git-reviewed").checked)return;
  let run=currentGitRun();
  if(!run||run.status==="complete"){
    if(gitState.facts?.length && !confirm("Replace the current fact candidates? Download the session first to keep your edits."))return;
    run={schema_version:2,kind:"patchpitch_git_review",status:"in_progress",preview_sha256:gitState.preview.preview_sha256,
      source_context:structuredClone(gitState.preview.source_context),evidence:structuredClone(gitState.preview.evidence),
      chunking:structuredClone(gitState.preview.chunking),attempts:[]};
    gitState.record=run;gitState.facts=[];
  }
  if(run.attempts.length>=96){error("This review has reached 96 recorded attempts. Download the session before starting a new review.");return;}
  const batches=gitState.preview.chunking.batches;
  let active=0,started=performance.now();
  gitExtracting=true;gitStopRequested=false;setBusy(true);error("");
  const update=()=>{$("status").textContent=`Local Gemma · request ${active+1}/${batches.length} · ${completedGitBatches(run).size} completed · ${((performance.now()-started)/1000).toFixed(1)}s${gitStopRequested?" · stopping after this request":""}`;};
  const timer=setInterval(update,250);
  try{
    run.status="in_progress";
    for(active=0;active<batches.length;active++){
      if(completedGitBatches(run).has(active))continue;
      if(run.attempts.length>=96){run.status="stopped";break;}
      started=performance.now();update();
      const body={...gitRequest(),reviewed:true,preview_sha256:gitState.preview.preview_sha256,batch_index:active};
      const data=await jsonRequest("/api/git/facts",body);
      if(data.batch?.index!==active || data.batch?.count!==batches.length || data.preview_sha256!==run.preview_sha256
        || JSON.stringify(data.batch.evidence_ids)!==JSON.stringify(batches[active].evidence_ids)){
        const failure=new Error("The server returned a different batch. Restart an older server, then review these diffs again.");failure.evidence=data;throw failure;
      }
      run.attempts.push({batch_index:active,status:"accepted",response:data,error:null});
      gitState.facts.push(...data.facts.map(f=>({...f,batch_index:active,current_text:f.text,include:false})));
      renderGitCandidates();renderGitRecord();
      if(gitStopRequested && completedGitBatches(run).size<batches.length){run.status="stopped";break;}
    }
    if(completedGitBatches(run).size===batches.length)run.status="complete";
    $("status").textContent=run.status==="complete"?"All diff parts processed. Review candidates against their cited parts, remove duplicates and explicitly choose up to 15 facts.":"Stopped after the current request. Completed batches and candidate edits are kept. Download the session or continue explicitly.";
  }catch(e){
    run.attempts.push({batch_index:active,status:"failed",response:e.evidence??null,error:{code:e.code||"request_failed",message:e.message}});
    run.status=completedGitBatches(run).size?"partial":"failed";
    error(e.message);$("status").textContent="Batch failed. Completed batches, candidate edits, input and writing drafts are kept. Download the session or continue explicitly; no automatic retry.";
  }
  finally{clearInterval(timer);gitExtracting=false;setBusy(false);renderGitCandidates();renderGitRecord();}
}
function renderGitRecord(){
  $("git-record").hidden=!gitState.record;
  $("git-record-raw").textContent=gitState.record?JSON.stringify(gitState.record,null,2):"";
  const run=currentGitRun();
  $("git-progress").textContent=run?`${completedGitBatches(run).size}/${run.chunking.batches.length} requests completed · ${run.status} · ${gitState.facts?.length||0} candidates. Your selection and edits are required before writing.`:"";
}
function gitEvidenceLabel(e){return e.id+" "+e.path+(e.parts?` · part ${e.part}/${e.parts} · diff bytes ${e.start_byte}–${e.end_byte}`:"");}
function renderGitCandidates(){
  $("git-candidates").replaceChildren();
  for(const [index,fact] of gitState.facts.entries()){
    const card=document.createElement("section");card.className="git-candidate";
    const label=document.createElement("label"),check=document.createElement("input");check.type="checkbox";check.checked=fact.include;check.disabled=busy;check.setAttribute("aria-label",`Use fact ${index+1}`);check.addEventListener("change",()=>{if(check.checked && gitState.facts.filter(f=>f.include).length>=15){check.checked=false;error("Choose at most 15 facts for one DevLog. Other candidates stay in the review.");return;}fact.include=check.checked;});label.append(check,document.createTextNode(` Fact ${index+1} · ${fact.kind} · ${fact.evidence_ids.join(", ")}`));
    const text=document.createElement("textarea");text.value=fact.current_text;text.maxLength=800;text.disabled=busy;text.setAttribute("aria-label",`Review fact ${index+1}`);text.addEventListener("input",()=>{fact.current_text=text.value;});
    const refs=document.createElement("p");refs.className="helper";
    for(const id of fact.evidence_ids){const evidence=gitState.preview.evidence.find(e=>e.id===id);if(!evidence)continue;const link=document.createElement("button");link.type="button";link.className="text-button";link.textContent="Review "+gitEvidenceLabel(evidence);link.disabled=busy;link.addEventListener("click",()=>{const details=$("git-evidence-"+id);details.open=true;details.querySelector("summary").focus();details.scrollIntoView({block:"nearest"});});refs.append(link);}
    card.append(label,text,refs);$("git-candidates").append(card);
  }
}
function applyGitFacts(){
  if(busy||!gitFactsReady())return;
  error("");
  const facts=gitState.facts.map((f,index)=>({...f,original_index:index})).filter(f=>f.include);
  if(!facts.length||facts.length>15){error("Choose 1–15 facts after reviewing them. Other candidates stay in the review.");return;}
  if(facts.some(f=>!f.current_text.trim())||facts.reduce((n,f)=>n+Array.from(f.current_text).length,0)>6000){error("Use nonempty facts and at most 6,000 total characters.");return;}
  if($("changes").value&&!confirm("Replace the current input notes with these reviewed Git facts? Existing drafts stay available."))return;
  const context=gitState.preview.source_context;
  if(!$("product").value)$("product").value=context.repository;
  if(!$("description").value)$("description").value="A software project under development.";
  if(!$("audience").value)$("audience").value="People following this project's development";
  $("release").value=`Development ${context.head.slice(0,12)}`;$("writing-goal").value="development";$("format").value="devlog";$("format").dispatchEvent(new Event("change"));$("media-note").value="";
  const prepared=facts.map((f,i)=>({id:`C${String(i+1).padStart(2,"0")}`,text:f.current_text,include:f.include,reason:f.kind==="uncertain"?"Model inference — review against code":""}));
  const refs=facts.map((f,i)=>({api_id:prepared[i].id,stable_id:`G${String(f.original_index+1).padStart(3,"0")}`,source_url:"",
    source_ref:`Git ${context.base||"empty tree"}..${context.head}; ${f.evidence_ids.map(id=>gitEvidenceLabel(gitState.preview.evidence.find(e=>e.id===id))).join("; ")}`}));
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
$("git-stop").addEventListener("click",()=>{gitStopRequested=true;syncGitButtons();});
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
  for(const evidence of data.evidence){const details=document.createElement("details"),summary=document.createElement("summary"),pre=document.createElement("pre");details.id="git-evidence-"+evidence.id;summary.textContent=gitEvidenceLabel(evidence);summary.tabIndex=0;
    if(evidence.parts){const note=document.createElement("p");note.className="helper";note.textContent=`Raw diff fragment ${evidence.part}/${evidence.parts}; byte range [${evidence.start_byte}, ${evidence.end_byte}). May continue a hunk or long line. ${evidence.hunk_header?"Preceding hunk: "+evidence.hunk_header:""}`;details.append(note);}
    pre.textContent=evidence.diff;details.prepend(summary);details.append(pre);$("git-diffs").append(details);}
  const count=data.chunking?.batches.length;
  $("git-preview-note").textContent=`${data.source_context.omitted_files.length} files omitted. ${data.evidence.length} complete diff parts${count?` · ${count} sequential local-model request(s) after confirmation`:" · review selected diffs again to plan model requests"}. Only displayed parts reach the model; no code is clipped. Inspect private material yourself; filename/credential checks are limited.`;
}

function gitReviewSnapshot(){return {...structuredClone(gitState),selected_files:gitSelection()};}
