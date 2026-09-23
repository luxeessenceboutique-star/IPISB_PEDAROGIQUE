from pydantic import BaseModel
from typing import Optional


class CourseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    code: Optional[str] = None
    semester: Optional[str] = None
    credits: int = 3
    cover_color: str = "blue"
    class_ids: list[str] = []


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    code: Optional[str] = None
    semester: Optional[str] = None
    credits: Optional[int] = None
    cover_color: Optional[str] = None
    class_ids: Optional[list[str]] = None


class AssignmentCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None
    max_grade: float = 20
    course_id: str
    # Évaluation créée depuis le raccourci "Note directe" (page Notes) plutôt
    # que le circuit normal Contrôle continu : is_quick_grade=true dispense
    # l'élève de remise préalable ; quick_grade_category fixe si elle compte
    # dans devoir_avg ("devoir") ou exam_avg ("exam") — cf. grades.py.
    is_quick_grade: bool = False
    quick_grade_category: Optional[str] = None


class SubmissionCreate(BaseModel):
    content: Optional[str] = None
    file_url: Optional[str] = None


class GradeInput(BaseModel):
    grade: Optional[float] = None
    feedback: Optional[str] = None


class QuickGradesUpsert(BaseModel):
    """Saisie directe des notes d'une évaluation (page Notes) — {student_id: note}."""
    grades: dict[str, Optional[float]]


class QuestionCreate(BaseModel):
    question: str
    options: list[str]
    correct_index: int
    order_num: int = 0
    type: str = "multiple_choice"  # 'multiple_choice' | 'true_false'
    difficulty: str = "medium"     # 'easy' | 'medium' | 'hard'
    points: float = 1
    source_module_id: Optional[str] = None
    source_lesson_id: Optional[str] = None


class QuestionUpdate(BaseModel):
    """All fields optional — PATCH only touches what the professor actually
    changed. Image is edited through the dedicated upload/delete endpoints,
    not here."""
    question: Optional[str] = None
    options: Optional[list[str]] = None
    correct_index: Optional[int] = None
    type: Optional[str] = None
    difficulty: Optional[str] = None
    points: Optional[float] = None
    source_module_id: Optional[str] = None
    source_lesson_id: Optional[str] = None


class QuestionsReorder(BaseModel):
    question_ids: list[str]  # full set of this exam's question ids, in the new display order


class ExamContentScope(BaseModel):
    """What course content this exam draws from — persisted so the
    selection survives a refresh and (Phase 2) is what gets handed to the
    AI generator. mode='full_course' ignores module_ids/lesson_ids."""
    mode: str = "selected"  # 'full_course' | 'selected'
    module_ids: list[str] = []
    lesson_ids: list[str] = []


class ExamGenerationConfig(BaseModel):
    """Configuration screen (§5) values — read by Phase 2's AI generation,
    but persisted now so the draft survives a refresh even before that
    exists."""
    target_question_count: int = 10
    question_types: list[str] = ["multiple_choice"]
    difficulty_mix: dict[str, int] = {"easy": 20, "medium": 60, "hard": 20}
    default_points: float = 1


class ExamCreate(BaseModel):
    title: str
    description: Optional[str] = None
    duration_minutes: int = 60
    start_time: Optional[str] = None
    course_id: str
    type: str = "examen"  # 'examen' | 'quiz'
    questions: list[QuestionCreate] = []
    content_scope: Optional[ExamContentScope] = None
    generation_config: Optional[ExamGenerationConfig] = None
    randomize_questions: bool = False
    randomize_answers: bool = False


class ExamUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    start_time: Optional[str] = None
    type: Optional[str] = None
    content_scope: Optional[ExamContentScope] = None
    generation_config: Optional[ExamGenerationConfig] = None
    randomize_questions: Optional[bool] = None
    randomize_answers: Optional[bool] = None


class ExamAnswers(BaseModel):
    answers: dict[str, int]


class GenerateQuestionsRequest(BaseModel):
    course_id: str
    topic: Optional[str] = None
    num_questions: int = 5


class MeetingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    course_id: Optional[str] = None
    class_id: Optional[str] = None
    scheduled_at: str
    duration_minutes: int = 60


class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: str
    end_time: Optional[str] = None
    event_type: str = "event"
    course_id: Optional[str] = None


class RoleAction(BaseModel):
    role: str
    action: str  # "add" or "remove"


class CreateUserRequest(BaseModel):
    email: str
    full_name: str
    password: str  # Temporary password set by creator
    role: Optional[str] = None  # must be one of the caller's assignable_roles(); professor callers may omit it (always "student")


class ClassCreate(BaseModel):
    name: str
    description: Optional[str] = None
    specialty_id: Optional[str] = None
    year_number: Optional[int] = None
    formation_id: Optional[str] = None
    trainer_id: Optional[str] = None
    start_date: Optional[str] = None
    duration_months: Optional[int] = None


class ClassUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    specialty_id: Optional[str] = None
    year_number: Optional[int] = None
    formation_id: Optional[str] = None
    trainer_id: Optional[str] = None
    start_date: Optional[str] = None
    duration_months: Optional[int] = None


class FormationCreate(BaseModel):
    name: str
    code: Optional[str] = None
    default_duration_months: Optional[int] = None
    description: Optional[str] = None


class AddStudentRequest(BaseModel):
    student_id: str


class TransferStudentRequest(BaseModel):
    to_class_id: str  # classe cible (doit être de la même filière/formation)


class StudentUpdate(BaseModel):
    full_name: Optional[str] = None
    statut: Optional[str] = None
    photo_url: Optional[str] = None


class StudentDetailsUpdate(BaseModel):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    date_naissance: Optional[str] = None  # ISO AAAA-MM-JJ
    lieu_naissance: Optional[str] = None
    cin: Optional[str] = None
    matricule: Optional[str] = None
    telephone: Optional[str] = None
    email_personnel: Optional[str] = None
    adresse: Optional[str] = None
    bac_annee: Optional[str] = None


class DocumentGenerate(BaseModel):
    type: str  # 'attestation_scolarite' | 'certificat' | 'convocation' | 'releve_notes'
    student_id: str


class ScheduleCreate(BaseModel):
    class_id: Optional[str] = None
    professor_id: Optional[str] = None
    course_id: Optional[str] = None
    room: str
    title: Optional[str] = None
    start_time: str
    end_time: str
    recurrence: str = "once"  # 'once' | 'weekly'


