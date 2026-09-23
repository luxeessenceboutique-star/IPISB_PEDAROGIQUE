"""
Role-tagged knowledge base describing every module of IPISB Connect, used by
the in-app platform copilot (backend/copilot/agent.py) to answer "how do I…"
and "what is…" questions from logged-in users.

Each section is tagged with which roles can actually see it in the sidebar
(frontend/src/routes/dashboard.tsx SIDE_ITEMS / allItems), so the copilot
never explains a feature a given user can't access.
"""

# role tags: "all" (admin+professor+student), "staff" (admin+professor), "admin" (admin only)

PLATFORM_SECTIONS: list[dict] = [
    {
        "key": "overview", "title": "Tableau de bord", "path": "/dashboard", "roles": ["all"],
        "body": "Vue d'ensemble personnalisée : prochains cours/examens, contrôle continu à rendre, "
                "annonces récentes et raccourcis vers les sections les plus utilisées.",
    },
    {
        "key": "courses", "title": "Cours", "path": "/dashboard/courses", "roles": ["all"],
        "body": "Liste des cours de l'utilisateur, avec supports (vidéos, PDF) et détails par cours. "
                "Les professeurs/admins peuvent créer, modifier ou archiver un cours depuis cette page. "
                "Les étudiants y consultent le contenu déposé par leurs professeurs.",
    },
    {
        "key": "assignments", "title": "Contrôle continu", "path": "/dashboard/assignments", "roles": ["all"],
        "body": "Gestion du contrôle continu : les professeurs créent une évaluation (consigne, date limite), "
                "les étudiants soumettent leur travail et voient leur note une fois corrigée.",
    },
    {
        "key": "exams", "title": "Examens", "path": "/dashboard/exams", "roles": ["all"],
        "body": "Examens QCM avec correction automatique. Les professeurs/admins créent les questions "
                "et publient l'examen ; les étudiants le passent en ligne et voient leur résultat.",
    },
    {
        "key": "agenda", "title": "Agenda", "path": "/dashboard/agenda", "roles": ["all"],
        "body": "Calendrier académique personnel : cours, examens, réunions et échéances de contrôle continu "
                "apparaissent automatiquement, avec la possibilité d'ajouter des événements personnels.",
    },
    {
        "key": "meetings", "title": "Réunions", "path": "/dashboard/meetings", "roles": ["all"],
        "body": "Visioconférence intégrée (Jitsi) : planifier une réunion, obtenir le lien, "
                "et rejoindre une session directement depuis la plateforme sans logiciel externe.",
    },
    {
        "key": "notifications", "title": "Notifications", "path": "/dashboard/notifications", "roles": ["all"],
        "body": "Centre de notifications (nouveau contrôle continu, note publiée, annonce, message). "
                "Le badge rouge dans la barre latérale indique le nombre de notifications non lues.",
    },
    {
        "key": "profile", "title": "Profil", "path": "/dashboard/profile", "roles": ["all"],
        "body": "Informations personnelles de l'utilisateur, photo, et paramètres du compte.",
    },
    {
        "key": "classes", "title": "Classes", "path": "/dashboard/classes", "roles": ["staff"],
        "body": "Gestion des classes/groupes d'étudiants : création de classe, affectation des étudiants "
                "et des professeurs, taux de scolarité par classe.",
    },
    {
        "key": "library", "title": "Bibliothèque", "path": "/dashboard/library", "roles": ["staff"],
        "body": "Bibliothèque de documents de référence officiels (cahiers des charges/CDC, programmes de "
                "formation, fiches et banques d'examens, règlements) fournis par la direction, organisés par "
                "catégorie en onglets. Consultation pour admin et professeurs ; seul un admin peut ajouter ou "
                "supprimer un document.",
    },
    {
        "key": "users", "title": "Utilisateurs", "path": "/dashboard/users", "roles": ["staff"],
        "body": "Gestion des comptes utilisateurs de la plateforme (rôle, activation), création de "
                "comptes professeurs/étudiants par un admin.",
    },
    {
        "key": "students", "title": "Stagiaires", "path": "/dashboard/students", "roles": ["admin"],
        "body": "Fiche administrative de chaque étudiant/stagiaire (dossier académique), distincte des "
                "employés RH — c'est le volet pédagogique/administratif des inscrits à l'IPISB.",
    },
    {
        "key": "documents", "title": "Documents", "path": "/dashboard/documents", "roles": ["admin"],
        "body": "Génération de documents administratifs (attestations, convocations) à partir de modèles, "
                "avec analyse IA de dossiers étudiants et stockage centralisé des pièces.",
    },
    {
        "key": "schedules", "title": "Emploi du temps", "path": "/dashboard/schedules", "roles": ["admin"],
        "body": "Construction et publication de l'emploi du temps par classe (créneaux, salles, professeurs).",
    },
    {
        "key": "announcements", "title": "Annonces", "path": "/dashboard/announcements", "roles": ["admin"],
        "body": "Publication d'annonces visibles par tous les utilisateurs concernés (ex : fermeture "
                "exceptionnelle, changement d'horaire).",
    },
    {
        "key": "accounting", "title": "Comptabilité", "path": "/dashboard/accounting", "roles": ["admin"],
        "body": (
            "Module de gestion administrative et financière, organisé en onglets : Vue d'ensemble, "
            "Analytique, Recettes, Dépenses, Factures, Demandes d'achat, Achats, Paiements, Inventaire, "
            "Budgets, Fournisseurs, Catégories, Journal (audit trail). Exemples d'usage : enregistrer une "
            "dépense (onglet Dépenses → Nouvelle dépense), suivre un budget par catégorie/mois (onglet "
            "Budgets), ou consulter l'historique des actions (onglet Journal)."
        ),
    },
    {
        "key": "rh", "title": "Ressources humaines", "path": "/dashboard/rh", "roles": ["admin"],
        "body": (
            "Module RH complet, organisé en onglets : Employés (fiches du personnel), Congés (demandes "
            "et soldes de congés, avec approbation), Paie (fiches de paie avec calcul CNSS/IR marocain et "
            "génération de bulletins PDF), Évaluations (entretiens de performance), Recrutement (annonces "
            "d'emploi, candidats, entretiens, créneaux de rendez-vous), Intégration (plans d'onboarding "
            "30/60/90 jours, pulse surveys), Formation (catalogue de formations, affectations, matrice de "
            "compétences), Talents (grille 9-box performance/potentiel, OKRs, plans de développement), "
            "Organigramme (projets/équipes en glisser-déposer), Matériel (inventaire du matériel assigné "
            "aux employés), Paramètres (départements et types de contrat). Exemples d'usage : approuver une "
            "demande de congé (onglet Congés → cliquer sur le bouton vert), générer la paie du mois "
            "(onglet Paie → sélectionner le mois → « Générer la paie du mois »), ou promouvoir un candidat "
            "en employé (onglet Recrutement → Candidats → « Promouvoir »)."
        ),
    },
]

ROLE_LABEL = {"admin": "administrateur", "professor": "professeur", "student": "étudiant"}


def sections_for_role(role: str) -> list[dict]:
    if role == "admin":
        allowed = {"all", "staff", "admin"}
    elif role == "professor":
        allowed = {"all", "staff"}
    else:
        allowed = {"all"}
    return [s for s in PLATFORM_SECTIONS if any(r in allowed for r in s["roles"])]


def render_sections(sections: list[dict]) -> str:
    return "\n\n".join(f"### {s['title']} ({s['path']})\n{s['body']}" for s in sections)
