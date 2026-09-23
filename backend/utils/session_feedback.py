import logging
import random

from supabase import Client

from utils.session_content import extract_session_content
from utils.exam_generation import generate_knowledge_questions

log = logging.getLogger(__name__)

KNOWLEDGE_QUESTIONS_PER_SESSION = 3


def _generate_and_store_knowledge_questions(db: Client, session: dict) -> list[str]:
    """Generates the 3 session-specific learning-check questions from the
    content actually covered (spec: start_position -> end_position, never
    the whole course) and stores them once for this session. Returns their
    ids — empty list if content was too thin or generation failed, which
    the caller treats as 'fewer than 5 questions this time', never as a
    reason to block the session from completing."""
    content = extract_session_content(db, session)
    if not content:
        log.info("Session %s: no extractable content for knowledge questions — skipping.", session.get("id"))
        return []

    # Everything below is best-effort: a bad AI response, a DB hiccup, or
    # (historically, while this table didn't exist yet) a missing table
    # must degrade to "fewer than 5 questions this time", never propagate
    # up and take the feedback-request creation + student notification
    # down with it — those are two unrelated concerns that used to share
    # one try/except in the caller and shouldn't.
    try:
        questions = generate_knowledge_questions(content, KNOWLEDGE_QUESTIONS_PER_SESSION)
        rows = [
            {
                "teaching_session_id": session["id"],
                "order_num": i + 1,
                "question": q["question"],
                "options": q["options"],
                "correct_index": q["correct_index"],
                "explanation": q.get("explanation") or None,
            }
            for i, q in enumerate(questions)
        ]
        res = db.from_("session_knowledge_questions").insert(rows).execute()
        return [r["id"] for r in res.data]
    except Exception as e:
        log.warning("Session %s: knowledge question generation/storage failed: %s", session.get("id"), e)
        return []


def create_feedback_requests(db: Client, session: dict, student_ids: list[str]) -> int:
    """Called once, when a TeachingSession ends. Every student gets the
    same 5 questions — 2 permanent feedback ratings + 3 knowledge-check
    questions generated fresh for THIS session — but each student's own
    randomized display order, generated here and stored, never re-shuffled
    on reopen (spec §26). Returns how many requests were created."""
    if not student_ids:
        return 0

    feedback_questions = (
        db.from_("session_feedback_questions")
        .select("id")
        .eq("is_active", True)
        .order("order_num")
        .execute()
        .data or []
    )
    feedback_ids = [q["id"] for q in feedback_questions]

    knowledge_ids = _generate_and_store_knowledge_questions(db, session)

    question_ids = feedback_ids + knowledge_ids
    if not question_ids:
        return 0

    rows = []
    for student_id in student_ids:
        order = question_ids[:]
        random.shuffle(order)
        rows.append({
            "teaching_session_id": session["id"],
            "student_id": student_id,
            "question_order": order,
        })

    try:
        db.from_("session_feedback_requests").upsert(
            rows, on_conflict="teaching_session_id,student_id", ignore_duplicates=True
        ).execute()
    except Exception:
        pass
    return len(rows)