class ScheduleUpdate(BaseModel):
    class_id: Optional[str] = None
    professor_id: Optional[str] = None
    course_id: Optional[str] = None
    room: Optional[str] = None
    title: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    recurrence: Optional[str] = None


# ── Specialties (filières) ──────────────────────────────────────────────────
SPECIALTY_TYPES = {"formation_initiale", "formation_continue"}


class SpecialtyCreate(BaseModel):
    name: str
    type: str = "formation_initiale"


class SpecialtyUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None


# ── Attendance ───────────────────────────────────────────────────────────────
class AttendanceEntry(BaseModel):
    student_id: str
    status: str = "present"  # 'present' | 'absent' | 'retard' | 'excuse'


class AttendanceMark(BaseModel):
    entries: list[AttendanceEntry]


# ── Continuous-assessment grade weighting ───────────────────────────────────
class CourseGradeWeightsUpdate(BaseModel):
    exam_weight: int
    devoir_weight: int
    quiz_weight: int


class AnnouncementCreate(BaseModel):
    titre: str
    corps: str
    audience_roles: list[str] = []


class TimetableCreate(BaseModel):
    class_id: str
    academic_year: str
    week_start: str  # date "YYYY-MM-DD", Monday
    week_end: str    # date "YYYY-MM-DD", Friday


class TimetableSlotCreate(BaseModel):
    day_of_week: int    # 0=Lundi .. 4=Vendredi
    start_time: str     # "HH:MM"
    end_time: str       # "HH:MM"
    subject: Optional[str] = None
    slot_type: str = "course"  # 'course' | 'exam'
    professor_id: Optional[str] = None
    room: Optional[str] = None


class TimetableSlotUpdate(BaseModel):
    day_of_week: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    subject: Optional[str] = None
    slot_type: Optional[str] = None
    professor_id: Optional[str] = None
    room: Optional[str] = None


class CategoryCreate(BaseModel):
    name: str
    code: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None


class CategoryArticleCreate(BaseModel):
    article: str
    code_article: Optional[str] = None
    caracteristiques: Optional[str] = None
    commentaire: Optional[str] = None


class CategoryArticleUpdate(BaseModel):
    article: Optional[str] = None
    code_article: Optional[str] = None
    caracteristiques: Optional[str] = None
    commentaire: Optional[str] = None


class SupplierCreate(BaseModel):
    company_name: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_number: Optional[str] = None
    legal_form: Optional[str] = None
    rib: Optional[str] = None
    bank: Optional[str] = None
    bank_branch: Optional[str] = None
    payment_terms_days: Optional[int] = None
    notes: Optional[str] = None
    comment: Optional[str] = None


class SupplierUpdate(BaseModel):
    company_name: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    tax_number: Optional[str] = None
    legal_form: Optional[str] = None
    rib: Optional[str] = None
    bank: Optional[str] = None
    bank_branch: Optional[str] = None
    payment_terms_days: Optional[int] = None
    notes: Optional[str] = None


class PurchaseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category_id: Optional[str] = None
    supplier_id: Optional[str] = None
    quantity: float = 1
    unit_price: float = 0
    vat_percent: float = 20
    currency: str = "MAD"
    purchase_date: Optional[str] = None
    payment_status: str = "pending"  # 'pending' | 'partially_paid' | 'paid'
    payment_method: Optional[str] = None
    approved_by: Optional[str] = None
    notes: Optional[str] = None
    comment: Optional[str] = None


class TemplateGenerate(BaseModel):
    student_id: Optional[str] = None
    employee_id: Optional[str] = None


class PurchaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category_id: Optional[str] = None
    supplier_id: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    vat_percent: Optional[float] = None
    currency: Optional[str] = None
    purchase_date: Optional[str] = None
    payment_status: Optional[str] = None
    payment_method: Optional[str] = None
    approved_by: Optional[str] = None
    notes: Optional[str] = None
    purchase_request_id: Optional[str] = None   # lien DA (Phase 2)
    quotation_id: Optional[str] = None           # devis retenu (Phase 2)


# ── Invoices (factures fournisseurs) ─────────────────────────────────────────
class InvoiceCreate(BaseModel):
    invoice_number: str
    supplier_id: Optional[str] = None
    purchase_id: Optional[str] = None       # commande liée (N° de commande affiché)
    class_id: Optional[str] = None          # promo rattachée (facturation élève)
    student_id: Optional[str] = None        # élève concerné
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    amount: float = 0                       # HT
    vat_percent: float = 20
    payment_status: str = "pending"         # 'pending' | 'partially_paid' | 'paid'
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None    # 'ov_permanent'|'ov_ponctuel'|'cheque'|'versement'|'espece'|'autre'
    comment: Optional[str] = None


class InvoiceUpdate(BaseModel):
    invoice_number: Optional[str] = None
    supplier_id: Optional[str] = None
    purchase_id: Optional[str] = None
    class_id: Optional[str] = None
    student_id: Optional[str] = None
    invoice_date: Optional[str] = None
    due_date: Optional[str] = None
    amount: Optional[float] = None
    vat_percent: Optional[float] = None
    payment_status: Optional[str] = None
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None
    comment: Optional[str] = None


# ── Expenses (dépenses) ──────────────────────────────────────────────────────
class ExpenseCreate(BaseModel):
    title: str
    category_id: Optional[str] = None
    supplier_id: Optional[str] = None
    amount: float = 0
    expense_date: Optional[str] = None
    payment_method: Optional[str] = None
    description: Optional[str] = None
    comment: Optional[str] = None
    caracteristiques: Optional[str] = None       # specs / modèle (dépenses d'équipement)
    warranty_end_date: Optional[str] = None      # fin de garantie
    beneficiary: Optional[str] = None            # utilisateur / demandeur


class ExpenseUpdate(BaseModel):
    title: Optional[str] = None
    category_id: Optional[str] = None
    supplier_id: Optional[str] = None
    amount: Optional[float] = None
    expense_date: Optional[str] = None
    payment_method: Optional[str] = None
    description: Optional[str] = None
    comment: Optional[str] = None
    caracteristiques: Optional[str] = None
    warranty_end_date: Optional[str] = None
    beneficiary: Optional[str] = None


