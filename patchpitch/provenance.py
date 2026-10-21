"""Source identity shared by every writing format, outside model instructions."""


def source_snapshot(request):
    refs = {ref.api_id: ref for ref in request.source_references}
    return [dict(api_id=c.id, stable_id=refs[c.id].stable_id if c.id in refs else c.id,
                 text=c.text, include=c.include,
                 source_url=refs[c.id].source_url if c.id in refs else "",
                 source_ref=refs[c.id].source_ref if c.id in refs else "")
            for c in request.changes]


def source_context(request):
    return {"pack_id": request.pack_id, "pack_version": request.pack_version,
            "pack_sha256": request.pack_sha256, "context_overrides": request.context_overrides,
            "source_context": request.source_context.model_dump() if request.source_context else None,
            "writing_goal": request.writing_goal}
