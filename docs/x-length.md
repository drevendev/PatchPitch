# X length estimate and URL budget

Unreleased correction for [#91](https://github.com/drevendev/PatchPitch/issues/91).
No release tag or package version is changed by this fix.

X counts a recognized URL as 23 characters, regardless of its visible length.
The previous `x-estimate-v1` reserved at least 23 but retained the entire weight
of long URLs. That overstated post length and reduced the available prose budget.
See [X's link documentation](https://help.x.com/en/using-twitter/how-to-tweet-a-link.html)
and the [twitter-text configuration](https://github.com/twitter/twitter-text/blob/master/config/v3.json).

`x-estimate-v2` applies 23 characters per supported URL in the Python CLI/API and
browser counter. The same estimate reserves the CTA and six selected hashtags
before model generation and checks the full assembled/edited post afterwards.
Each URL contributes 23; surrounding prose, spaces, punctuation and hashtags
remain separate. Query strings, UTM parameters, paths and fragments inside a
recognized URL do not add to its weight.

## Extraction boundary

The local extractor supports HTTP(S) and bare ASCII DNS domains (including
punycode), optional numeric ports, paths, queries and fragments. It checks host
label syntax and length, excludes email/mention/relative-path prefixes and keeps
sentence punctuation and unmatched brackets outside a URL. Balanced brackets in
a path remain part of the URL. The same URL spans mask fragments before hashtag
counting, so a URL's `#fragment` is not a seventh post hashtag.

This is a bounded estimate, not full twitter-text conformance. It does not use
the complete upstream TLD registry or IDN extraction rules. Unsupported Unicode
hosts, IP literals, credentials, malformed hosts/ports and ambiguous candidates
retain their ordinary weight. Emoji sequences still use the existing codepoint
estimate; NFC and Unicode weight ranges are unchanged. The UI continues to show
an estimate and require verification in X.

The authored fixture corpus covers categories reviewed against the upstream
[URL extraction fixtures](https://github.com/twitter/twitter-text/blob/master/conformance/extract.yml).
Expected counts are asserted independently in Python and JavaScript, in addition
to parity. CLI and browser checks exercise generation reservations, six tags
including `#DEVCommunity`, acceptance at 280 and rejection at 281.

## Saved runs and historical evidence

Original responses and their `x-estimate-v1` measurements are not rewritten.
Current validation refreshes the count on a copied result using `x-estimate-v2`.
The UI likewise computes the current editor count without replacing historical
generation records. The changed source fingerprint gives new campaigns a new
runtime identity; unfinished old campaigns still require their original runtime
for resume. No snapshots or original files are migrated to bypass that check.

For the three ASCII 0.3.0 article announcements, the 95-character DEV URL weighs
23. Their resulting estimates are **176, 185 and 178**, instead of the historical
248, 257 and 250. No shortening service or network request is needed to count.
