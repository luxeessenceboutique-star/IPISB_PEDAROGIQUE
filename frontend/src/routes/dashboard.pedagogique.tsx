import { createFileRoute, redirect, Link } from "@tanstack/react-router";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import {
  BookOpen, ClipboardList, GraduationCap, CalendarDays, Video, IdCard,
  Presentation, CalendarRange, Library, Layers, UserCog, Wallet, ListChecks,
  FileText, Megaphone, Users, Award, type LucideIcon,
} from "lucide-react";
import { PageHead, SectionLabel } from "@/components/dashboard/ui";

export const Route = createFileRoute("/dashboard/pedagogique")({
  beforeLoad: async () => {
    const { data: sess } = await supabase.auth.getSession();
    if (!sess.session) throw redirect({ to: "/auth" });
  },
  component: PedagogiquePage,
});

const PAL = {
  ink: "oklch(22% 0.025 175)", muted: "oklch(48% 0.02 180)", line: "oklch(88% 0.015 170)", paper: "oklch(99% 0.005 160)",
};
const sans = '"Manrope", system-ui, sans-serif';

type Card = { key: string; label: string; sub: string; to: string; icon: LucideIcon; show: boolean };

function CardGrid({ cards }: { cards: Card[] }) {
  const visible = cards.filter(c => c.show);
  if (visible.length === 0) return null;
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 14, marginBottom: 26 }}>
      {visible.map(c => {
        const Icon = c.icon;
        return (
          <Link
            key={c.key} to={c.to as "/dashboard"}
            className="dash-card u-hover-lift"
            style={{ padding: "20px 20px", textDecoration: "none", display: "block" }}
          >
            <div style={{ width: 38, height: 38, borderRadius: 10, background: "var(--pal-pale)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--pal-primary)", marginBottom: 12 }}>
              <Icon size={18} strokeWidth={1.8} />
            </div>
            <div style={{ fontFamily: sans, fontSize: 14.5, fontWeight: 700, color: PAL.ink }}>{c.label}</div>
            <div style={{ fontFamily: sans, fontSize: 12, color: PAL.muted, marginTop: 3, lineHeight: 1.4 }}>{c.sub}</div>
          </Link>
        );
      })}
    </div>
  );
}

function PedagogiquePage() {
  const { roles } = useAuth();
  const isAdmin = roles.includes("admin");
  const isProf = roles.includes("professor");
  const isCashier = roles.includes("cashier");
  const isRestrictedStaff = (roles.includes("rh") || roles.includes("assistant_rh") || roles.includes("comptabilite") || roles.includes("accountant") || isCashier) && !isAdmin && !isProf;
  const canManageClasses = isAdmin || isProf || isCashier;
  const showRh = isAdmin || roles.includes("rh") || roles.includes("assistant_rh");
  const showAccounting = isAdmin || isCashier || roles.includes("accountant") || roles.includes("comptabilite");
  const showTasks = isAdmin || isProf || showAccounting || showRh;

  const academique: Card[] = [
    { key: "courses", label: "Cours", sub: "Contenu pédagogique, modules et leçons.", to: "/dashboard/courses", icon: BookOpen, show: !isRestrictedStaff },
    { key: "assignments", label: "Contrôle continu", sub: "Devoirs, rendus et notation.", to: "/dashboard/assignments", icon: ClipboardList, show: !isRestrictedStaff },
    { key: "exams", label: "Examens", sub: "Épreuves, questions et résultats.", to: "/dashboard/exams", icon: GraduationCap, show: !isRestrictedStaff },
    { key: "grades", label: "Notes", sub: "Relevé de notes consolidé, moyennes par matière et générale.", to: "/dashboard/grades", icon: Award, show: isAdmin || isProf },
    { key: "classes", label: "Classes", sub: "Filières, promotions et effectifs.", to: "/dashboard/classes", icon: Layers, show: canManageClasses },
    { key: "students", label: "Élèves", sub: "Fiches stagiaires et dossiers.", to: "/dashboard/students", icon: IdCard, show: isAdmin || isProf },
    { key: "roster", label: "Effectifs des stagiaires", sub: "Import/export Excel — même format que le Canevas.", to: "/dashboard/roster", icon: Users, show: showRh || isAdmin },
    { key: "teaching-sessions", label: "Séances", sub: "Historique des séances et retours.", to: "/dashboard/teaching-sessions", icon: Presentation, show: isAdmin || isProf },
    { key: "timetables", label: "Emplois du temps", sub: "Grilles horaires par classe.", to: "/dashboard/timetables", icon: CalendarRange, show: isAdmin || isProf },
    { key: "library", label: "Bibliothèque", sub: "Documents et ressources par filière.", to: "/dashboard/library", icon: Library, show: isAdmin || isProf },
    { key: "agenda", label: "Agenda", sub: "Calendrier partagé des événements.", to: "/dashboard/agenda", icon: CalendarDays, show: !isRestrictedStaff },
    { key: "meetings", label: "Réunions", sub: "Visioconférences et liens de session.", to: "/dashboard/meetings", icon: Video, show: !isRestrictedStaff },
  ];

  const gestion: Card[] = [
    { key: "rh", label: "RH", sub: "Employés, congés, paie, recrutement.", to: "/dashboard/rh", icon: UserCog, show: showRh },
    { key: "accounting", label: "Comptabilité", sub: "Scolarité, recettes, dépenses, trésorerie.", to: "/dashboard/accounting", icon: Wallet, show: showAccounting },
    { key: "tasks", label: "Tâches", sub: "Suivi des tâches internes.", to: "/dashboard/tasks", icon: ListChecks, show: showTasks },
    { key: "documents", label: "Documents", sub: "Modèles et documents officiels.", to: "/dashboard/documents", icon: FileText, show: isAdmin },
    { key: "communication", label: "Communication", sub: "Annonces internes par rôle.", to: "/dashboard/communication", icon: Megaphone, show: isAdmin },
  ];

  return (
    <div style={{ fontFamily: sans }}>
      <PageHead
        eyebrow="Centralisation"
        title="Pédagogique"
        sub="Un point d'accès unique vers tout ce qui touche aux élèves, à leur formation et aux modules associés."
      />

      <SectionLabel>Scolarité & pédagogie</SectionLabel>
      <CardGrid cards={academique} />

      <SectionLabel>Autres modules</SectionLabel>
      <CardGrid cards={gestion} />
    </div>
  );
}
