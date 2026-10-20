"use strict";
// Mirrors social_count.py. Conservative estimate; always verify in X.
window.socialLength = text => {
  text = text.normalize("NFC");
  const weight = c => {const n=c.codePointAt(0);return n<=4351 || (n>=8192&&n<=8205) || (n>=8208&&n<=8223) || (n>=8242&&n<=8247) ? 1:2;};
  let count=Array.from(text).reduce((n,c)=>n+weight(c),0);
  const urls=/(?:https?:\/\/|www\.)[^\s<>]+|(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,63}(?:\/[^\s<>]*)?/gi;
  for(const m of text.matchAll(urls)) {
    const trailing=m[0].length-m[0].replace(/[.,!?;:)'"…]+$/u,"").length;
    count+=Math.max(0,23+2*trailing-Array.from(m[0]).reduce((n,c)=>n+weight(c),0));
  }
  return {characters:count,limit:280,policy:"x-estimate-v1",estimated:true,over_limit:count>280,requires_x_preview:true};
};
