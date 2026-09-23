# Seeds an isolated E2E test fixture for the Playwright suite: one
# professor, one student, one class, one course assigned to that class,
# and one published module/lesson carrying a 2-slide deck (so the
# presentation-flow test has something to click through).
#
# Idempotent — safe to re-run. Never touches real student/professor data;
# everything it creates is prefixed "E2E " / uses an "e2e." email so it's
# unmistakable in the dashboard if you go looking for it.
#
# Run once before the E2E suite: python seed_e2e.py
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
db = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

PROF_EMAIL = os.environ.get("E2E_PROFESSOR_EMAIL", "e2e.professor@ipisb.ma")
PROF_PASSWORD = os.environ.get("E2E_PROFESSOR_PASSWORD", "E2E_Prof_2026!")
STUDENT_EMAIL = os.environ.get("E2E_STUDENT_EMAIL", "e2e.student@ipisb.ma")
STUDENT_PASSWORD = os.environ.get("E2E_STUDENT_PASSWORD", "E2E_Student_2026!")
# A second, unrelated professor — owns nothing the first professor's E2E
# course/exam belongs to. Exists purely so the exam-authoring ownership
# fix (a professor must not manage another professor's exam) has someone
# to fail as, tested via a direct API call with this professor's own token.
PROF2_EMAIL = os.environ.get("E2E_PROFESSOR2_EMAIL", "e2e.professor2@ipisb.ma")
PROF2_PASSWORD = os.environ.get("E2E_PROFESSOR2_PASSWORD", "E2E_Prof2_2026!")

CLASS_NAME = "E2E Test Class"
COURSE_TITLE = "E2E Test Course"
MODULE_TITLE = "E2E Module 1"
LESSON_TITLE = "E2E Lesson 1"
# Second module, markdown-only (no slides) — lets the suite exercise chapter
# next/prev navigation (needs >1 module) and the nullable-slide_id content
# position path for text-only lessons (spec Decision 2), not just slides.
MODULE_2_TITLE = "E2E Module 2"
LESSON_2_TITLE = "E2E Lesson 2"
LESSON_2_CONTENT = "## E2E Text Lesson\n\nThis is markdown-only content with no slide deck."

SLIDES = [
    {
        "id": "e2e-slide-1",
        "title": "Slide 1",
        "elements": [
            {
                "id": "e2e-el-1", "type": "text", "x": 40, "y": 40, "width": 400, "height": 80, "rotation": 0,
                "content": "E2E Slide One", "fontSize": 32, "fontFamily": "Manrope", "bold": True,
                "italic": False, "underline": False, "align": "left", "color": "#111111", "backgroundColor": None,
            },
        ],
    },
    {
        "id": "e2e-slide-2",
        "title": "Slide 2",
        "elements": [
            {
                "id": "e2e-el-2", "type": "text", "x": 40, "y": 40, "width": 400, "height": 80, "rotation": 0,
                "content": "E2E Slide Two", "fontSize": 32, "fontFamily": "Manrope", "bold": True,
                "italic": False, "underline": False, "align": "left", "color": "#111111", "backgroundColor": None,
            },
        ],
    },
]


def get_or_create_user(email: str, password: str, full_name: str) -> str:
    # `profiles` is checked by exact email first — list_users() paginates
    # (50/page) and this project has more real users than that, so scanning
    # its default page silently misses matches and would create duplicate
    # auth accounts on every re-run. profiles.email is an exact, unpaginated
    # lookup and is always kept in sync with auth.users below.
    existing_profile = db.from_("profiles").select("id").eq("email", email).execute().data
    if existing_profile:
        return existing_profile[0]["id"]

    try:
        res = db.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"full_name": full_name},
        })
        return str(res.user.id)
    except Exception:
        # Auth user exists but its profile row doesn't (inconsistent state,
        # e.g. an interrupted earlier run) — fall back to a paginated scan.
        page = 1
        while True:
            batch = db.auth.admin.list_users(page=page, per_page=200)
            if not batch:
                raise
            for u in batch:
                if u.email == email:
                    return str(u.id)
            page += 1


def ensure_profile(uid: str, email: str, full_name: str, created_by: str | None = None) -> None:
    # created_by matters: "Mes Étudiants" (dashboard/users) only shows
    # students where profiles.created_by == the professor's own id — a
    # student created straight through the Auth admin API (as this script
    # does) is invisible there otherwise, even if they're correctly in the
    # professor's class. Set it here so the E2E fixture matches what a
    # student created through the normal "Créer un compte Étudiant" flow
    # would look like.
    fields = {"id": uid, "email": email, "full_name": full_name}
    if created_by:
        fields["created_by"] = created_by
    db.from_("profiles").upsert(fields).execute()


def ensure_role(uid: str, role: str) -> None:
    try:
        db.from_("user_roles").upsert({"user_id": uid, "role": role}).execute()
    except Exception:
        pass  # role already assigned — same "ignore duplicate" pattern used elsewhere in this codebase


