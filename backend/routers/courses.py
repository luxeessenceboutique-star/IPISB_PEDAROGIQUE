from fastapi import APIRouter, Depends, HTTPException
from typing import Annotated
from supabase import Client
from deps import get_current_user, get_db, CurrentUser
from models import CourseCreate, CourseUpdate

router = APIRouter(prefix="/courses", tags=["courses"])


def _build_course_list(courses: list, db: Client, user: CurrentUser) -> list:
    """Annotate courses with professor name, enrollment count, and assigned classes."""
    if not courses:
        return []

    course_ids = [c["id"] for c in courses]

    # Assigned classes per course
    class_rows = db.from_("class_courses").select("course_id, class_id").in_("course_id", course_ids).execute().data or []
    course_to_class_ids: dict[str, list[str]] = {}
    all_class_ids: set[str] = set()
    for r in class_rows:
        course_to_class_ids.setdefault(r["course_id"], []).append(r["class_id"])
        all_class_ids.add(r["class_id"])

    # Class names
    class_name_map: dict[str, str] = {}
    if all_class_ids:
        cls_rows = db.from_("classes").select("id, name").in_("id", list(all_class_ids)).execute().data or []
        class_name_map = {c["id"]: c["name"] for c in cls_rows}

    # Student count per course (unique students across all assigned classes)
    enrollment_count: dict[str, int] = {}
    if all_class_ids:
        student_rows = db.from_("class_students").select("class_id, student_id").in_("class_id", list(all_class_ids)).execute().data or []
        class_to_students: dict[str, set[str]] = {}
        for r in student_rows:
            class_to_students.setdefault(r["class_id"], set()).add(r["student_id"])
        for course_id, cls_ids in course_to_class_ids.items():
            unique_students: set[str] = set()
            for cid in cls_ids:
                unique_students |= class_to_students.get(cid, set())
            enrollment_count[course_id] = len(unique_students)

    # Professor names
    prof_ids = list({c["professor_id"] for c in courses if c.get("professor_id")})
    prof_map: dict[str, str] = {}
    if prof_ids:
        profs = db.from_("profiles").select("id, full_name").in_("id", prof_ids).execute().data or []
        prof_map = {p["id"]: (p["full_name"] or "—") for p in profs}

    # Module count (content volume) per course.
    module_count: dict[str, int] = {}
    mod_rows = db.from_("course_modules").select("course_id").in_("course_id", course_ids).execute().data or []
    for r in mod_rows:
        module_count[r["course_id"]] = module_count.get(r["course_id"], 0) + 1

    return [
        {
            **c,
            "professor_name": prof_map.get(c.get("professor_id", ""), "—") if c.get("professor_id") else "—",
            "enrollment_count": enrollment_count.get(c["id"], 0),
            "module_count": module_count.get(c["id"], 0),
            "is_enrolled": True,
            "assigned_classes": [
                {"id": cid, "name": class_name_map.get(cid, "?")}
                for cid in course_to_class_ids.get(c["id"], [])
            ],
        }
        for c in courses
    ]


