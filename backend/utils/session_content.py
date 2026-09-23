from supabase import Client

# Hard cap on how much text gets sent to the AI per session — a session
# spanning many lessons could otherwise produce a very large prompt. This
# is plenty for 3 short comprehension questions and keeps cost/latency
# predictable.
MAX_CONTENT_CHARS = 8000


def _lesson_text(lesson: dict) -> str:
    """Slides win when present (spec: 'if the lesson contains slides, use
    the slide content') — flattens each slide's text elements in order;
    falls back to the plain markdown content for text-only lessons."""
    slides = lesson.get("slides") or []
    if slides:
        parts = []
        for slide in slides:
            for el in slide.get("elements", []):
                if el.get("type") == "text" and el.get("content"):
                    parts.append(el["content"])
        if parts:
            return "\n".join(parts)
    return lesson.get("content") or ""


def extract_session_content(db: Client, session: dict) -> str:
    """Walks course_modules -> course_lessons between the session's
    recorded start_position and end_position (module/lesson granularity —
    not slide-level trimming within a lesson, since a lesson's slides are
    normally one coherent topic) and returns their concatenated text.

    Deliberately does NOT fall back to "the whole course" if positions are
    missing/incomplete — per spec, knowledge questions must come only from
    what was actually covered. Returns "" when nothing can be determined,
    and callers must treat that as "skip generation", not "use everything".
    """
    course_id = session.get("course_id")
    start_pos = session.get("start_position") or {}
    end_pos = session.get("end_position") or {}
    start_module_id = start_pos.get("module_id")
    end_module_id = end_pos.get("module_id") or start_module_id
    if not course_id or not start_module_id:
        return ""

    modules = (
        db.from_("course_modules")
        .select("id, order_num, title")
        .eq("course_id", course_id)
        .order("order_num")
        .execute()
        .data or []
    )
    module_ids = [m["id"] for m in modules]
    if start_module_id not in module_ids:
        return ""
    start_idx = module_ids.index(start_module_id)
    end_idx = module_ids.index(end_module_id) if end_module_id in module_ids else start_idx
    if end_idx < start_idx:
        start_idx, end_idx = end_idx, start_idx
    covered_modules = modules[start_idx:end_idx + 1]

    start_lesson_id = start_pos.get("lesson_id")
    end_lesson_id = end_pos.get("lesson_id")

    chunks: list[str] = []
    for i, module in enumerate(covered_modules):
        lessons = (
            db.from_("course_lessons")
            .select("id, order_num, title, content, slides")
            .eq("module_id", module["id"])
            .order("order_num")
            .execute()
            .data or []
        )
        lesson_ids = [l["id"] for l in lessons]

        # Trim to the lesson range only at the first/last module — a middle
        # module (fully between start and end) contributes all its lessons.
        lo = lesson_ids.index(start_lesson_id) if i == 0 and start_lesson_id in lesson_ids else 0
        hi = (lesson_ids.index(end_lesson_id) if i == len(covered_modules) - 1 and end_lesson_id in lesson_ids else len(lessons) - 1)
        if hi < lo:
            lo, hi = 0, len(lessons) - 1

        for lesson in lessons[lo:hi + 1]:
            text = _lesson_text(lesson).strip()
            if text:
                chunks.append(f"## {module['title']} — {lesson['title']}\n{text}")

    full_text = "\n\n".join(chunks).strip()
    return full_text[:MAX_CONTENT_CHARS]
