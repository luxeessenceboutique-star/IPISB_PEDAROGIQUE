"""Export Excel de la grille de Contrôle Continu (CC) d'une classe —
reproduit la feuille Excel manuscrite historique que l'établissement
utilisait pour suivre, pour TOUTE une cohorte, la note de CC de chaque
élève dans chaque UF (Unité de Formation) assignée à la classe : une seule
feuille, une ligne par élève, une colonne par UF (titre + coefficient en
en-tête), puis MPCC (Moyenne Pondérée des Contrôles Continus) en dernière
colonne.

Même garde-fou d'import circulaire que utils/pv_excel.py / utils/pv_docx.py :
ce fichier importe `_class_courses` / `compute_overall_average` depuis
routers.grades, qui elle-même doit importer `render_cc_grid_excel` depuis
CE fichier seulement DANS LE CORPS de son endpoint (import différé), jamais
en tête de module — sinon ImportError circulaire garanti (déjà confirmé
pour de vrai avec pv_excel.py cette session : "cannot import name ... from
partially initialized module 'routers.grades'").

Écrit directement avec l'API bas niveau d'openpyxl (Workbook / merge_cells /
Alignment / Border / Font / PatternFill) plutôt qu'avec utils/excel.py::
make_xlsx : make_xlsx ne sait produire qu'un en-tête à UN seul niveau (une
ligne de libellés de colonnes) + des lignes de données, alors que cette
feuille a besoin d'un en-tête à 3 niveaux avec fusions verticales ET
horizontales, d'une ligne de pied de tableau (moyenne de classe) et d'un
bloc de signature — rien de tout ça n'existe dans make_xlsx. On réutilise
seulement `utils.excel._THEMES["grey"]` pour la couleur de fond de l'en-tête,
afin de rester visuellement cohérent avec les autres exports Excel de l'app.
"""
import io
from pathlib import Path
from typing import Optional

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from supabase import Client

from utils import institution
from utils.documents import fr_year_label
from utils.excel import _THEMES

# Même logo que tous les exports Word de l'app (examen_docx.py / pv_docx.py
# via controle_continu_docx.py) — un seul fichier, jamais dupliqué.
LOGO_PATH = Path(__file__).resolve().parent.parent / "pptx_export" / "ipisb_logo.png"

# Mêmes caractères interdits dans un nom de feuille Excel que pv_excel.py
# (openpyxl lève une ValueError sinon — un nom de classe réel en contient,
# ex. "[DEMO] Infirmiers Polyvalents — Promo 2026").
_INVALID_SHEET_CHARS = str.maketrans({c: "" for c in "[]*?:/\\"})

_GREY_FILL = PatternFill("solid", fgColor=_THEMES["grey"]["header"])  # D5DBDB
# Rouge plein pour la ligne d'un élève dont la MPCC est < 10 — seuil repris
# du "<10 = échec" déjà utilisé ailleurs dans grades.py (_suggest_mention /
# compute_class_decisions). Cf. note de judgment call dans le rapport final.
# Rouge saturé (pas un rouge pâle) + texte blanc pour le contraste — vérifié
# visuellement via le rendu PDF/PNG que texte blanc reste lisible dessus.
_RED_FILL = PatternFill("solid", fgColor="C0392B")
_WHITE = "FFFFFF"
_THIN = Side(style="thin", color="BFC9CA")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

# Libellés affichés du bloc signature — EXACTEMENT les 4 rôles réels de
# l'établissement (cf. class_jury). Le premier est délibérément tout en
# majuscules sans accent : c'est le libellé de la feuille source, pas une
# incohérence de frappe.
_JURY_LABELS = [
    "PRESIDENT DE JURY D'EXAMEN",
    "Membre professionnel",
    "Membre formateur 1",
    "Membre formateur 2",
]


def _safe_sheet_name(name: str) -> str:
    cleaned = (name or "").translate(_INVALID_SHEET_CHARS).strip()
    return (cleaned or "CC")[:31]