# ── Budgets (budget prévisionnel par catégorie / année / mois / plage) ───────
class BudgetCreate(BaseModel):
    category_id: str
    year: int
    month: Optional[int] = None             # None = budget annuel ou plage
    start_date: Optional[str] = None        # renseignées ensemble = budget « du … au … »
    end_date: Optional[str] = None
    amount: float = 0
    comment: Optional[str] = None


class BudgetUpdate(BaseModel):
    category_id: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    amount: Optional[float] = None
    comment: Optional[str] = None


# ── Revenues (recettes) ──────────────────────────────────────────────────────
class RevenueCreate(BaseModel):
    title: str
    revenue_type: str = "other"             # 'tuition'|'subsidy'|'donation'|'service'|'other'
    category_id: Optional[str] = None
    amount: float = 0                       # HT
    vat_percent: float = 0
    payment_method: Optional[str] = None
    status: str = "received"                # 'expected' | 'received' | 'cancelled'
    revenue_date: Optional[str] = None
    description: Optional[str] = None
    class_id: Optional[str] = None          # promo rattachée (analytique formation)
    student_id: Optional[str] = None        # élève ayant payé (analytique formation)
    comment: Optional[str] = None


class RevenueUpdate(BaseModel):
    title: Optional[str] = None
    revenue_type: Optional[str] = None
    category_id: Optional[str] = None
    amount: Optional[float] = None
    vat_percent: Optional[float] = None
    payment_method: Optional[str] = None
    status: Optional[str] = None
    revenue_date: Optional[str] = None
    description: Optional[str] = None
    class_id: Optional[str] = None
    student_id: Optional[str] = None


# ── Phase 2 — Demandes d'achat (DA) & devis ──────────────────────────────────
class PurchaseRequestCreate(BaseModel):
    company: Optional[str] = None
    service: Optional[str] = None
    requester_name: Optional[str] = None
    project: Optional[str] = None
    activity: Optional[str] = None
    justification: Optional[str] = None
    request_type: str = "nouveau_besoin"        # 'nouveau_besoin' | 'renouvellement'
    asset_category: str = "consommable"         # 'consommable'|'equipement'|'locaux'|'service'
    category_id: Optional[str] = None           # accounting_categories — même liste que Dépenses
    characteristics: Optional[str] = None
    conformity_note: Optional[str] = None
    conformity_criteria: list[str] = []
    article_code: Optional[str] = None
    quantity: float = 1
    budget_estimate: float = 0
    duration: Optional[str] = None
    comment: Optional[str] = None


class PurchaseRequestUpdate(BaseModel):
    company: Optional[str] = None
    service: Optional[str] = None
    requester_name: Optional[str] = None
    project: Optional[str] = None
    activity: Optional[str] = None
    justification: Optional[str] = None
    request_type: Optional[str] = None
    asset_category: Optional[str] = None
    category_id: Optional[str] = None
    characteristics: Optional[str] = None
    conformity_note: Optional[str] = None
    conformity_criteria: Optional[list[str]] = None
    article_code: Optional[str] = None
    quantity: Optional[float] = None
    budget_estimate: Optional[float] = None
    duration: Optional[str] = None
    quote_synthesis: Optional[str] = None
    payment_mode: Optional[str] = None
    payment_terms_days: Optional[int] = None
    nc: Optional[str] = None                     # 'noir' | 'comptable'


class DecisionInput(BaseModel):
    decision: str                                # 'validation' | 'retour' | 'annulation'
    comment: Optional[str] = None


class QuoteSelectInput(BaseModel):
    quotation_id: str
    decision: str = "validation"                 # 'validation' | 'retour' | 'annulation'
    comment: Optional[str] = None


# ── Journal de caisse ─────────────────────────────────────────────────────────
class CashJournalEntryCreate(BaseModel):
    entry_date: Optional[str] = None             # défaut = aujourd'hui
    type: str = "sortie"                         # 'entree' | 'sortie'
    action: str
    prestataire: Optional[str] = None
    amount: float = 0                            # DH, valeur positive
    justificatif: Optional[str] = None
    nc: str = "comptable"                        # 'noir' | 'comptable'
    channel: str = "caisse"                      # 'caisse' (espèces) | 'banque' (Journal des comptes)
    payment_mode: Optional[str] = None           # virement|ov_permanent|ov_ponctuel|cheque|prelevement|carte|especes|…
    payment_ref: Optional[str] = None            # n° de chèque / n° d'OV / réf. de virement


class CashJournalEntryUpdate(BaseModel):
    """Modification d'une ligne du journal de caisse (tous champs optionnels)."""
    entry_date: Optional[str] = None
    type: Optional[str] = None                   # 'entree' | 'sortie'
    action: Optional[str] = None
    prestataire: Optional[str] = None
    amount: Optional[float] = None               # DH, valeur positive
    justificatif: Optional[str] = None
    nc: Optional[str] = None                      # 'noir' | 'comptable'
    channel: Optional[str] = None                 # 'caisse' | 'banque'
    payment_mode: Optional[str] = None
    payment_ref: Optional[str] = None


class CashNoteItem(BaseModel):
    """Ligne du tableau d'une note de caisse. `montant` (TTC) est toujours
    recalculé par le backend à partir de montant_ht × (1 + tva_percent/100) —
    jamais fait confiance à la valeur envoyée par le client."""
    article: Optional[str] = None
    prestataire: Optional[str] = None
    montant_ht: float = 0
    tva_percent: float = 20
    montant: float = 0                              # TTC — recalculé côté serveur


class CashNoteCreate(BaseModel):
    """Création d'une note de caisse (modèle bébleo « Note de Caisse »)."""
    note_date: Optional[str] = None                 # défaut = aujourd'hui
    beneficiary_name: str                           # Nom et Prénom
    beneficiary_cin: Optional[str] = None           # CIN
    objet: Optional[str] = None                     # Objet de la note
    period_from: Optional[str] = None               # Du ...
    period_to: Optional[str] = None                 # ... au ...
    accorded_by: Optional[str] = None               # Accordée par
    items: list[CashNoteItem] = []                  # [{article, prestataire, montant_ht, tva_percent, montant}]
    nc: str = "comptable"                           # nature journal : 'noir' | 'comptable'
    caisse: str = "caisse_sociale"                  # caisse visée : caisse_sociale=Comptable | caisse_secondaire=Sociale
    disbursement_method: str = "espece"             # remise au bénéficiaire : 'espece' | 'versement'
    comment: Optional[str] = None


