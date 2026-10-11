import { createFileRoute, Outlet, redirect, Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import {
  Home, Bell, Compass,
  Layers, LogOut, X,
  User, RefreshCw,
  ChevronDown, Plus,
} from "lucide-react";
import { Wordmark } from "@/components/Wordmark";
import { DashAvatar } from "@/components/dashboard/ui";
import { PlatformCopilot } from "@/components/PlatformCopilot";
import { useAuth } from "@/lib/auth";
import { supabase } from "@/integrations/supabase/client";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useBreakpoint } from "@/lib/useBreakpoint";

const PAL = {
  ink:     "oklch(22% 0.025 175)",
  muted:   "oklch(48% 0.02 180)",
  mid:     "oklch(62% 0.085 170)",
  pale:    "oklch(94% 0.025 165)",
  cream:   "oklch(97% 0.012 90)",
  paper:   "oklch(99% 0.005 160)",
  danger:  "oklch(64% 0.18 25)",
  lineSoft:"oklch(92% 0.012 170)",
};
const sans = '"Manrope", system-ui, sans-serif';

export const Route = createFileRoute("/dashboard")({
  beforeLoad: async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) throw redirect({ to: "/auth" });
  },
  component: DashboardLayout,
});

type NavLeaf = {
  type: "leaf"; key: string; to: string; icon: typeof Home;
  exact?: boolean; badge?: boolean; label?: string; search?: Record<string, string>;
};
type NavGroup = {
  type: "group"; key: string; icon: typeof Home; homeTo?: string; exact?: boolean; label?: string; children: NavEntry[];
};
type NavEntry = NavLeaf | NavGroup;

function entryMatchesPath(entry: NavEntry, pathname: string): boolean {
  return entry.type === "leaf"
    ? pathname.startsWith(entry.to)
    : entry.children.some(c => entryMatchesPath(c, pathname));
}

function leaf(partial: Omit<NavLeaf, "type">): NavLeaf {
  return { type: "leaf", ...partial };
}
function group(partial: Omit<NavGroup, "type">): NavGroup {
  return { type: "group", ...partial };
}

type Specialty = { id: string; name: string; type: "formation_initiale" | "formation_continue" };