def _class_info(db: Client, class_id: str) -> dict:
    """Nom de la classe + filière (specialties.name) + niveau (year_number,
    formaté via fr_year_label) — même requête/pattern que pv_docx.py::
    _class_info, dupliquée ici plutôt qu'importée (convention établie entre
    ces fichiers d'export frères). Lève ValueError si la classe n'existe
    pas (à l'appelant de la traduire en HTTPException 404)."""
    rows = (
        db.from_("classes").select("name, year_number, specialties(name)")
        .eq("id", class_id).execute().data or []
    )
    if not rows:
        raise ValueError(f"Classe introuvable : {class_id}")
    klass = rows[0]
    specialty = klass.get("specialties") or {}
    return {
        "name": klass.get("name") or class_id,
        "filiere": specialty.get("name") or "",
        "niveau": fr_year_label(klass.get("year_number")),
    }


def _class_students(db: Client, class_id: str) -> list[dict]:
    """Élèves de la classe, triés par nom (repli email) — [{id, full_name,
    email}]. Même requête que pv_docx.py::_class_students, dupliquée ici
    plutôt qu'importée (convention établie entre ces fichiers d'export
    frères — cf. pv_excel.py/pv_docx.py, qui font déjà de même)."""
    memberships = db.from_("class_students").select("student_id").eq("class_id", class_id).execute().data or []
    student_ids = list({m["student_id"] for m in memberships})
    if not student_ids:
        return []
    profiles = db.from_("profiles").select("id, full_name, email").in_("id", student_ids).execute().data or []
    profiles.sort(key=lambda p: (p.get("full_name") or p.get("email") or "").lower())
    return profiles


def _class_jury_members(db: Client, class_id: str) -> list[dict]:
    """Jury de la décision finale (class_jury, L70 — pas encore appliquée sur
    le projet Supabase en prod au moment d'écrire ce module) — toujours
    exactement 4 entrées {name, role}, dégradées en entrées vides si la
    table n'existe pas encore ou si la classe n'a pas de jury configuré.
    Même pattern que pv_docx.py::_class_jury_members, dupliqué ici à
    l'identique plutôt qu'importé."""
    try:
        rows = db.from_("class_jury").select("members").eq("class_id", class_id).execute().data
    except Exception:
        rows = None  # L70 pas encore appliquée
    members = list((rows[0].get("members") if rows else None) or [])[:4]
    while len(members) < 4:
        members.append({"name": "", "role": ""})
    return members


def _style_range(ws, cell_range: str, *, fill=None, font=None, alignment=None, border=None) -> None:
    """Applique fill/font/alignment/border à CHAQUE cellule d'une plage —
    nécessaire après ws.merge_cells() : openpyxl ne propage PAS le style de
    la cellule-ancre (en haut à gauche) au reste de la plage fusionnée. Les
    cellules non-ancres deviennent des `MergedCell` : elles refusent .value
    mais acceptent toujours fill/font/alignment/border, donc on les stylise
    une par une pour que la plage fusionnée ait une bordure/un fond continus."""
    for row in ws[cell_range]:
        for cell in row:
            if fill is not None:
                cell.fill = fill
            if font is not None:
                cell.font = font
            if alignment is not None:
                cell.alignment = alignment
            if border is not None:
                cell.border = border


