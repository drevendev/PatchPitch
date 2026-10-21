"use strict";

// Session-only records. No localStorage, automatic files, or telemetry payloads.
const generationRecords = [];

function rememberGeneration(request, {response=null, error=null}, started) {
  const record = {
    schema_version:1, id:`A${String(Math.max(0,...generationRecords.map(r=>Number(r.id.slice(1))))+1).padStart(2,"0")}`,
    recorded_at:new Date().toISOString(), status:error?"failed":"accepted",
    client_elapsed_seconds:Number(((performance.now()-started)/1000).toFixed(3)),
    input_snapshot:structuredClone(request), response:response?structuredClone(response):null,
    error:error?{code:error.code||"request_failed",message:error.message,http_status:error.httpStatus??null}:null,
    evidence:error?.evidence?structuredClone(error.evidence):null
  };
  generationRecords.push(record);
  if(response)response.local_record_id=record.id;
  appendRecordOption(record);$("record-choice").value=record.id;
  $("generation-records").hidden=false;showGenerationRecord();
  if(error){closeDisclosure($("generation-records"));$("generation-records").open=true;$("generation-records").querySelector("summary").setAttribute("aria-expanded","true");}
  if(!unloadProtected){window.addEventListener("beforeunload",warnUnload);unloadProtected=true;}
}

function selectedGenerationRecord(){return generationRecords.find(record=>record.id===$("record-choice").value);}

function showGenerationRecord(){
  const record=selectedGenerationRecord();if(!record)return;
  const meta=record.evidence||record.response?.meta||{};
  const raw=record.evidence?.raw_response??record.response?.raw_response;
  const identity=meta.returned_model??meta.model??"unknown";
  const duration=Number.isFinite(meta.elapsed_seconds)?`${meta.elapsed_seconds.toFixed(1)}s server time`:`${record.client_elapsed_seconds.toFixed(1)}s browser time`;
  $("record-summary").textContent=`${record.recorded_at} · ${record.input_snapshot.release_label||"Unversioned"} · returned model: ${identity} · ${duration}`;
  $("record-outcome").textContent=record.error?`Failed · ${record.error.code}: ${record.error.message}`:"Accepted by application checks. Review the wording and facts before use.";
  $("record-raw-label").textContent=record.error?"Original response — rejected, not a draft":"Original model response";
  $("record-raw").textContent=raw==null?"No model response was available for this attempt.":typeof raw.message?.content==="string"?raw.message.content:JSON.stringify(raw,null,2);
}

function generationRecordExport(){
  saveCurrent();
  const record=structuredClone(selectedGenerationRecord());
  // Keep original API data immutable; edited text is a separate review snapshot.
  const saved=[...drafts.values()].find(state=>state.data.local_record_id===record.id ||
    state.posts?.some(post=>post.local_record_id===record.id));
  if(saved)record.review_snapshot={markdown:saved.markdown,posts:saved.posts,edited:saved.edited,
    validation:"Snapshot of the current draft; manual edits have not been revalidated."};
  return JSON.stringify(record,null,2)+"\n";
}

$("record-choice").addEventListener("change",showGenerationRecord);
$("copy-record").addEventListener("click",async()=>{
  try{await navigator.clipboard.writeText(generationRecordExport());$("status").textContent="Generation record copied. It may contain private input and model text.";}
  catch{error("Clipboard unavailable. Use Download record JSON instead.");}
});
$("download-record").addEventListener("click",()=>{
  const record=selectedGenerationRecord();
  const filename=exportName({context:{product:record.input_snapshot.product.name,release_label:record.input_snapshot.release_label,generated_at:record.recorded_at},presentation:{format:record.input_snapshot.format}}).replace(/\.md$/,`-${record.id}-${record.status}.json`);
  const url=URL.createObjectURL(new Blob([generationRecordExport()],{type:"application/json;charset=utf-8"}));
  const link=document.createElement("a");link.href=url;link.download=filename;link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);$("status").textContent="Generation record downloaded locally. Nothing has been published.";
});

function appendRecordOption(record){
  const request=record.input_snapshot;
  const option=document.createElement("option");option.value=record.id;
  option.textContent=`${record.id} · ${request.product.name} · ${formatNames[request.format]}${request.operation==="regenerate"?` · rewrite ${request.target_post_id}`:""} · ${record.status}`;
  $("record-choice").append(option);
}