class CashNoteUpdate(BaseModel):
    """Modification d'une note de caisse (tous champs optionnels)."""
    note_date: Optional[str] = None
    beneficiary_name: Optional[str] = None
    beneficiary_cin: Optional[str] = None
    objet: Optional[str] = None
    period_from: Optional[str] = None
    period_to: Optional[str] = None
    accorded_by: Optional[str] = None
    items: Optional[list[CashNoteItem]] = None
    nc: Optional[str] = None                         # 'noir' | 'comptable'
    caisse: Optional[str] = None                     # caisse_sociale | caisse_secondaire
    disbursement_method: Optional[str] = None        # 'espece' | 'versement'
    comment: Optional[str] = None


class CashNotePay(BaseModel):
    """Exécution du paiement (décaissement) d'une avance de note de caisse approuvée."""
    payment_method: str = "cheque"                   # ov_permanent | ov_ponctuel | cheque | caisse_sociale | autre
    payment_reference: Optional[str] = None          # n° chèque / virement
    payment_date: Optional[str] = None               # défaut = aujourd'hui


class MissionNoteCreate(BaseModel):
    """Création d'une note de frais de mission (modèle bébleo « Note des frais de mission »).
    La matrice est ventilée par thème/article (clés fixes, cf. MISSION_CATALOG) et par jour :
      - days    : dates ordonnées des colonnes (≤ 10)
      - amounts : {clé_article: [montant J1, montant J2, ...]} aligné sur days."""
    note_date: Optional[str] = None                  # défaut = aujourd'hui
    beneficiary_name: str                            # Nom et Prénom
    beneficiary_cin: Optional[str] = None            # CIN
    accompanied_by: Optional[str] = None             # Accompagné par
    objet: Optional[str] = None                      # Objet de mission
    mission_from: Optional[str] = None               # Mission du ...
    mission_to: Optional[str] = None                 # ... au ...
    accorded_by: Optional[str] = None                # Accordée par
    days: list[str] = []                             # ["AAAA-MM-JJ", ...] (≤ 10)
    amounts: dict[str, list[float]] = {}             # {article: [montant par jour]}
    nc: str = "comptable"                            # nature journal : 'noir' | 'comptable'
    caisse: str = "caisse_sociale"                   # caisse visée : caisse_sociale=Comptable | caisse_secondaire=Sociale
    comment: Optional[str] = None


class MissionNoteUpdate(BaseModel):
    """Modification d'une note de frais de mission (tous champs optionnels)."""
    note_date: Optional[str] = None
    beneficiary_name: Optional[str] = None
    beneficiary_cin: Optional[str] = None
    accompanied_by: Optional[str] = None
    objet: Optional[str] = None
    mission_from: Optional[str] = None
    mission_to: Optional[str] = None
    accorded_by: Optional[str] = None
    days: Optional[list[str]] = None
    amounts: Optional[dict[str, list[float]]] = None
    nc: Optional[str] = None                          # 'noir' | 'comptable'
    caisse: Optional[str] = None                      # caisse_sociale | caisse_secondaire
    comment: Optional[str] = None


class QuotationCreate(BaseModel):
    purchase_request_id: str
    supplier_id: Optional[str] = None
    quote_number: str
    quote_date: Optional[str] = None
    expiration_date: Optional[str] = None
    amount: float = 0
    currency: str = "MAD"
    rank: int = 1
    comment: Optional[str] = None
    delivery_required: bool = False
    delivery_cost: Optional[float] = None  # None = coût inconnu / à préciser ; 0 = gratuite
    delivery_included: bool = False  # la livraison est-elle déjà comprise dans `amount` ?
    vat_percent: float = 20  # `amount` reste HT ; total_incl_vat (TTC) est calculé en base


class QuotationUpdate(BaseModel):
    supplier_id: Optional[str] = None
    quote_number: Optional[str] = None
    quote_date: Optional[str] = None
    expiration_date: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    rank: Optional[int] = None
    comment: Optional[str] = None
    delivery_required: Optional[bool] = None
    delivery_cost: Optional[float] = None
    delivery_included: Optional[bool] = None
    vat_percent: Optional[float] = None


class ClassTuitionUpdate(BaseModel):
    tuition_per_student: float


class TrainerRateUpdate(BaseModel):
    hourly_rate: float
    currency: str = "MAD"
    social_charge_percent: float = 0


# ── Phase 3 — Réceptions, Paiements, Inventaire & Mouvements ───────────────
class PurchaseReceptionCreate(BaseModel):
    purchase_id: str
    received_quantity: float = 1
    quality_status: str = "conforme"  # 'conforme' | 'non_conforme_partiel' | 'non_conforme_total' | 'retourne'
    qhse_checked: bool = False
    inclure_rapport_comptable: bool = False
    validation_cg: bool = False
    comment: Optional[str] = None


class PurchaseReceptionUpdate(BaseModel):
    received_quantity: Optional[float] = None
    quality_status: Optional[str] = None
    qhse_checked: Optional[bool] = None
    inclure_rapport_comptable: Optional[bool] = None
    validation_cg: Optional[bool] = None
    comment: Optional[str] = None


class PurchaseReceptionValidation(BaseModel):
    decision: str            # 'accept' | 'reject'
    comment: str             # obligatoire — motive la décision, conservé comme historique


class PurchasePaymentCreate(BaseModel):
    purchase_id: str
    amount: float
    payment_date: Optional[str] = None
    payment_method: str  # 'ov_permanent' | 'ov_ponctuel' | 'cheque' | 'caisse_sociale' | 'autre'
    reference: Optional[str] = None
    comment: Optional[str] = None
    nc: str = "comptable"  # 'noir' | 'comptable' — pour le journal de caisse (non stocké sur le paiement)
    installment_id: Optional[str] = None  # échéance planifiée réglée (échéancier du bon de commande) ; None = hors échéancier


