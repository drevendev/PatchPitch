# Backlog

## DEV video with sound and controls

Status: deferred by the owner on 23 October 2026; outside the completed article publication cycle. No scheduled work or new hosting account is implied.

Investigate a supported way to play the demo **inside a DEV article**, with audible sound and visible play/pause, seek and volume controls. The current accepted fallback is a DEV CTA opening the GitHub Pages player.

Observed obstacle: DEV's Forem processing treats raw HTML video as GIF-like media. Its initializer forces muted looping playback and removes controls, including when `controls="controls"` is explicitly supplied. A plain MP4 link, external CTA or muted inline loop does not satisfy this backlog item.

Acceptance criteria:

- Use a supported DEV embed or native video feature; investigate supported video hosts, including YouTube when the owner is ready to set it up.
- Verify the saved DEV rendering in a browser: video plays inside the article, sound can be enabled, and play/pause, seeking and volume work.
- Check subtitles and responsive layout; retain the GitHub-hosted source and fallback player.
- Test in a draft first. Updating a published article or creating a hosting account remains a separate explicit action.

Context: [publication closeout](publication-closeout-2026-10-23.md).
