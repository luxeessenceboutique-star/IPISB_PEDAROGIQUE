"""
Builds the IPISB "Certificat de Scolarité" Word template from the hand-made
v3 file by swapping each dotted blank ("…………") for a {{ placeholder }}.

Why placeholders instead of leaving the dots: field detection on a dotted
template goes through the LLM path (utils/templates._detect_fields_from_text),
which reads the *whole* document and cannot tell a blank to fill from fixed
boilerplate — it tagged the header, the director's name, the authorisation
number and the footer as "student data" and blanked them out. A {{ … }}
template takes utils/templates._detect_fields_jinja instead: one placeholder →
one field, deterministic, zero LLM, and every character outside the braces is
guaranteed untouched.

Only the dotted runs change; the rest of word/document.xml is copied byte for
byte, so the layout, fonts, logo and page borders stay exactly as designed.

Usage:  python build_certificat_scolarite.py <source.docx> <output.docx>
"""
import re
import shutil
import sys
import zipfile
from pathlib import Path

# In document order — each dotted blank of the v3 file, and the variable that
# replaces it. Order matters: several blanks share the same dot count.
PLACEHOLDERS = [
    "{{ nom_prenom }}",          # Certifie que :
    "{{ date_naissance }}",      # Né(e) le :
    "{{ date_inscription }}",    # A été inscrit(e) le :
    "{{ numero_inscription }}",  # Sous N° :
    "{{ classe }}",              # A poursuivi sa formation en classe :
    "{{ filiere }}",             # Filière de formation :
    "{{ niveau }}",              # Niveau de formation :
    "{{ date_edition }}",        # Fait à El Jadida, le
]

DOTTED_RUN = re.compile(r"(<w:t[^>]*>)…+(</w:t>)")


def build(src: Path, dst: Path) -> None:
    with zipfile.ZipFile(src) as zin:
        parts = {name: zin.read(name) for name in zin.namelist()}

    xml = parts["word/document.xml"].decode("utf-8")

    seen = 0

    def swap(m: re.Match) -> str:
        nonlocal seen
        if seen >= len(PLACEHOLDERS):
            raise SystemExit(f"More dotted blanks than placeholders ({seen + 1})")
        out = f"{m.group(1)}{PLACEHOLDERS[seen]}{m.group(2)}"
        seen += 1
        return out

    xml = DOTTED_RUN.sub(swap, xml)
    if seen != len(PLACEHOLDERS):
        raise SystemExit(f"Expected {len(PLACEHOLDERS)} dotted blanks, found {seen}")

    parts["word/document.xml"] = xml.encode("utf-8")

    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        # [Content_Types].xml first — Word rejects the archive otherwise.
        for name in sorted(parts, key=lambda n: n != "[Content_Types].xml"):
            zout.writestr(name, parts[name])

    print(f"{dst}  ({dst.stat().st_size} bytes, {seen} placeholders)")


if __name__ == "__main__":
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("Certificat_de_Scolarite_IPISB_v3.docx")
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).with_name("Certificat_de_Scolarite_IPISB.docx")
    if not source.exists():
        raise SystemExit(f"Source introuvable : {source}")
    if source.resolve() == target.resolve():
        shutil.copy(source, source.with_suffix(".bak.docx"))
    build(source, target)
