# -*- coding: utf-8 -*-
"""One-off manual test of the course-generation pipeline (utils/course_generation.py),
run against the pilot course: AS-107 'Droit législation' (Aide-Soignant, 1ère année).

Run from backend/, with the venv active:
    venv\\Scripts\\activate
    python generate_pilot_course.py

Safe to re-run: each run inserts a fresh set of draft course_modules/course_lessons
rows (status='draft'), nothing is published or overwritten. Delete drafts you don't
want to keep from the course_modules/course_lessons tables directly, or once the
review UI exists.
"""
# Must load .env before importing anything that reads OPENAI_API_KEY/
# OPENAI_BASE_URL as a module-level constant (utils/course_generation.py) —
# unlike the real app, this script has no main.py to import `deps` first.
from dotenv import load_dotenv
load_dotenv()

from utils.course_generation import gather_grounding_text, generate_module_outline, generate_lesson_content
from deps import get_db

db = get_db()

COURSE_ID = "8b745bf0-f529-4336-a843-5901ac96b3d5"   # AS-107 Droit législation
COURSE_TITLE = "Droit législation"
SPECIALTY_ID = "064bf887-f0da-4a2e-9519-0d28733cb81c"  # Aide-Soignant
FILIERE_LABEL = "Aide-Soignant · 1ère année"

print("=== Stage 0: gathering grounding text ===")
outline_grounding = gather_grounding_text(db, SPECIALTY_ID, ["cdc", "programmes", "fiches_examens"])
print(f"{len(outline_grounding)} chars gathered for outline stage")
print(outline_grounding[:800])
print("...\n")

print("=== Stage 1: generate_module_outline ===")
modules = generate_module_outline(COURSE_TITLE, FILIERE_LABEL, outline_grounding)
for m in modules:
    print(f"  - {m['title']}  (TH {m['hours_theory']}h / TP {m['hours_practice']}h)")
    print(f"    objectifs: {m['objectives']}")

print(f"\n{len(modules)} chapters generated. Saving as draft course_modules...")
saved_modules = []
for i, m in enumerate(modules, start=1):
    res = db.from_("course_modules").insert({
        "course_id": COURSE_ID,
        "order_num": i,
        "title": m["title"],
        "objectives": m["objectives"],
        "hours_theory": m["hours_theory"],
        "hours_practice": m["hours_practice"],
        "status": "draft",
        "source_specialty_id": SPECIALTY_ID,
        "generated_at": "now()",
    }).execute()
    saved_modules.append(res.data[0])
print(f"Saved {len(saved_modules)} draft modules.")

print("\n=== Stage 2: generate_lesson_content per chapter ===")
lesson_grounding = gather_grounding_text(db, SPECIALTY_ID, ["fiches_examens"])
print(f"{len(lesson_grounding)} chars gathered for lesson stage\n")

for mod in saved_modules:
    print(f"--- Generating lesson for: {mod['title']} ---")
    content = generate_lesson_content(COURSE_TITLE, mod["title"], mod["objectives"], lesson_grounding)
    db.from_("course_lessons").insert({
        "module_id": mod["id"],
        "order_num": 1,
        "title": mod["title"],
        "content": content,
        "status": "draft",
        "generated_at": "now()",
    }).execute()
    print(content[:600])
    print(f"... [{len(content)} chars total]\n")

print("DONE. Review drafts with:")
print("  select id, title, status from course_modules where course_id = '%s';" % COURSE_ID)
print("  select l.id, l.title, l.status, length(l.content) from course_lessons l")
print("  join course_modules m on m.id = l.module_id where m.course_id = '%s';" % COURSE_ID)
