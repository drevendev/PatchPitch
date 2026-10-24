"use strict";
let voiceBundle = null;

function showVoice() {
  const ctx = voiceBundle?.context;
  $("voice-status").textContent = ctx
    ? `${ctx.packs.at(-1).id} / ${ctx.packs.at(-1).version} · ${ctx.language} · ${ctx.tags.join(", ")} · build ${ctx.build_id.slice(0,12)}. Profile candidate: review the generated voice. ${ctx.examples_selected.length} examples, ${ctx.rules_applied.length} rules.${ctx.rules_omitted.length ? " · Some rules omitted: inspect export budget." : ""}`
    : "No Quillgrain profile loaded. Load a voice-bundle.json exported for the selected language and channel.";
  $("voice").disabled = busy || Boolean(ctx);
  $("style").value = ctx ? "voice" : ($("style").value === "voice" ? "warm" : $("style").value);
  $("remove-voice").disabled = busy || !ctx;
}

$("voice-file").addEventListener("change", async () => {
  const file = $("voice-file").files[0];
  if (!file || busy) return;
  setBusy(true); error("");
  try {
    if (file.size > 512000) throw new Error("Voice exports must be at most 512 KB.");
    const candidate = JSON.parse(await file.text());
    await jsonRequest("/api/voice/validate", candidate);
    voiceBundle = candidate;
    $("language").value = candidate.context.language;
    const tags = candidate.context.tags;
    if (tags.includes("social.telegram")) $("format").value = "telegram";
    else if (tags.includes("social.x")) $("format").value = "x_single";
    else $("format").value = "devlog";
    $("format").dispatchEvent(new Event("change"));
    $("style").value = "voice"; $("confirmed").checked = false;
    protectSession();
    $("status").textContent = "Voice loaded locally. Review your facts; no generation was started. Session files will include the private profile.";
  } catch(e) { error(e.message); }
  finally { setBusy(false); showVoice(); $("voice-file").value = ""; }
});
$("remove-voice").addEventListener("click", () => {
  if(busy) return;
  voiceBundle = null; $("confirmed").checked = false; showVoice(); protectSession();
});
$("style").addEventListener("change", () => {
  if(voiceBundle && $("style").value !== "voice") {
    voiceBundle = null; showVoice();
    $("status").textContent = "Ordinary preset selected. Existing drafts retain their original voice snapshot.";
  }
});
showVoice();