function DashboardLayout() {
  const { user, roles, signOut } = useAuth();
  const { t, lang } = useI18n();
  const { isTablet } = useBreakpoint();
  const navigate = useNavigate();
  const routerState = useRouterState();
  const pathname = routerState.location.pathname;
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [unread, setUnread] = useState(0);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  function toggleGroup(key: string) {
    setCollapsedGroups(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  // Close drawer on navigation
  useEffect(() => { setDrawerOpen(false); }, [pathname]);
  // Close drawer on Escape
  useEffect(() => {
    const fn = (e: KeyboardEvent) => { if (e.key === "Escape") setDrawerOpen(false); };
    window.addEventListener("keydown", fn);
    return () => window.removeEventListener("keydown", fn);
  }, []);

  // Live unread-notification count for the sidebar badge
  useEffect(() => {
    if (!user) return;
    let active = true;
    const fetchUnread = async () => {
      const { count } = await supabase
        .from("notifications").select("*", { count: "exact", head: true })
        .eq("user_id", user.id).eq("read", false);
      if (active) setUnread(count ?? 0);
    };
    fetchUnread();
    const channel = supabase.channel("sidebar-notifications")
      .on("postgres_changes", { event: "*", schema: "public", table: "notifications", filter: `user_id=eq.${user.id}` }, fetchUnread)
      .subscribe();
    return () => { active = false; supabase.removeChannel(channel); };
  }, [user, pathname]);

  const isAdmin = roles.includes("admin");
  const isProf  = roles.includes("professor");
  const isCashier = roles.includes("cashier");
  const canManageClasses = isAdmin || isProf || isCashier;

  // Filières (specialties), pour peupler Formation initiale / Formation
  // continue dans la barre latérale — un seul appel léger, uniquement pour
  // les rôles qui gèrent des classes.
  const [specialties, setSpecialties] = useState<Specialty[]>([]);
  useEffect(() => {
    if (!user || !canManageClasses) { setSpecialties([]); return; }
    api.get("/api/specialties").then((d) => setSpecialties(Array.isArray(d) ? d : [])).catch(() => setSpecialties([]));
  }, [user, canManageClasses]);

  const roleLabel = isAdmin ? t("dash.role.admin")
    : isProf ? t("dash.role.professor")
    : t("dash.role.student");
  const fullName = (user?.user_metadata?.full_name as string | undefined) ?? user?.email ?? "?";
  const spaceLabel = lang === "fr"
    ? `Espace ${roleLabel.toLowerCase()}`
    : lang === "ar" ? `فضاء ${roleLabel}` : `${roleLabel} space`;

  function filiereChildren(filiereType: Specialty["type"], addLabel: string): NavLeaf[] {
    const items: NavLeaf[] = specialties
      .filter(s => s.type === filiereType)
      .map(s => leaf({
        key: s.id, label: s.name, to: "/dashboard/classes", icon: Layers,
        search: { specialty: s.id },
      }));
    if (isAdmin) {
      items.push(leaf({
        key: `add-${filiereType}`, label: addLabel, to: "/dashboard/classes", icon: Plus,
        search: { manage: "specialties" },
      }));
    }
    return items;
  }

  const navEntries: NavEntry[] = [
    // Notifications en tout premier, visible par tous.
    leaf({ key: "dash.notifications", to: "/dashboard/notifications", icon: Bell, badge: true }),

    // Aperçu — page d'accueil (dashboard.index.tsx).
    leaf({ key: "dash.overview", to: "/dashboard", icon: Home, exact: true }),

    // Pédagogique — hub centralisant Cours, Élèves, Séances…
    leaf({ key: "dash.pedagogique", to: "/dashboard/pedagogique", icon: Compass }),

    // Formation initiale / continue — filières dynamiques (Classes → Filières).
    ...(canManageClasses ? [
      group({ key: "dash.formationInitiale", icon: User, children: filiereChildren("formation_initiale", t("dash.addFiliere")) }),
      group({ key: "dash.formationContinue", icon: RefreshCw, children: filiereChildren("formation_continue", t("dash.addFiliere")) }),
    ] : []),
  ];

  // Un groupe sans enfant disparaît ; un groupe avec un seul enfant ET une
  // destination propre (homeTo) se réduit à un simple lien — c'est le cas
  // "Aperçu" pour un étudiant ou un membre du personnel restreint.
  const visibleEntries: NavEntry[] = navEntries.flatMap((it): NavEntry[] => {
    if (it.type === "leaf") return [it];
    if (it.children.length === 0) return [];
    if (it.children.length === 1 && it.homeTo) {
      return [leaf({ key: it.key, to: it.homeTo, icon: it.icon, exact: it.exact })];
    }
    return [it];
  });

  async function handleLogout() {
    await signOut();
    navigate({ to: "/auth" });
  }

  // Rendu récursif : un groupe (ex. Comptabilité) peut lui-même contenir des
  // groupes — chaque niveau d'imbrication ajoute son propre repli/dépli et
  // un retrait supplémentaire.
  function renderNavEntry(it: NavEntry, depth: number): React.ReactNode {
    const nested = depth > 0 ? { paddingInlineStart: 34 + (depth - 1) * 18, fontSize: 13 } : {};
    const iconSize = depth > 0 ? 15 : 17;

    if (it.type === "leaf") {
      const isActive = it.exact ? pathname === it.to : pathname.startsWith(it.to);
      const I = it.icon;
      return (
        <Link key={it.key} to={it.to as "/dashboard"} search={it.search}
          className={isActive ? "side-link is-active" : "side-link"}
          style={{ textDecoration: "none", fontFamily: sans, ...nested }}>
          <I size={iconSize} strokeWidth={1.7} />
          {it.label ?? t(it.key)}
          {it.badge && unread > 0 && (
            <span style={{ marginInlineStart: "auto", fontSize: 10, fontWeight: 800, color: PAL.paper, background: PAL.danger, padding: "2px 7px", borderRadius: 999 }}>{unread}</span>
          )}
        </Link>
      );
    }

    const GI = it.icon;
    const isGroupActive = it.children.some(c => entryMatchesPath(c, pathname));
    const isCollapsed = collapsedGroups.has(it.key);
    return (
      <div key={it.key}>
        <button
          type="button"
          onClick={() => toggleGroup(it.key)}
          className={isGroupActive ? "side-link is-active" : "side-link"}
          style={{ textDecoration: "none", fontFamily: sans, width: "100%", border: 0, background: "transparent", cursor: "pointer", textAlign: "start", ...nested }}
        >
          <GI size={iconSize} strokeWidth={1.7} />
          {it.label ?? t(it.key)}
          <ChevronDown size={14} strokeWidth={2}
            style={{ marginInlineStart: "auto", transition: "transform .15s ease", transform: isCollapsed ? "rotate(-90deg)" : "none", opacity: .6 }} />
        </button>
        {!isCollapsed && (
          <div style={{ display: "flex", flexDirection: "column", gap: 2, marginTop: 2 }}>
            {it.children.map(c => renderNavEntry(c, depth + 1))}
          </div>
        )}
      </div>
    );
  }

  const Sidebar = (
    <aside style={{
      background: PAL.paper,
      borderInlineEnd: `1px solid ${PAL.lineSoft}`,
      padding: "22px 16px",
      display: "flex", flexDirection: "column", gap: 22,
      width: isTablet ? 280 : "auto",
      height: isTablet ? "100%" : "auto",
      minHeight: 0,
    }}>
      <div style={{ padding: "0 8px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Link to="/dashboard" style={{ textDecoration: "none" }}>
          <Wordmark size={36} />
        </Link>
        {isTablet && (
          <button onClick={() => setDrawerOpen(false)} aria-label="Close" style={{
            background: "none", border: 0, cursor: "pointer", color: PAL.muted, lineHeight: 1, display: "flex", padding: 4,
          }}><X size={18} /></button>
        )}
      </div>

      <nav className="scroll-y" style={{ display: "flex", flexDirection: "column", gap: 2, flex: 1, minHeight: 0 }}>
        <span className="eyebrow" style={{ padding: "2px 12px 8px", fontSize: 9.5 }}>{spaceLabel}</span>
        {visibleEntries.map((it) => renderNavEntry(it, 0))}
      </nav>

      <div style={{ height: 1, background: PAL.lineSoft }} />

      {/* user card */}
      <div style={{ padding: 12, borderRadius: 14, background: PAL.pale, display: "flex", flexDirection: "column", gap: 10 }}>
        <Link to="/dashboard/profile" style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}>
          <DashAvatar name={fullName} size={34} tone="primary" />
          <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.25, flex: 1, minWidth: 0 }}>
            <span style={{ fontSize: 12.5, fontWeight: 700, color: PAL.ink, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const }}>
              {fullName}
            </span>
            <span style={{ fontSize: 10.5, color: PAL.muted }}>{roleLabel}</span>
          </div>
        </Link>
        <button onClick={handleLogout} className="btn-c btn-c-ghost btn-c-sm" style={{ width: "100%" }}>
          <LogOut size={14} strokeWidth={1.7} />
          {t("dash.logout")}
        </button>
      </div>
    </aside>
  );

  // ── Mobile / tablet layout: top bar + drawer ──────────────────────
  if (isTablet) {
    return (
      <div style={{ width: "100%", minHeight: "100vh", background: PAL.cream, fontFamily: sans }}>
        {/* Top bar */}
        <header style={{
          position: "sticky", top: 0, zIndex: 30,
          background: PAL.paper, borderBottom: `1px solid ${PAL.lineSoft}`,
          padding: "12px 16px",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <button onClick={() => setDrawerOpen(true)} aria-label="Menu" style={{
            display: "flex", flexDirection: "column", gap: 4, background: "none", border: 0, cursor: "pointer", padding: 6,
          }}>
            {[0,1,2].map(i => <span key={i} style={{ width: 22, height: 2, background: PAL.ink, borderRadius: 2, display: "block" }} />)}
          </button>
          <Link to="/dashboard" style={{ textDecoration: "none" }}><Wordmark size={26} /></Link>
          <Link to="/dashboard/profile" aria-label={t("dash.profile")} style={{ textDecoration: "none" }}>
            <DashAvatar name={fullName} size={30} tone="primary" />
          </Link>
        </header>

        {/* Drawer overlay */}
        {drawerOpen && (
          <>
            <div onClick={() => setDrawerOpen(false)} className="anim-fade" style={{ position: "fixed", inset: 0, background: "oklch(0% 0 0 / .4)", zIndex: 40, backdropFilter: "blur(2px)" }} />
            <div style={{ position: "fixed", top: 0, insetInlineStart: 0, bottom: 0, zIndex: 41, animation: "drawer-in .28s cubic-bezier(.22,1,.36,1)", boxShadow: "8px 0 32px oklch(0% 0 0 / .12)" }}>
              <style>{`@keyframes drawer-in{from{transform:translateX(-100%)}to{transform:none}}`}</style>
              {Sidebar}
            </div>
          </>
        )}

        {/* Main */}
        <main style={{ padding: "20px 16px", overflow: "auto" }}>
          <div key={pathname} className="page-enter" style={{ maxWidth: 1180, margin: "0 auto" }}>
            <Outlet />
          </div>
        </main>
        <PlatformCopilot />
      </div>
    );
  }

  // ── Desktop layout ────────────────────────────────────────────────
  return (
    <div style={{ width: "100%", height: "100vh", overflow: "hidden", display: "grid", gridTemplateColumns: "248px 1fr", background: PAL.cream, fontFamily: sans }}>
      {Sidebar}
      <main className="scroll-y" style={{ minHeight: 0, padding: "30px 36px" }}>
        <div key={pathname} className="page-enter" style={{ maxWidth: 1180, margin: "0 auto" }}>
          <Outlet />
        </div>
      </main>
      <PlatformCopilot />
    </div>
  );
}
