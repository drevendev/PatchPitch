"use strict";

const saveFileBytes=32_000_000;

const sessionFields=["product","description","audience","release","voice","cta","changes","format","style","intent","writing-goal","language","tag-allowlist"];

function downloadJSON(value,filename){
  const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)+"\n"],{type:"application/json;charset=utf-8"}));
  const a=document.createElement("a");a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function currentForm(){
  const form=Object.fromEntries(sessionFields.map(id=>[id.replaceAll("-","_"),$(id).value]));
  return {...form,legacy_x:$("legacy-x").checked,media_note:$("media-note").value,post_count:Number($("post-count").value),auto_tags:$("auto-tags").checked};
}
function sessionSnapshot(){
  saveCurrent();
  return {kind:"patchpitch_session",schema_version:1,voice_bundle:structuredClone(voiceBundle),x_catalog:structuredClone(xCatalog),form:currentForm(),changes:structuredClone(changes),
    preview_text:previewText,pack_context:structuredClone(packContext),drafts:structuredClone([...drafts.values()]),
    active_key:result?contextKey(result.presentation?.format||"devlog",result.context):null,
    records:structuredClone(generationRecords),record_choice:$("record-choice").value||null,
    git_controls:typeof gitControls==="function"?gitControls():{},
    publication_markers:typeof publicationMarkers!=="undefined"?structuredClone(publicationMarkers):{},git_record:null,git_review:typeof gitReviewSnapshot==="function"?gitReviewSnapshot():null};
}
function hasSessionContent(){return Boolean(
  ["product","description","audience","release","voice","cta","changes","media-note"].some(id=>$(id).value)
  || voiceBundle || changes.length || drafts.size || generationRecords.length || hasGitContent());}

async function saveFile(kind){
  if(busy)return;
  setBusy(true);error("");
  try{
    const value=kind==="session"?sessionSnapshot():{kind:"patchpitch_profile",schema_version:1,
      product:{name:$("product").value,description:$("description").value},audience:$("audience").value,cta_text:$("cta").value};
    // Check the actual pretty-printed download, not only the compact request.
    // Otherwise a successful Save can produce a file that Open rejects.
    if(new TextEncoder().encode(JSON.stringify(value,null,2)+"\n").length>saveFileBytes)
      throw new Error("Save files must be at most 32 MB. Download the Git review or generation records separately to keep this work.");
    const checked=await jsonRequest("/api/session/validate",value);
    const name=exportName({context:{product:$("product").value,release_label:kind},presentation:{format:kind}}).replace(/\.md$/,".json");
    downloadJSON(checked,name);
    $("status").textContent=kind==="session"?"Session downloaded. Open this file to restore your inputs, drafts and records. Keep it private.":"Product profile downloaded. Release facts and drafts are not included.";
  }catch(e){error(e.message);}
  finally{setBusy(false);}
}

async function openFile(file,kind){
  if(busy||!file)return;
  setBusy(true);error("");
  try{
    if(file.size>saveFileBytes)throw new Error("Save files must be at most 32 MB.");
    const value=JSON.parse(await file.text());
    if(value.kind!==`patchpitch_${kind}`)throw new Error(`Choose a PatchPitch ${kind} file.`);
    const checked=await jsonRequest("/api/session/validate",value);
    if(hasSessionContent() && !confirm(kind==="session"?"Replace this tab with the saved session? Download the current session first to keep it.":"Apply this product profile? Release notes and existing drafts will stay available."))return;
    if(kind==="session")restoreSession(checked);
    else{
      $("product").value=checked.product.name;$("description").value=checked.product.description;
      $("audience").value=checked.audience;$("cta").value=checked.cta_text;
      $("media-note").value="";updateContextReview();
    }
    $("status").textContent=kind==="session"?"Session opened. Review the restored facts before another generation. Nothing was generated or published.":"Profile opened. Review the context and current release facts before generation.";
  }catch(e){error(e.message);$("status").textContent="The save file was not opened. Your current session is still here.";}
  finally{setBusy(false);$(kind==="session"?"open-session":"open-profile").value="";}
}

function restoreSession(saved){
  inputRevision++;clearTimeout(previewTimer);closeDisclosure($("selection-panel"));
  for(const id of sessionFields)$(id).value=saved.form[id.replaceAll("-","_")] ?? (id === "language" ? "en" : "");
  voiceBundle=structuredClone(saved.voice_bundle ?? null);showVoice();
  xCatalog=structuredClone(saved.x_catalog ?? null);showCatalog();$("legacy-x").checked=saved.form.legacy_x ?? false;
  $("media-note").value=saved.form.media_note;$("post-count").value=String(saved.form.post_count);
  $("auto-tags").checked=saved.form.auto_tags;$("format").dispatchEvent(new Event("change"));
  packContext=structuredClone(saved.pack_context);
  applyPrepared(saved.preview_text??saved.form.changes,{changes:structuredClone(saved.changes)});
  previewText=saved.preview_text;$("confirmed").checked=false;
  $("pack-status").textContent=packContext?"Restored source snapshot · review before generating.":"Restored manual notes · review before generating.";
  $("example-label").hidden=true;
  drafts.clear();for(const state of saved.drafts)drafts.set(contextKey(state.data.presentation.format,state.data.context),structuredClone(state));
  generationRecords.splice(0,generationRecords.length,...structuredClone(saved.records));
  $("record-choice").replaceChildren();for(const record of generationRecords)appendRecordOption(record);
  $("generation-records").hidden=!generationRecords.length;
  if(saved.record_choice){$("record-choice").value=saved.record_choice;showGenerationRecord();}
  result=null;socialPosts=[];currentMarkdown="";currentTags=[];edited=false;
  const active=drafts.get(saved.active_key);
  if(active){render(active.data,active);}
  else{
    for(const id of ["result","result-tools","storage-hint","social-posts","editor","editor-label"])$(id).hidden=true;
    $("empty-state").hidden=false;$("saved-drafts").replaceChildren();
  }
  if(typeof restoreGitControls==="function")restoreGitControls(saved.git_controls,saved.publication_markers,saved.git_record??null,saved.git_review??null);
  if(hasSessionContent())protectSession();
}

$("save-session").addEventListener("click",()=>saveFile("session"));
$("save-profile").addEventListener("click",()=>saveFile("profile"));
$("open-session").addEventListener("change",()=>openFile($("open-session").files[0],"session"));
$("open-profile").addEventListener("change",()=>openFile($("open-profile").files[0],"profile"));