def main():
    print("Seeding E2E fixture...")

    prof_id = get_or_create_user(PROF_EMAIL, PROF_PASSWORD, "E2E Professor")
    ensure_profile(prof_id, PROF_EMAIL, "E2E Professor")
    ensure_role(prof_id, "professor")
    print(f"[OK] professor {PROF_EMAIL} -> {prof_id}")

    student_id = get_or_create_user(STUDENT_EMAIL, STUDENT_PASSWORD, "E2E Student")
    ensure_profile(student_id, STUDENT_EMAIL, "E2E Student", created_by=prof_id)
    ensure_role(student_id, "student")
    print(f"[OK] student {STUDENT_EMAIL} -> {student_id}")

    existing_class = db.from_("classes").select("id").eq("name", CLASS_NAME).execute().data
    class_id = existing_class[0]["id"] if existing_class else (
        db.from_("classes").insert({"name": CLASS_NAME, "created_by": prof_id}).execute().data[0]["id"]
    )
    print(f"[OK] class -> {class_id}")

    try:
        db.from_("class_students").insert({"class_id": class_id, "student_id": student_id}).execute()
    except Exception:
        pass  # already a member

    existing_course = (
        db.from_("courses").select("id").eq("title", COURSE_TITLE).eq("professor_id", prof_id).execute().data
    )
    course_id = existing_course[0]["id"] if existing_course else (
        db.from_("courses").insert({"title": COURSE_TITLE, "professor_id": prof_id, "is_published": True}).execute().data[0]["id"]
    )
    print(f"[OK] course -> {course_id}")

    try:
        db.from_("class_courses").insert({"class_id": class_id, "course_id": course_id}).execute()
    except Exception:
        pass  # already assigned

    existing_module = (
        db.from_("course_modules").select("id").eq("course_id", course_id).eq("title", MODULE_TITLE).execute().data
    )
    module_id = existing_module[0]["id"] if existing_module else (
        db.from_("course_modules")
        .insert({"course_id": course_id, "order_num": 1, "title": MODULE_TITLE, "status": "published"})
        .execute().data[0]["id"]
    )
    print(f"[OK] module -> {module_id}")

    existing_lesson = (
        db.from_("course_lessons").select("id").eq("module_id", module_id).eq("title", LESSON_TITLE).execute().data
    )
    if existing_lesson:
        lesson_id = existing_lesson[0]["id"]
        db.from_("course_lessons").update({"slides": SLIDES, "status": "published"}).eq("id", lesson_id).execute()
    else:
        lesson_id = (
            db.from_("course_lessons")
            .insert({"module_id": module_id, "order_num": 1, "title": LESSON_TITLE, "status": "published", "slides": SLIDES})
            .execute().data[0]["id"]
        )
    print(f"[OK] lesson -> {lesson_id}")

    existing_module_2 = (
        db.from_("course_modules").select("id").eq("course_id", course_id).eq("title", MODULE_2_TITLE).execute().data
    )
    module_2_id = existing_module_2[0]["id"] if existing_module_2 else (
        db.from_("course_modules")
        .insert({"course_id": course_id, "order_num": 2, "title": MODULE_2_TITLE, "status": "published"})
        .execute().data[0]["id"]
    )
    print(f"[OK] module 2 -> {module_2_id}")

    existing_lesson_2 = (
        db.from_("course_lessons").select("id").eq("module_id", module_2_id).eq("title", LESSON_2_TITLE).execute().data
    )
    if not existing_lesson_2:
        db.from_("course_lessons").insert({
            "module_id": module_2_id, "order_num": 1, "title": LESSON_2_TITLE,
            "status": "published", "content": LESSON_2_CONTENT,
        }).execute()
    print(f"[OK] lesson 2 -> module {module_2_id}")

    # Exam Authoring Studio needs the student explicitly in course_enrollments
    # — that's the table exams.py / the exams RLS policies check for exam
    # access, which is a *different* mechanism than the class_students-based
    # access course_generation.py uses for course content (a pre-existing
    # split in this codebase, not something this fixture invents).
    try:
        db.from_("course_enrollments").insert({"course_id": course_id, "student_id": student_id}).execute()
    except Exception:
        pass  # already enrolled
    print(f"[OK] course_enrollments -> student enrolled in {course_id}")

    prof2_id = get_or_create_user(PROF2_EMAIL, PROF2_PASSWORD, "E2E Professor 2")
    ensure_profile(prof2_id, PROF2_EMAIL, "E2E Professor 2")
    ensure_role(prof2_id, "professor")
    print(f"[OK] professor 2 {PROF2_EMAIL} -> {prof2_id}")

    print("\nE2E fixture ready:")
    print(f"  Professor:   {PROF_EMAIL} / {PROF_PASSWORD}")
    print(f"  Professor 2: {PROF2_EMAIL} / {PROF2_PASSWORD}  (owns nothing — for ownership-boundary tests)")
    print(f"  Student:     {STUDENT_EMAIL} / {STUDENT_PASSWORD}")
    print(f"  Class:       {CLASS_NAME}  ({class_id})")
    print(f"  Course:      {COURSE_TITLE}  ({course_id})")


if __name__ == "__main__":
    main()