class PurchaseInstallmentIn(BaseModel):
    """Une échéance de l'échéancier prévisionnel d'un bon de commande.
    L'axe n\\c est dérivé côté serveur du mode ('caisse_sociale' → 'noir')."""
    label: Optional[str] = None          # jalon : avance, à la livraison, contrôle qualité, mensualité…
    amount: float = 0
    payment_mode: str = "cheque"         # ov_permanent|ov_ponctuel|cheque|caisse_sociale|autre
    due_date: Optional[str] = None       # échéance prévue (ISO yyyy-mm-dd), nullable


class PurchaseInstallmentsReplace(BaseModel):
    """Remplace l'intégralité de l'échéancier d'un bon de commande."""
    installments: list[PurchaseInstallmentIn] = []


class InventoryItemCreate(BaseModel):
    name: str
    asset_category: str  # 'consommable' | 'equipement' | 'locaux' | 'service'
    purchase_id: Optional[str] = None
    reception_id: Optional[str] = None
    initial_value: float = 0
    purchase_date: Optional[str] = None
    status: str = "actif"  # 'actif' | 'hors_service' | 'vendu' | 'perdu'
    amortissement_duree_annees: Optional[int] = None
    niveau_alerte: Optional[float] = None
    quantity: float = 1
    location: Optional[str] = None
    comment: Optional[str] = None
    caracteristiques: Optional[str] = None
    unite: Optional[str] = None
    prix_unitaire_ttc: Optional[float] = None
    tva_percent: Optional[float] = None
    # L62 : origine catalogue (Comptabilité > Catégories) — optionnel.
    category_ref_id: Optional[str] = None
    catalog_article_id: Optional[str] = None
    code_article: Optional[str] = None


class InventoryItemUpdate(BaseModel):
    name: Optional[str] = None
    asset_category: Optional[str] = None
    status: Optional[str] = None
    initial_value: Optional[float] = None
    purchase_date: Optional[str] = None
    amortissement_duree_annees: Optional[int] = None
    niveau_alerte: Optional[float] = None
    quantity: Optional[float] = None
    location: Optional[str] = None
    comment: Optional[str] = None
    caracteristiques: Optional[str] = None
    unite: Optional[str] = None
    prix_unitaire_ttc: Optional[float] = None
    tva_percent: Optional[float] = None
    category_ref_id: Optional[str] = None
    catalog_article_id: Optional[str] = None
    code_article: Optional[str] = None


class InventoryMovementCreate(BaseModel):
    movement_type: str  # 'entree' | 'sortie' | 'ajustement'
    quantity: float
    movement_date: Optional[str] = None
    description: Optional[str] = None
    beneficiary: Optional[str] = None   # demandeur, sur les sorties


class InventoryAllocationIn(BaseModel):
    location: str
    quantity: float = 0


class InventoryAllocationsUpdate(BaseModel):
    allocations: list[InventoryAllocationIn] = []


# ── Locaux (référentiel des pièces du bâtiment) ──────────────────────────────
class LocalCreate(BaseModel):
    name: str
    floor: str = "3e"                       # 'rdc'|'1er'|'2e'|'3e'|'4e'|'terrasse'
    code: Optional[str] = None
    capacity: Optional[int] = None
    note: Optional[str] = None
    sort_order: Optional[int] = None


class LocalUpdate(BaseModel):
    name: Optional[str] = None
    floor: Optional[str] = None
    code: Optional[str] = None
    capacity: Optional[int] = None
    note: Optional[str] = None
    sort_order: Optional[int] = None
    active: Optional[bool] = None


# ── Inventaire : catégories d'actifs gérables ────────────────────────────────
class InventoryCategoryCreate(BaseModel):
    label: str


class InventoryCategoryUpdate(BaseModel):
    label: Optional[str] = None
    active: Optional[bool] = None
    sort_order: Optional[int] = None


# ── RH — Employees (Ressources humaines) ──────────────────────────────────────
class EmployeeCreate(BaseModel):
    full_name: str
    cin: Optional[str] = None
    matricule: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    status: str = "active"           # 'active' | 'on-leave' | 'inactive'
    hire_date: Optional[str] = None
    contract_type: Optional[str] = None
    contract_start: Optional[str] = None
    contract_end: Optional[str] = None
    salary: Optional[float] = None
    birth_date: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    nationality: Optional[str] = None
    manager: Optional[str] = None
    cnss_number: Optional[str] = None
    bank_account: Optional[str] = None
    notes: Optional[str] = None
    # Identité complémentaire
    gender: Optional[str] = None
    place_of_birth: Optional[str] = None
    marital_status: Optional[str] = None
    dependents_count: Optional[int] = None
    blood_type: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    personal_email: Optional[str] = None
    # Pièce d'identité
    cin_issue_date: Optional[str] = None
    cin_expiry_date: Optional[str] = None
    passport_number: Optional[str] = None
    # Contact d'urgence
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    # Poste / conditions de travail
    grade: Optional[str] = None
    work_location: Optional[str] = None
    weekly_hours: Optional[float] = None
    # Administratif / paie
    bank_name: Optional[str] = None
    amo_number: Optional[str] = None
    tax_id: Optional[str] = None
    cimr_number: Optional[str] = None


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    cin: Optional[str] = None
    matricule: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    status: Optional[str] = None
    hire_date: Optional[str] = None
    contract_type: Optional[str] = None
    contract_start: Optional[str] = None
    contract_end: Optional[str] = None
    salary: Optional[float] = None
    birth_date: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    nationality: Optional[str] = None
    manager: Optional[str] = None
    cnss_number: Optional[str] = None
    bank_account: Optional[str] = None
    notes: Optional[str] = None
    gender: Optional[str] = None
    place_of_birth: Optional[str] = None
    marital_status: Optional[str] = None
    dependents_count: Optional[int] = None
    blood_type: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    personal_email: Optional[str] = None
    cin_issue_date: Optional[str] = None
    cin_expiry_date: Optional[str] = None
    passport_number: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relation: Optional[str] = None
    grade: Optional[str] = None
    work_location: Optional[str] = None
    weekly_hours: Optional[float] = None
    bank_name: Optional[str] = None
    amo_number: Optional[str] = None
    tax_id: Optional[str] = None
    cimr_number: Optional[str] = None


# ── RH — Leave requests ────────────────────────────────────────────────────────
class LeaveRequestCreate(BaseModel):
    employee_id: str
    type: str = "other"              # 'recovery'(R) | 'sick'(M) | 'unpaid'(CS) | 'permission'(P) | 'other'(A) | 'unjustified_absence'(AJ)
    start_date: str
    end_date: str
    days: int
    reason: Optional[str] = None


