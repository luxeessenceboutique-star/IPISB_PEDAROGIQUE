"""IPISB's official identity — the exact wording a government body, an
employer or an embassy expects to see on an attestation, printed byte-for-
byte as the institution provided it. Every generator that prints an
official document (utils/documents.py, utils/pdf_generators.py,
routers/document_templates.py's placeholder context) imports from here
instead of hardcoding its own copy, so a correction only ever needs to
happen once — and so the same three past mistakes (a fake phone number, a
generic "El Jadida, Maroc" instead of the real postal address, and one PDF
generator that printed "Rabat" because it was copied from an unrelated
project) can't quietly reappear in a fourth place later.

Do not edit these values without new instructions from the institution —
they are legal/administrative facts (authorization number, registered
address), not copy to improve on.
"""

NAME = "Institut Privé d'Innovation en Santé et Bien-être"
SHORT_NAME = "IPISB"
CITY = "El Jadida"
LEGAL_STATUS = "Établissement de Formation Professionnelle Privé"
AUTHORIZATION = "Autorisé sous N° 3/02/3/2024 du 09/07/2024"
ADDRESS = "Sise au 24, 3ème étage, Lotissement Ennajd, El Jadida — MAROC"
PHONE = "06 32 82 28 98"
WEBSITE = "www.ipisb.com"
EMAIL = "ipisbj.infirmiers@gmail.com"

# One line, for a letterhead's contact row: "Tél : … • www.… • …@…"
CONTACT_LINE = f"Tél : {PHONE}   •   {WEBSITE}   •   {EMAIL}"

# The certificat de scolarité's real signatory — printed exactly as
# supplied ("Je soussignée", feminine, is part of the given wording, not a
# guess at the director's gender to be re-derived if the incumbent changes;
# update this constant instead).
DIRECTOR_CIVILITY = "Mme"
DIRECTOR_NAME = "TALAH LAILA"
DIRECTOR_TITLE = "Directrice de l'Établissement"
