"""Local editorial comparison, not a quality score or publication command."""
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE="https://drevengames.itch.io/idle-fantasy-shop/devlog/1714671/title-012-plan-a-little-let-the-fields-rest"


class BodyText(HTMLParser):
    def __init__(self):super().__init__();self.active=False;self.depth=0;self.parts=[]
    def handle_starttag(self,tag,attrs):
        if tag=="section" and "post_body" in dict(attrs).get("class",""):
            self.active=True;self.depth=1;return
        if self.active:
            if tag not in {"br","img","hr","input","meta","link","source"}:self.depth+=1
            if tag in {"p","li","h2","h3","br"}:self.parts.append("\n")
    def handle_endtag(self,tag):
        if self.active:
            self.depth-=1
            if self.depth==0:self.active=False
            if tag in {"p","li","h2","h3"}:self.parts.append("\n")
    def handle_data(self,data):
        if self.active:self.parts.append(data)


def main():
    raw=ROOT/"artifacts"/"ifs-devlog-0.12.html"
    parser=BodyText();parser.feed(raw.read_text(encoding="utf-8"))
    text="".join(parser.parts)
    english=re.split(r"Русский",text,maxsplit=1)[0]
    english="\n".join(re.sub(r"\s+"," ",line).strip() for line in english.splitlines() if line.strip())
    directory=ROOT/"artifacts"/"ifs-comparison"
    (directory/"original-devlog-english.txt").write_text(english,encoding="utf-8")
    edited=(ROOT/"submission"/"ifs-reviewed-announcement.md").read_text(encoding="utf-8")
    words=lambda value:len(re.findall(r"\b[\w’'-]+\b",value))
    attempts=[]
    for path in sorted(directory.glob("*.json")):
        data=json.loads(path.read_text(encoding="utf-8"))
        if "response" in data:
            response=data["response"]
            attempts.append({"file":str(path.relative_to(ROOT)).replace("\\","/"),"model":response["meta"]["model"],"status":data.get("status","EXERCISED"),"seconds":response["meta"]["elapsed_seconds"],"warnings":response["warnings"]})
        elif "status" in data:attempts.append({"file":str(path.relative_to(ROOT)).replace("\\","/"),"model":data.get("model"),"status":data["status"],"error":data.get("error")})
    result={"source_url":SOURCE,"source_html_sha256":hashlib.sha256(raw.read_bytes()).hexdigest(),"original_english_words":words(english),"edited_announcement_words":words(edited),"scope":"Selected main changes; not a full devlog replacement or independent code audit","reviewer":"Agent editorial observations; owner preference/quality rating pending","attempts":attempts,"edited_copy":"submission/ifs-reviewed-announcement.md","publication":"LOCAL ONLY"}
    (ROOT/"submission"/"ifs-comparison.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