class LeaveRequestUpdate(BaseModel):
    status: Optional[str] = None     # 'pending' | 'approved' | 'rejected' | 'cancelled'
    reason: Optional[str] = None
    comment: Optional[str] = None


# ── RH — Payroll ────────────────────────────────────────────────────────────────
class PayrollCreate(BaseModel):
    employee_id: str
    month: int
    year: int
    base_salary: float
    bonuses: float = 0
    deductions: float = 0
    notes: Optional[str] = None


class PayrollUpdate(BaseModel):
    bonuses: Optional[float] = None
    deductions: Optional[float] = None
    status: Optional[str] = None     # 'draft' | 'validated' | 'paid'
    notes: Optional[str] = None


# ── RH — Performance reviews ────────────────────────────────────────────────────
# review_type distingue les 3 cadences demandées : mensuelle (alimentée par
# l'agrégat des tâches quotidiennes -> décision de prime de rendement),
# semestrielle (projets + résultats moyen/long terme) et annuelle (objectifs
# annuels -> note + évolution vs année précédente, calculée à la volée).
class PerformanceReviewCreate(BaseModel):
    employee_id: str
    period: str
    review_type: str = "annual"      # 'monthly' | 'semestrial' | 'annual'
    score: Optional[float] = None    # 0-20
    feedback: Optional[str] = None
    objectives: Optional[str] = None
    achievements: Optional[str] = None
    improvements: Optional[str] = None
    status: str = "draft"            # 'draft' | 'submitted' | 'acknowledged'
    task_count: Optional[int] = None
    bonus_suggested: Optional[float] = None
    bonus_decided: Optional[float] = None


class PerformanceReviewUpdate(BaseModel):
    score: Optional[float] = None
    feedback: Optional[str] = None
    objectives: Optional[str] = None
    achievements: Optional[str] = None
    improvements: Optional[str] = None
    status: Optional[str] = None
    bonus_decided: Optional[float] = None


class GoalCreate(BaseModel):
    employee_id: str
    title: str
    description: Optional[str] = None
    due_date: Optional[str] = None
    year: Optional[int] = None       # regroupement "objectifs annuels"


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None      # 'pending' | 'in_progress' | 'done'
    progress: Optional[int] = None    # 0-100
    due_date: Optional[str] = None
    year: Optional[int] = None


# ── RH — Fiche de poste digitalisée (L63) ───────────────────────────────────────
class JobDescriptionCreate(BaseModel):
    department: str
    position: str
    mission: Optional[str] = None


class JobDescriptionUpdate(BaseModel):
    mission: Optional[str] = None


class JobHeadingCreate(BaseModel):
    parent_id: Optional[str] = None   # None = grand titre, sinon sous-titre
    label: str
    coefficient: float = 1
    sort_order: int = 0


class JobHeadingUpdate(BaseModel):
    label: Optional[str] = None
    coefficient: Optional[float] = None
    sort_order: Optional[int] = None


# ── RH — Tâches quotidiennes (L63) ──────────────────────────────────────────────
DAILY_TASK_STATUSES = {"submitted", "validated", "returned"}


class DailyTaskCreate(BaseModel):
    employee_id: str
    heading_id: Optional[str] = None  # None = "autre tâche" libre
    label: str
    coefficient: Optional[float] = None  # défaut : celui de la rubrique, sinon 1
    task_date: Optional[str] = None
    due_date: Optional[str] = None
    employee_comment: Optional[str] = None


class DailyTaskUpdate(BaseModel):
    label: Optional[str] = None
    due_date: Optional[str] = None
    employee_comment: Optional[str] = None


class DailyTaskValidate(BaseModel):
    decision: str                     # 'validate' | 'return'
    note: Optional[float] = None      # requis si decision == 'validate' (0-20)
    manager_comment: str


class ProbationDecision(BaseModel):
    decision: str                     # 'passed' | 'failed' | 'extended'
    feedback: Optional[str] = None
    extend_days: Optional[int] = None  # required when decision == 'extended'
    status: Optional[str] = None


# ── RH phase 2 — Departments & contract types ──────────────────────────────────
class DepartmentCreate(BaseModel):
    name: str
    description: Optional[str] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ContractTypeCreate(BaseModel):
    name: str
    description: Optional[str] = None


class ContractTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


# ── RH phase 2 — Assets ────────────────────────────────────────────────────────
class AssetCreate(BaseModel):
    name: str
    category: Optional[str] = None
    serial_number: Optional[str] = None
    employee_id: Optional[str] = None
    status: str = "available"
    notes: Optional[str] = None


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    serial_number: Optional[str] = None
    employee_id: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


# ── RH phase 2 — Onboarding ─────────────────────────────────────────────────────
class OnboardingUpdate(BaseModel):
    phase: Optional[str] = None                # 'day30'|'day60'|'day90'|'completed'
    buddy_name: Optional[str] = None
    buddy_email: Optional[str] = None
    contract_signed: Optional[bool] = None
    plan_30: Optional[list] = None
    plan_60: Optional[list] = None
    plan_90: Optional[list] = None


class PulseSurveyCreate(BaseModel):
    week_number: Optional[int] = None
    satisfaction_score: Optional[int] = None    # 1-5
    integration_score: Optional[int] = None     # 1-5
    clarity_score: Optional[int] = None         # 1-5
    comment: Optional[str] = None


# ── RH phase 2 — Recruitment (ads, candidates, interviews, slots) ──────────────
class JobAdCreate(BaseModel):
    poste: str
    description: Optional[str] = None
    competences: Optional[str] = None
    experience: Optional[str] = None
    contenu: str
    image_url: Optional[str] = None
    is_active: bool = True


class JobAdUpdate(BaseModel):
    poste: Optional[str] = None
    description: Optional[str] = None
    competences: Optional[str] = None
    experience: Optional[str] = None
    contenu: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


