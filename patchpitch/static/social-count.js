"use strict";
// Mirrors social_count.py, including its bounded ASCII-DNS URL extraction.
// Not full twitter-text conformance; Unicode/emoji and other URLs need X preview.
window.socialLength = text => {
  text = text.normalize("NFC");
  const weight = c => {const n=c.codePointAt(0);return n<=4351 || (n>=8192&&n<=8205) || (n>=8208&&n<=8223) || (n>=8242&&n<=8247) ? 1:2;};
  let count=Array.from(text).reduce((n,c)=>n+weight(c),0);
  const urls=/(?<![\p{L}\p{N}_@/#$.\-])(?:https?:\/\/|www\.|[A-Za-z0-9_-]+\.)[^\s<>\x00-\x1f\x7f"'`\u2018\u2019\u201c\u201d]+/giu;
  for(const m of text.matchAll(urls)) {
    let token=m[0];
    const stack=[], pairs={")":"(","]":"[","}":"{"};
    for(let i=0;i<token.length;i++) {
      const char=token[i];
      if("([{".includes(char)) stack.push([char,i]);
      else if(")]}".includes(char)) {
        if(!stack.length || stack.at(-1)[0]!==pairs[char]) {token=token.slice(0,i);break;}
        stack.pop();
      }
    }
    if(stack.length) token=token.slice(0,stack[0][1]);
    token=token.replace(/[.,!?;:\u2026]+$/u,"");
    const authority=token.replace(/^https?:\/\//i,"").split(/[/?#]/u,1)[0];
    const parsed=/^([A-Za-z0-9.-]+)(?::([0-9]{1,5}))?$/u.exec(authority);
    if(!parsed) continue;
    const [,host,port]=parsed, labels=host.split(".");
    if(host.length>253 || labels.length<2 || labels.some(label=>!/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$/u.test(label)) ||
       !/^(?:[A-Za-z]{2,63}|xn--[A-Za-z0-9-]{1,59})$/iu.test(labels.at(-1)) || (port && (+port<1 || +port>65535))) continue;
    count+=23-Array.from(token).reduce((n,c)=>n+weight(c),0);
  }
  return {characters:count,limit:280,policy:"x-estimate-v2",estimated:true,over_limit:count>280,requires_x_preview:true};
};
