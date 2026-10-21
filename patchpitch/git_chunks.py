"""Lossless, deterministic diff fragments and bounded local-model batches."""
import hashlib
import json
import re

CHUNK_BYTES = 6000
FILE_BYTES = 128_000
TOTAL_BYTES = 192_000
MAX_CHUNKS = 64
BATCH_BYTES = 12_000
MAX_BATCHES = 24
FACTS_PER_BATCH = 8


def fragments(text):
    """Prefer line boundaries; split long lines only at UTF-8 boundaries.

    Concatenating the results reproduces every original byte, including headers,
    whitespace and unterminated lines. No clipping or generated source context.
    """
    current, size, escaped = [], 0, 0
    def cost(value):
        return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))-2
    for line in text.splitlines(keepends=True):
        raw = line.encode("utf-8")
        line_cost = cost(line)
        if size + len(raw) <= CHUNK_BYTES and escaped + line_cost <= 9000:
            current.append(line)
            size += len(raw)
            escaped += line_cost
            continue
        if current:
            yield "".join(current)
            current, size, escaped = [], 0, 0
        while len(line.encode("utf-8")) > CHUNK_BYTES or cost(line) > 9000:
            low, high = 1, min(len(line), CHUNK_BYTES)
            while low < high:
                end = (low+high+1)//2
                if len(line[:end].encode("utf-8")) <= CHUNK_BYTES and cost(line[:end]) <= 9000:
                    low = end
                else:
                    high = end-1
            yield line[:low]
            line = line[low:]
        current, size, escaped = [line], len(line.encode("utf-8")), cost(line)
    if current:
        yield "".join(current)


def evidence_for(path, text, start_id):
    pieces = list(fragments(text))
    offset, hunk, result = 0, "", []
    # Read headers from the original lines: a fragment can start in the middle
    # of an added line whose contents happen to look like a hunk header.
    headers = [(m.start(), m.group(1)) for m in
               re.finditer(r"(?m)^(@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@)", text)] if text.startswith("diff --git ") else []
    header_index, char_offset = 0, 0
    for part, piece in enumerate(pieces, 1):
        while header_index < len(headers) and headers[header_index][0] < char_offset:
            hunk = headers[header_index][1]
            header_index += 1
        item = {"id": f"D{start_id+part-1:02}", "path": path, "diff": piece}
        end = offset + len(piece.encode("utf-8"))
        if len(pieces) > 1:
            item.update(part=part, parts=len(pieces), start_byte=offset, end_byte=end, hunk_header=hunk)
        result.append(item)
        # A raw fragment can begin or end inside a hunk/long line. The last
        # preceding hunk header is orientation only, not an invented full patch.
        offset = end
        char_offset += len(piece)
    return result


def batch_plan(evidence):
    batches, ids, size = [], [], 2  # JSON array brackets.
    for item in evidence:
        # Budget serialized evidence as well as raw code: escaped tabs/quotes and
        # long paths must not silently consume the model's context window.
        cost = len(json.dumps(item, ensure_ascii=False).encode("utf-8"))
        if cost + 2 > BATCH_BYTES:
            raise ValueError("One diff fragment exceeds the model request budget.")
        separator = 2 if ids else 0  # json.dumps uses comma + space.
        if ids and size + separator + cost > BATCH_BYTES:
            batches.append({"index": len(batches), "evidence_ids": ids, "bytes": size})
            ids, size, separator = [], 2, 0
        ids.append(item["id"])
        size += separator + cost
    if ids:
        batches.append({"index": len(batches), "evidence_ids": ids, "bytes": size})
    if len(evidence) > MAX_CHUNKS or len(batches) > MAX_BATCHES:
        raise ValueError("This selection needs too many batches. Narrow the range or file selection.")
    return {"version": 1, "batches": batches,
            "total_bytes": sum(len(e["diff"].encode("utf-8")) for e in evidence)}


def preview_hash(base, head, evidence, chunking=None, repository_id=None):
    value = {"base": base, "head": head, "evidence": evidence}
    if chunking is not None:
        value["chunking"] = chunking
        value["repository_id"] = repository_id
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate_chunks(evidence, files, chunking):
    """Check coverage, ordering, byte ranges and the exact request plan on Open."""
    if list(dict.fromkeys(e["path"] for e in evidence)) != files:
        raise ValueError("Git evidence and selected files differ.")
    expected = []
    for path in files:
        group = [e for e in evidence if e["path"] == path]
        text = "".join(e["diff"] for e in group)
        if len(text.encode("utf-8")) > FILE_BYTES:
            raise ValueError("Saved file diff budget exceeded.")
        expected.extend(evidence_for(path, text, len(expected)+1))
    if evidence != expected or batch_plan(evidence) != chunking or chunking["total_bytes"] > TOTAL_BYTES:
        raise ValueError("Saved diff chunks or batch plan are inconsistent.")