class CandidateCreate(BaseModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class CandidateUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class CandidateCommentCreate(BaseModel):
    text: str


class CandidatePromote(BaseModel):
    hire_date: Optional[str] = None
    position: Optional[str] = None
    required_documents: Optional[list[str]] = None
    probation_duration_days: int = 30  # 30 | 60 | 90


class InterviewCreate(BaseModel):
    candidate_id: str
    interviewer_ids: list[str] = []               # jusqu'à 3 — voir schedule_interview()
    date: str
    start_time: str
    end_time: str
    type: str                                    # 'rh'|'technical'|'final'
    meet_link: Optional[str] = None
    notes: Optional[str] = None
    slot_id: Optional[str] = None


class InterviewUpdate(BaseModel):
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    type: Optional[str] = None
    meet_link: Optional[str] = None
    notes: Optional[str] = None
    interviewer_ids: Optional[list[str]] = None    # None = inchangé ; liste (même vide) = remplace


# ── Interview evaluation — digitalise "Grille d'Entretien de Recrutement"
# et "Fiche d'Entretien d'Embauche" (formulaires RH papier). ──────────────────
class GrilleRow(BaseModel):
    score: Optional[int] = None        # 1-5
    remarque: Optional[str] = None


class EvaluationGrille(BaseModel):
    connaissance_domaine: GrilleRow = GrilleRow()
    formations: GrilleRow = GrilleRow()
    experiences_pro: GrilleRow = GrilleRow()
    competences: GrilleRow = GrilleRow()
    outils: GrilleRow = GrilleRow()
    travail_equipe: GrilleRow = GrilleRow()
    ponctualite_reactivite: GrilleRow = GrilleRow()
    organisation_autonomie: GrilleRow = GrilleRow()
    motivation: GrilleRow = GrilleRow()
    mobilite: GrilleRow = GrilleRow()
    disponibilite: GrilleRow = GrilleRow()
    pretentions_salariales: GrilleRow = GrilleRow()
    observations: Optional[str] = None


class CompetenceRating(BaseModel):
    commentaire: Optional[str] = None
    niveau: Optional[str] = None       # inti|qualifie|experimente|master (agilites : low|medium|high)


class EvaluationFiche(BaseModel):
    ponctualite: Optional[str] = None
    maitrise_de_soi: Optional[str] = None
    facon_de_se_presenter: Optional[str] = None
    comportement: Optional[str] = None
    interet_poste: Optional[str] = None
    competences_corps_metier: CompetenceRating = CompetenceRating()
    competences_transverses: CompetenceRating = CompetenceRating()
    agilites: CompetenceRating = CompetenceRating()
    softskills: dict[str, bool] = {}   # clé = slug de l'affirmation
    points_forts: Optional[str] = None
    axes_amelioration: Optional[str] = None
    appreciation_generale: Optional[str] = None


INTERVIEW_DECISIONS = {"negative", "standby", "other_interview", "offer", "other_entity"}
INTERVIEW_ENTRETIEN_TYPES = {"presentiel", "distance"}


class InterviewEvaluationUpsert(BaseModel):
    grille: Optional[EvaluationGrille] = None
    fiche: Optional[EvaluationFiche] = None
    decision: Optional[str] = None
    decision_detail: Optional[str] = None
    salary_current: Optional[str] = None
    salary_expected: Optional[str] = None
    interviewer_visa: Optional[str] = None
    entite_affectation: Optional[str] = None
    type_entretien: Optional[str] = None
    duree_entretien: Optional[str] = None
    notes: Optional[str] = None
    recruiter_id: Optional[str] = None


class SlotCreate(BaseModel):
    date: str
    start_time: str
    end_time: str
    ad_id: Optional[str] = None
    interviewer_ids: list[str] = []   # jusqu'à MAX_INTERVIEWERS — voir rh_recruitment.py


class SlotUpdate(BaseModel):
    interviewer_ids: list[str]


# ── RH phase 2 — Org chart ──────────────────────────────────────────────────────
class OrgProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#0891b2"


class OrgProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


class OrgMemberAdd(BaseModel):
    employee_id: str
    role_in_team: Optional[str] = None


class OrgMemberRoleUpdate(BaseModel):
    role_in_team: str


class OrgPositionUpdate(BaseModel):
    x: float
    y: float


# ── RH phase 2 — Training & skills ──────────────────────────────────────────────
class TrainingCreate(BaseModel):
    title: str
    category: str = "technique"
    provider: Optional[str] = None
    duration_hours: int = 0
    cost_dh: float = 0
    description: Optional[str] = None


class TrainingUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    provider: Optional[str] = None
    duration_hours: Optional[int] = None
    cost_dh: Optional[float] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class TrainingAssignmentCreate(BaseModel):
    employee_id: str
    training_id: str
    status: str = "planned"
    notes: Optional[str] = None


class TrainingAssignmentUpdate(BaseModel):
    status: Optional[str] = None
    score: Optional[int] = None
    notes: Optional[str] = None
    completed_at: Optional[str] = None


class SkillCreate(BaseModel):
    name: str
    category: str = "technique"
    description: Optional[str] = None


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class EmployeeSkillUpsert(BaseModel):
    employee_id: str
    skill_id: str
    level: str = "beginner"


# ── RH phase 2 — Talent management ──────────────────────────────────────────────
class TalentProfileUpdate(BaseModel):
    performance_score: Optional[int] = None      # 1-5
    potential_score: Optional[int] = None         # 1-5
    flight_risk: Optional[str] = None             # 'low'|'medium'|'high'
    is_critical_position: Optional[bool] = None
    successor_names: Optional[list] = None
    career_path: Optional[str] = None
    next_role: Optional[str] = None
    notes: Optional[str] = None


class OkrCreate(BaseModel):
    title: str
    description: Optional[str] = None
    quarter: Optional[str] = None
    progress: int = 0
    status: str = "active"


class OkrUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    quarter: Optional[str] = None
    progress: Optional[int] = None
    status: Optional[str] = None


class PdiItemCreate(BaseModel):
    title: str
    action_type: str = "formation"
    target_date: Optional[str] = None
    notes: Optional[str] = None


class PdiItemUpdate(BaseModel):
    title: Optional[str] = None
    action_type: Optional[str] = None
    target_date: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


# ── Suivi de paiement des élèves (échéancier mensuel + alertes) ────────────
class TuitionPlanUpdate(BaseModel):
    monthly_fee: Optional[float] = None       # mensualité SAISIE (standardisée par promo)
    registration_fee: Optional[float] = None  # (obsolète, remplacé par advance)
    advance: Optional[float] = None           # frais d'inscription (poste séparé, hors budget) — peut être 0
    annual_budget: Optional[float] = None      # dérivé = mensualité × nb_mois (hors frais) — ignoré en écriture
    enrollment_number: Optional[str] = None
    enrollment_date: Optional[str] = None
    enrollment_status: Optional[str] = None  # 'actif'|'abandon'|'absent'|'suspendu'|'diplome'
    payment_comment: Optional[str] = None
    due_day: Optional[int] = None             # jour d'échéance de la mensualité (1..28), par élève
    grace_days: Optional[int] = None          # jours de tolérance après l'échéance (0..27)


class TuitionPlanBulkItem(TuitionPlanUpdate):
    student_id: str


class TuitionPlanBulkUpdate(BaseModel):
    updates: list[TuitionPlanBulkItem]


class ClassScheduleUpdate(BaseModel):
    payment_start_month: Optional[str] = None  # 1er du mois (ex. '2024-09-01')
    installments_count: Optional[int] = None


class TuitionPaymentCreate(BaseModel):
    class_id: str
    student_id: str
    period_month: str  # mois d'imputation (normalisé au 1er du mois côté router)
    amount: float = 0
    method: Optional[str] = None
    note: Optional[str] = None
    paid_on: Optional[str] = None
    comment: Optional[str] = None
    receipt_reference: Optional[str] = None


class TuitionPaymentUpdate(BaseModel):
    period_month: Optional[str] = None
    amount: Optional[float] = None
    method: Optional[str] = None
    note: Optional[str] = None
    paid_on: Optional[str] = None
    receipt_reference: Optional[str] = None


# ── Validation N+1 (file d'attente des saisies caissier) ───────────────────
class ApprovalReject(BaseModel):
    comment: str  # motif du rejet (obligatoire)


# ── Registre des règlements bancaires (migrations l37, l38) ─────────────────
class ChequeCreate(BaseModel):
    """Saisie manuelle d'une pièce au registre."""
    direction: str = "recu"                  # 'emis' (établi par l'école) | 'recu'
    mode: str = "cheque"                     # cheque|versement|virement|ov_permanent|ov_ponctuel
    amount: float = 0
    counterparty: Optional[str] = None       # bénéficiaire (émis) | tireur (reçu)
    cheque_number: Optional[str] = None
    bank: Optional[str] = None
    label: Optional[str] = None              # objet du chèque
    issue_date: Optional[str] = None         # défaut = aujourd'hui
    due_date: Optional[str] = None           # échéance / remise prévue
    comment: Optional[str] = None


class ChequeUpdate(BaseModel):
    """Complète ou corrige un chèque (le statut se change via /status)."""
    counterparty: Optional[str] = None
    cheque_number: Optional[str] = None
    bank: Optional[str] = None
    label: Optional[str] = None
    issue_date: Optional[str] = None
    due_date: Optional[str] = None
    remitted_date: Optional[str] = None      # « déposé le » — corrigeable après coup
    comment: Optional[str] = None


class ChequeStatusUpdate(BaseModel):
    """Avancement dans le cycle de vie : remis | encaisse | impaye | annule."""
    status: str
    date: Optional[str] = None               # date d'encaissement / d'impayé / nouvelle échéance
    comment: Optional[str] = None


# {module_id, lesson_id, slide_id} — slide_id is None for markdown-only lessons
class TeachingSessionStart(BaseModel):
    course_id: str
    class_id: str
    start_position: Optional[dict] = None


class TeachingSessionPositionUpdate(BaseModel):
    position: dict


class TeachingSessionEnd(BaseModel):
    end_position: Optional[dict] = None


class SessionFeedbackSubmit(BaseModel):
    answers: dict[str, int]  # {question_id: 1-5}


# ── Gestion des tâches (Task Management) ────────────────────────────────────
TASK_STATUSES = {"todo", "in_progress", "in_review", "done", "blocked", "cancelled"}
TASK_PRIORITIES = {"low", "medium", "high", "urgent"}
TASK_DOMAINS = {"rh", "comptabilite", "scolarite", "general"}


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"
    domain: Optional[str] = None
    assignee_id: Optional[str] = None
    due_date: Optional[str] = None
    linked_entity_type: Optional[str] = None
    linked_entity_id: Optional[str] = None


class TaskUpdate(BaseModel):
    """PATCH générique — ne touche jamais status ni assignee_id, forcés via
    les endpoints dédiés /status et /assign (même garde-fou que rh_leaves.py)."""
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    domain: Optional[str] = None
    due_date: Optional[str] = None
    linked_entity_type: Optional[str] = None
    linked_entity_id: Optional[str] = None


class TaskStatusUpdate(BaseModel):
    status: str


class TaskAssign(BaseModel):
    assignee_id: Optional[str] = None  # None = désassigner (retour au backlog)


class TaskCommentCreate(BaseModel):
    text: str


class RosterCreate(BaseModel):
    academic_year: str = "2025-2026"
    departement: Optional[str] = None
    region: Optional[str] = None
    province: Optional[str] = None
    milieu: Optional[str] = None
    etablissement: Optional[str] = None
    mode_formation: Optional[str] = None
    niveau_formation: Optional[str] = None
    secteur: Optional[str] = None
    filiere: Optional[str] = None
    annee_formation: Optional[str] = None
    nom: str
    prenom: str
    genre: Optional[str] = None
    besoins_specifiques: bool = False
    type_handicap: Optional[str] = None
    cin: Optional[str] = None
    id_massar: Optional[str] = None
    date_naissance: Optional[str] = None
    nationalite: Optional[str] = None
    etranger_migrant_refugie: Optional[str] = None
    pays_origine: Optional[str] = None
    niveau_scolaire: Optional[str] = None
    date_dernier_niveau: Optional[str] = None


class RosterUpdate(RosterCreate):
    nom: Optional[str] = None
    prenom: Optional[str] = None
    academic_year: Optional[str] = None


class RoomCreate(BaseModel):
    name: str
    capacity: Optional[int] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    equipment: Optional[str] = None
    notes: Optional[str] = None


class RoomUpdate(BaseModel):
    name: Optional[str] = None
    capacity: Optional[int] = None
    building: Optional[str] = None
    floor: Optional[str] = None
    equipment: Optional[str] = None
    notes: Optional[str] = None