def _write_letterhead(ws, ncol: int, filiere: str, niveau: str) -> int:
    """Bandeau institutionnel (logo + raison sociale + n° d'autorisation +
    filière/niveau de la classe) au-dessus de la grille — manquait
    entièrement dans la 1ère version de cet export (repéré par l'utilisateur
    en comparant au gabarit réel). Texte tiré exclusivement de
    utils/institution.py (jamais retapé à la main, cf. son propre docstring :
    source de vérité unique pour ces mentions légales).

    Le logo occupe SA PROPRE ligne, au-dessus du texte (pas à côté) : une 1ère
    version le mettait à côté, avec le texte confiné à la colonne 2..ncol
    pour ne pas le chevaucher — mais sur une classe à peu d'UF (ncol petit),
    cette colonne unique est bien trop étroite pour la raison sociale
    (~100 caractères) : le texte débordait sur de nombreuses lignes et
    chevauchait le bloc suivant (repéré en regardant le rendu réel d'une
    classe à 2 colonnes, cf. rapport de vérification). Logo au-dessus +
    texte sur la largeur complète 1..ncol (comme demandé) élimine le
    chevauchement quelle que soit la largeur de la table, au prix d'empiler
    verticalement plutôt que côte à côte.

    Retourne le numéro de ligne où la grille (en-tête à 3 lignes) doit
    commencer, pour que tous les indices de ligne en aval (first_data_row,
    footer_row, etc.) restent calculés en relatif plutôt qu'à la main."""
    row = 1
    # Plancher de largeur pour le texte institutionnel (même principe que
    # `zone_cols = max(ncol, 4)` plus bas pour le bloc signature) : sur une
    # classe à très peu d'UF (ncol=2 : juste "Nom & Prénom" + "MPCC*"), la
    # largeur réelle du tableau (~44 unités) est plus étroite que le cas où
    # ce rendu a été vérifié visuellement (~72 unités, 2 UF) — on étend donc
    # la fusion au-delà de `ncol` si besoin, dans des colonnes "virtuelles"
    # (largeur par défaut, jamais utilisées par la grille elle-même) plutôt
    # que de risquer un texte sur trop de lignes repliées.
    text_ncol = max(ncol, 6)

    if LOGO_PATH.exists():
        try:
            img = XLImage(str(LOGO_PATH))
            # Hauteur modeste (~90px, dans la fourchette ~80-120px) en
            # conservant le ratio réel du fichier.
            target_h = 90
            orig_w, orig_h = img.width, img.height
            img.height = target_h
            img.width = int(target_h * orig_w / orig_h) if orig_h else target_h
            ws.add_image(img, f"A{row}")
            ws.row_dimensions[row].height = 70  # ~93px — contient le logo de 90px sans déborder
            row += 1
        except Exception:
            pass  # logo illisible/corrompu : on dégrade sans faire planter l'export

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=text_ncol)
    name_cell = ws.cell(
        row=row, column=1,
        value=f"{institution.NAME.upper()} -{institution.LEGAL_STATUS}-",
    )
    name_cell.font = Font(bold=True, size=11)
    name_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    # Hauteur généreuse (~3 lignes à 11pt) : sur une classe à peu de colonnes
    # la largeur totale 1..ncol reste modeste, et la raison sociale complète
    # peut avoir besoin de plus de 2 lignes pour tenir sans être coupée.
    ws.row_dimensions[row].height = 48
    row += 1

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=text_ncol)
    auth_cell = ws.cell(row=row, column=1, value=institution.AUTHORIZATION)
    auth_cell.font = Font(size=10)
    auth_cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 20
    row += 1

    if filiere:
        label = f"Filière : {filiere}" + (f" ({niveau})" if niveau else "")
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=text_ncol)
        fil_cell = ws.cell(row=row, column=1, value=label)
        fil_cell.font = Font(bold=True, size=10)
        fil_cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        ws.row_dimensions[row].height = 18
        row += 1

    row += 1  # ligne vide de séparation avant la grille
    return row


