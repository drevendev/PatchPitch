param([string]$ArtifactDirectory)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$taskSpeech = New-Object System.Speech.Synthesis.SpeechSynthesizer
$taskVoices = @($taskSpeech.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'en-*' })
if ($taskVoices.Count -eq 0) { throw 'No installed English voice; render with captions only.' }
$taskSpeech.SelectVoice($taskVoices[0].VoiceInfo.Name)
$taskSpeech.Rate = 0
$taskCues = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $ArtifactDirectory 'narration-cues.json') | ConvertFrom-Json
foreach ($taskCue in $taskCues) {
    $taskSpeech.SetOutputToWaveFile((Join-Path $ArtifactDirectory $taskCue.file))
    $taskSpeech.Speak([string]$taskCue.text)
    $taskSpeech.SetOutputToNull()
}
$taskSpeech.Dispose()
@{ voice=$taskVoices[0].VoiceInfo.Name; engine='Windows System.Speech'; network=$false; cost=0 } | ConvertTo-Json | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $ArtifactDirectory 'voice-evidence.json')