@router.get("")
async def list_courses(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    is_student = not user.can_create()

    if is_student:
        # Students see only courses whose assigned classes they belong to
        student_classes = db.from_("class_students").select("class_id").eq("student_id", user.id).execute().data or []
        class_ids = [m["class_id"] for m in student_classes]
        if not class_ids:
            return []
        cc_rows = db.from_("class_courses").select("course_id").in_("class_id", class_ids).execute().data or []
        course_ids = list({r["course_id"] for r in cc_rows})
        if not course_ids:
            return []
        courses = db.from_("courses").select("*").in_("id", course_ids).order("created_at", desc=True).execute().data or []
    elif user.is_admin():
        courses = db.from_("courses").select("*").order("created_at", desc=True).execute().data or []
    else:
        # Professor sees their own courses
        courses = db.from_("courses").select("*").eq("professor_id", user.id).order("created_at", desc=True).execute().data or []

    return _build_course_list(courses, db, user)


@router.get("/list")
async def list_courses_simple(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    return db.from_("courses").select("id, title").order("title").execute().data or []


@router.post("")
async def create_course(
    body: CourseCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if not user.can_create():
        raise HTTPException(403, "Only professors and admins can create courses")
    # Required going forward so AI generation has something real to ground on
    # beyond the title (see utils/course_generation.py) — only enforced here,
    # at creation. Existing courses created before this check, and rows
    # inserted directly (seed_e2e.py, bulk imports), are untouched: nothing
    # downstream requires a description, generation just uses it when present.
    if not body.description or len(body.description.strip()) < 15:
        raise HTTPException(400, "La description est obligatoire (au moins 15 caractères) pour permettre une génération IA fiable.")

    res = db.from_("courses").insert({
        "title":       body.title,
        "description": body.description,
        "code":        body.code,
        "semester":    body.semester,
        "credits":     body.credits,
        "cover_color": body.cover_color,
        "professor_id": user.id,
        "is_published": True,
    }).execute()
    created = res.data[0]

    # Assign to selected classes
    for class_id in body.class_ids:
        try:
            db.from_("class_courses").insert({
                "class_id":  class_id,
                "course_id": created["id"],
            }).execute()
        except Exception:
            pass  # ignore duplicate

    return created


@router.patch("/{course_id}")
async def update_course(
    course_id: str,
    body: CourseUpdate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    course = db.from_("courses").select("professor_id").eq("id", course_id).execute().data
    if not course:
        raise HTTPException(404, "Cours introuvable")
    if not user.is_admin() and course[0]["professor_id"] != user.id:
        raise HTTPException(403, "Non autorisé")

    fields: dict = {}
    if body.title       is not None: fields["title"]       = body.title
    if body.description is not None: fields["description"] = body.description
    if body.code        is not None: fields["code"]        = body.code
    if body.semester    is not None: fields["semester"]    = body.semester
    if body.credits     is not None: fields["credits"]     = body.credits
    if body.cover_color is not None: fields["cover_color"] = body.cover_color
    if fields:
        db.from_("courses").update(fields).eq("id", course_id).execute()

    if body.class_ids is not None:
        db.from_("class_courses").delete().eq("course_id", course_id).execute()
        for class_id in body.class_ids:
            try:
                db.from_("class_courses").insert({"class_id": class_id, "course_id": course_id}).execute()
            except Exception:
                pass

    return {"ok": True}


@router.post("/{course_id}/classes/{class_id}")
async def assign_course_to_class(
    course_id: str,
    class_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    course = db.from_("courses").select("professor_id").eq("id", course_id).execute().data
    if not course:
        raise HTTPException(404, "Cours introuvable")
    if not user.is_admin() and course[0]["professor_id"] != user.id:
        raise HTTPException(403, "Non autorisé")
    try:
        db.from_("class_courses").insert({"class_id": class_id, "course_id": course_id}).execute()
    except Exception as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@router.delete("/{course_id}/classes/{class_id}")
async def unassign_course_from_class(
    course_id: str,
    class_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    course = db.from_("courses").select("professor_id").eq("id", course_id).execute().data
    if not course:
        raise HTTPException(404, "Cours introuvable")
    if not user.is_admin() and course[0]["professor_id"] != user.id:
        raise HTTPException(403, "Non autorisé")
    db.from_("class_courses").delete().eq("course_id", course_id).eq("class_id", class_id).execute()
    return {"ok": True}


@router.delete("/{course_id}")
async def delete_course(
    course_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    course = db.from_("courses").select("professor_id").eq("id", course_id).execute().data
    if not course:
        raise HTTPException(404, "Not found")
    if not user.is_admin() and course[0]["professor_id"] != user.id:
        raise HTTPException(403, "Not authorized")
    db.from_("class_courses").delete().eq("course_id", course_id).execute()
    db.from_("courses").delete().eq("id", course_id).execute()
    return {"ok": True}


@router.post("/{course_id}/enroll")
async def enroll(
    course_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    if user.can_create():
        raise HTTPException(403, "Only students can enroll in courses")
    try:
        db.from_("course_enrollments").insert({"course_id": course_id, "student_id": user.id}).execute()
    except Exception as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@router.delete("/{course_id}/enroll")
async def unenroll(
    course_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Client, Depends(get_db)],
):
    db.from_("course_enrollments").delete().eq("course_id", course_id).eq("student_id", user.id).execute()
    return {"ok": True}