def render_cc_grid_excel(db: Client, class_id: str) -> bytes:
    """Grille de Contrôle Continu d'une classe — une ligne par élève, une
    colonne par UF assignée à la classe (titre + coefficient en en-tête),
    note CC de l'élève dans chaque UF, MPCC (moyenne pondérée) en dernière
    colonne. Lève ValueError si la classe n'existe pas (à l'appelant de la
    traduire en HTTPException 404 — même convention que render_pv_excel ;
    ce fichier n'a pas de dépendance FastAPI)."""
    from routers.grades import _class_courses, compute_overall_average  # import différé : cf. note en tête de fichier

    info = _class_info(db, class_id)
    class_name, filiere, niveau = info["name"], info["filiere"], info["niveau"]
    # Ordre stable et déterministe des UF — fixé UNE fois ici (via ce seul
    # appel à _class_courses) et réutilisé pour les en-têtes ET pour indexer
    # les notes de chaque élève, plutôt que de faire confiance à l'ordre de
    # `courses` retourné par compute_overall_average (pas garanti identique
    # d'un élève à l'autre).
    courses = sorted(_class_courses(db, class_id), key=lambda c: c.get("title") or "")
    students = _class_students(db, class_id)
    jury_members = _class_jury_members(db, class_id)

    # Un seul appel compute_overall_average PAR ÉLÈVE (pas par élève × par
    # UF — elle calcule déjà toutes les UF d'un coup en interne via
    # compute_course_grade). `courses` dans son retour donne la note de
    # chaque UF pour CET élève ; on l'indexe par course_id pour ne pas
    # supposer qu'elle respecte l'ordre canonique ci-dessus.
    mpcc_by_student: dict[str, Optional[float]] = {}
    grades_by_student: dict[str, dict[str, Optional[float]]] = {}
    for s in students:
        sid = s["id"]
        result = compute_overall_average(db, sid, class_id)
        mpcc_by_student[sid] = result["average"]
        grades_by_student[sid] = {c["course_id"]: c["grade"] for c in result["courses"]}

    # "Moyenne de la classe" (pied de tableau) — amélioration délibérée par
    # rapport à la feuille source, qui laissait cette ligne vide : la calculer
    # pour de vrai est trivial avec les données déjà en main et strictement
    # plus utile qu'une ligne blanche. Moyenne simple (NON pondérée par
    # coefficient — demandé explicitement comme une moyenne de notes, pas une
    # UF supplémentaire dans la pondération MPCC), en excluant les élèves sans
    # note dans cette UF (même convention de non-comptage des notes manquantes
    # que partout ailleurs dans ce fichier/ grades.py — jamais compté comme 0).
    course_ids = [c["id"] for c in courses]
    course_class_avg: dict[str, Optional[float]] = {}
    for cid in course_ids:
        vals = [
            grades_by_student[s["id"]].get(cid)
            for s in students
            if grades_by_student[s["id"]].get(cid) is not None
        ]
        course_class_avg[cid] = round(sum(vals) / len(vals), 2) if vals else None

    mpcc_vals = [v for v in mpcc_by_student.values() if v is not None]
    class_mpcc_avg = round(sum(mpcc_vals) / len(mpcc_vals), 2) if mpcc_vals else None

    n_courses = len(courses)
    ncol = n_courses + 2  # col 1 = "Nom & Prénom", cols 2..n+1 = UF, dernière = "MPCC*"
    col_mpcc = ncol

    wb = Workbook()
    ws = wb.active
    ws.title = _safe_sheet_name(f"CC {class_name}")

    bold = Font(bold=True)
    small_italic = Font(italic=True, size=9)
    wrap_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center")

    # Bandeau institutionnel (logo + raison sociale + n° d'autorisation +
    # filière/niveau) — tout ce qui suit est calculé en relatif à partir de
    # `hr` (la ligne où commence l'en-tête à 3 lignes de la grille), jamais
    # en lignes codées en dur, pour ne jamais désynchroniser ces deux blocs.
    hr = _write_letterhead(ws, ncol, filiere, niveau)

    ws.row_dimensions[hr].height = 40  # bandeau titre — "taller row" (wrap_text sur peu de colonnes)
    ws.row_dimensions[hr + 1].height = 42  # titres d'UF (wrap_text)
    ws.row_dimensions[hr + 2].height = 16  # coefficients — petite ligne

    # ── Colonne 1 "Nom & Prénom" — fusion verticale sur les 3 lignes d'en-tête ─
    ws.merge_cells(start_row=hr, start_column=1, end_row=hr + 2, end_column=1)
    ws.cell(row=hr, column=1, value="Nom & Prénom")
    _style_range(ws, f"A{hr}:A{hr + 2}", font=bold, alignment=left, border=_BORDER)

    # ── Dernière colonne "MPCC*" — fusion verticale sur les 3 lignes d'en-tête,
    #    même fond gris que les colonnes UF ─────────────────────────────────
    last_col_letter = get_column_letter(col_mpcc)
    ws.merge_cells(start_row=hr, start_column=col_mpcc, end_row=hr + 2, end_column=col_mpcc)
    ws.cell(row=hr, column=col_mpcc, value="MPCC*")
    _style_range(
        ws, f"{last_col_letter}{hr}:{last_col_letter}{hr + 2}",
        fill=_GREY_FILL, font=bold, alignment=center, border=_BORDER,
    )

    # ── Colonnes UF (titre + coefficient, bandeau titre fusionné) ───────────
    if n_courses:
        first_uf_col, last_uf_col = 2, n_courses + 1
        first_letter, last_letter = get_column_letter(first_uf_col), get_column_letter(last_uf_col)

        ws.merge_cells(start_row=hr, start_column=first_uf_col, end_row=hr, end_column=last_uf_col)
        ws.cell(row=hr, column=first_uf_col, value="Contrôles Continus (durant tout le cursus de formation)")
        # wrap_text (pas `center` simple) : sur une classe à peu d'UF, la
        # plage fusionnée est trop étroite pour le titre sur une seule ligne —
        # sans wrap_text, Excel le clippe au lieu de l'afficher sur 2 lignes
        # (repéré en regardant le rendu réel, cf. rapport de vérification).
        _style_range(
            ws, f"{first_letter}{hr}:{last_letter}{hr}",
            fill=_GREY_FILL, font=bold, alignment=wrap_center, border=_BORDER,
        )

        for j, c in enumerate(courses, start=2):
            title_cell = ws.cell(row=hr + 1, column=j, value=c.get("title") or "UF")
            title_cell.fill, title_cell.font, title_cell.alignment, title_cell.border = (
                _GREY_FILL, bold, wrap_center, _BORDER,
            )
            coeff_cell = ws.cell(row=hr + 2, column=j, value=c.get("credits"))
            coeff_cell.fill, coeff_cell.font, coeff_cell.alignment, coeff_cell.border = (
                _GREY_FILL, Font(size=9), center, _BORDER,
            )

    # ── Lignes élèves ────────────────────────────────────────────────────────
    first_data_row = hr + 3  # juste après les 3 lignes d'en-tête de la grille
    for i, s in enumerate(students):
        r = first_data_row + i
        sid = s["id"]
        name = s.get("full_name") or s.get("email") or "—"
        mpcc = mpcc_by_student.get(sid)
        is_fail = mpcc is not None and mpcc < 10  # seuil "<10 = échec" — cf. note en tête de fichier

        name_cell = ws.cell(row=r, column=1, value=name)
        name_cell.alignment, name_cell.border = left, _BORDER

        for j, c in enumerate(courses, start=2):
            grade = grades_by_student.get(sid, {}).get(c["id"])
            cell = ws.cell(row=r, column=j, value=grade)
            cell.number_format, cell.alignment, cell.border = "0.00", center, _BORDER

        mpcc_cell = ws.cell(row=r, column=col_mpcc, value=mpcc)
        mpcc_cell.number_format, mpcc_cell.font, mpcc_cell.alignment, mpcc_cell.border = (
            "0.00", bold, center, _BORDER,
        )

        if is_fail:
            for j in range(1, ncol + 1):
                cell = ws.cell(row=r, column=j)
                cell.fill = _RED_FILL
                # Texte blanc pour rester lisible sur le rouge plein — on
                # garde le gras déjà posé (colonne MPCC) plutôt que de
                # l'écraser.
                cell.font = Font(color=_WHITE, bold=cell.font.bold if cell.font else False)

    if students:
        footer_row = first_data_row + len(students)
    else:
        # Pas d'élève inscrit : une ligne de notice pour que la feuille se
        # lise comme "classe vide" plutôt que comme un export cassé.
        ws.merge_cells(start_row=first_data_row, start_column=1, end_row=first_data_row, end_column=ncol)
        notice = ws.cell(row=first_data_row, column=1, value="Aucun élève inscrit dans cette classe.")
        notice.font, notice.alignment = Font(italic=True), center
        footer_row = first_data_row + 1

    # ── Pied de tableau : "Moyenne de la classe" ────────────────────────────
    label_cell = ws.cell(row=footer_row, column=1, value="Moyenne de la classe")
    label_cell.font, label_cell.alignment, label_cell.border = bold, left, _BORDER

    for j, c in enumerate(courses, start=2):
        cell = ws.cell(row=footer_row, column=j, value=course_class_avg.get(c["id"]))
        cell.number_format, cell.font, cell.alignment, cell.border = "0.00", bold, center, _BORDER

    avg_cell = ws.cell(row=footer_row, column=col_mpcc, value=class_mpcc_avg)
    avg_cell.number_format, avg_cell.font, avg_cell.alignment, avg_cell.border = "0.00", bold, center, _BORDER

    # ── Largeurs de colonnes ────────────────────────────────────────────────
    ws.column_dimensions["A"].width = 32
    for j in range(2, ncol):
        ws.column_dimensions[get_column_letter(j)].width = 14
    ws.column_dimensions[get_column_letter(col_mpcc)].width = 12

    # ── Note de bas de tableau ───────────────────────────────────────────────
    r = footer_row + 2
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncol)
    footnote = ws.cell(row=r, column=1, value=(
        "* MPCC : Moyenne pondérée des notes des contrôles continus durant "
        "tout le cursus de formation (en tenant compte des coefficients "
        "d'évaluation Ci)"
    ))
    footnote.font, footnote.alignment = small_italic, left

    # ── Bloc signature ───────────────────────────────────────────────────────
    r += 2
    sig_heading = ws.cell(row=r, column=1, value="Signature :")
    sig_heading.font = Font(bold=True, underline="single")
    sig_heading.alignment = left

    r += 1
    label_row, name_row = r, r + 1
    # Hauteur généreuse + wrap_text (ci-dessous) : sur une classe à peu d'UF,
    # les colonnes réelles sont étroites (14/12) et un libellé comme "Membre
    # professionnel" ne tient pas sur une ligne — sans wrap_text le texte
    # débordait sur la cellule voisine au lieu d'être contenu (repéré sur le
    # rendu réel, cf. rapport de vérification).
    ws.row_dimensions[label_row].height = 30
    ws.row_dimensions[name_row].height = 24
    # Répartit les 4 libellés du jury sur toute la largeur du tableau (pas
    # seulement les 4 premières colonnes réelles) : étend la zone à 4
    # colonnes minimum pour rester cohérent même sur une classe à 0/1 UF
    # (ncol très petit), en répartissant le reste le plus uniformément
    # possible sinon.
    zone_cols = max(ncol, 4)
    base, rem = divmod(zone_cols, 4)
    col_cursor = 1
    for i, label in enumerate(_JURY_LABELS):
        span = base + (1 if i < rem else 0)
        start_col, end_col = col_cursor, col_cursor + span - 1
        col_cursor = end_col + 1

        if end_col > start_col:
            ws.merge_cells(start_row=label_row, start_column=start_col, end_row=label_row, end_column=end_col)
            ws.merge_cells(start_row=name_row, start_column=start_col, end_row=name_row, end_column=end_col)

        lbl_cell = ws.cell(row=label_row, column=start_col, value=label)
        lbl_cell.font, lbl_cell.alignment = Font(bold=True, size=10), wrap_center

        member = jury_members[i] if i < len(jury_members) else {}
        name_cell = ws.cell(row=name_row, column=start_col, value=member.get("name") or "")
        name_cell.font, name_cell.alignment = Font(italic=True, size=10), wrap_center

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
