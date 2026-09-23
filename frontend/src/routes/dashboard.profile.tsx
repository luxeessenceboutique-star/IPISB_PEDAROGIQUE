import { createFileRoute, redirect } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { toast } from "sonner";
import { Calendar, Loader2, KeyRound, CheckCircle } from "lucide-react";
import { PageHead, SectionLabel, DashAvatar } from "@/components/dashboard/ui";

export const Route = createFileRoute("/dashboard/profile")({
  beforeLoad: async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) throw redirect({ to: "/auth" });
  },
  component: ProfilePage,
});

const ROLE_CHIPS: Record<string, string> = {
  admin:     "chip-c-ink",
  professor: "chip-c-amber",
  student:   "chip-c-green",
};

function ProfilePage() {
  const { t, lang } = useI18n();
  const { user, roles, updatePassword } = useAuth();

  const [fullName,   setFullName]   = useState("");
  const [avatarUrl,  setAvatarUrl]  = useState("");
  const [saving,     setSaving]     = useState(false);

  const [newPw,      setNewPw]      = useState("");
  const [confirmPw,  setConfirmPw]  = useState("");
  const [changingPw, setChangingPw] = useState(false);
  const [showPw,     setShowPw]     = useState(false);

  useEffect(() => {
    setFullName((user?.user_metadata?.full_name as string | undefined) ?? "");
    setAvatarUrl((user?.user_metadata?.avatar_url as string | undefined) ?? "");
  }, [user]);

  if (!user) return null;

  const isAdmin   = roles.includes("admin");
  const isProf    = roles.includes("professor");
  const roleLabel = isAdmin
    ? t("dash.role.admin")
    : isProf
    ? t("dash.role.professor")
    : t("dash.role.student");

  const memberSince = user.created_at
    ? new Date(user.created_at).toLocaleDateString(lang === "ar" ? "ar-MA" : lang === "fr" ? "fr-FR" : "en-US", {
        year: "numeric", month: "long", day: "numeric",
      })
    : "—";

  async function saveProfile() {
    setSaving(true);
    try {
      const { error } = await supabase.auth.updateUser({
        data: { full_name: fullName, avatar_url: avatarUrl },
      });
      if (error) throw error;
      // also update profiles table if it exists
      await supabase.from("profiles").upsert({ id: user!.id, full_name: fullName, avatar_url: avatarUrl }, { onConflict: "id" });
      toast.success(t("profile.saved"));
    } catch (e: any) {
      toast.error(e.message ?? t("profile.save_error"));
    } finally {
      setSaving(false);
    }
  }

  async function changePassword() {
    if (newPw !== confirmPw) { toast.error(t("profile.password_mismatch")); return; }
    if (newPw.length < 6)    { toast.error(t("profile.password_short"));    return; }
    setChangingPw(true);
    try {
      await updatePassword(newPw);
      toast.success(t("profile.password_changed"));
      setNewPw(""); setConfirmPw("");
    } catch (e: any) {
      toast.error(e.message ?? t("profile.password_error"));
    } finally {
      setChangingPw(false);
    }
  }

  const topRole = isAdmin ? "admin" : isProf ? "professor" : "student";

  const fieldLabel = (txt: string) => (
    <div className="eyebrow" style={{ fontSize: 9.5, marginBottom: 6 }}>{txt}</div>
  );

  return (
    <div>
      <PageHead
        eyebrow={lang === "fr" ? "Mon compte" : lang === "ar" ? "حسابي" : "My account"}
        title={t("profile.title")}
        sub={t("profile.subtitle")}
      />

      <div className="grid items-start gap-4 lg:[grid-template-columns:320px_1fr]">
        {/* Identity card */}
        <div className="dash-card card-pop flex flex-col items-center gap-3 px-5 py-7 text-center">
          {avatarUrl ? (
            <img
              src={avatarUrl}
              alt={fullName}
              className="h-[76px] w-[76px] rounded-full object-cover"
              style={{ boxShadow: "0 0 0 2px var(--pal-line-soft)" }}
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          ) : (
            <DashAvatar name={fullName || user?.email || "?"} size={76} tone="primary" />
          )}
          <div>
            <div className="h-serif" style={{ fontSize: 24 }}>{fullName || user?.email || "—"}</div>
            <div className="mt-1" style={{ color: "var(--pal-muted)", fontSize: 13 }}>{user?.email}</div>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-1.5">
            <span className={`chip-c ${ROLE_CHIPS[topRole]}`}>{roleLabel}</span>
            {roles.length > 1 && roles.filter(r => r !== topRole).map(r => (
              <span key={r} className={`chip-c ${ROLE_CHIPS[r] ?? ""}`}>{t(`dash.role.${r}` as any)}</span>
            ))}
          </div>
          <div className="flex flex-col items-center gap-1" style={{ fontSize: 12, color: "var(--pal-muted)" }}>
            <span className="flex items-center gap-1.5">
              <Calendar size={13} strokeWidth={1.7} />{memberSince}
            </span>
            <span className="flex items-center gap-1.5">
              <CheckCircle size={13} strokeWidth={1.7} style={{ color: "var(--pal-good)" }} />
              {user?.email_confirmed_at ? (lang === "fr" ? "Email vérifié" : lang === "ar" ? "بريد مؤكد" : "Email verified") : (lang === "fr" ? "Non vérifié" : "Not verified")}
            </span>
          </div>
        </div>

        <div className="flex min-w-0 flex-col gap-4">
          {/* Personal info */}
          <div className="dash-card card-pop p-6">
            <SectionLabel>{t("profile.section.info")}</SectionLabel>
            <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
              <div>
                {fieldLabel(t("profile.fullname"))}
                <input
                  className="input-c"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder={lang === "fr" ? "Votre nom complet" : lang === "ar" ? "اسمك الكامل" : "Your full name"}
                />
              </div>
              <div>
                {fieldLabel(t("profile.email"))}
                <input className="input-c" style={{ background: "var(--pal-cream)", cursor: "not-allowed" }} value={user?.email ?? ""} readOnly />
                <p className="mt-1" style={{ fontSize: 11, color: "var(--pal-muted)" }}>{t("profile.email_readonly")}</p>
              </div>
              <div>
                {fieldLabel(t("profile.avatar_url"))}
                <input
                  className="input-c"
                  value={avatarUrl}
                  onChange={(e) => setAvatarUrl(e.target.value)}
                  placeholder="https://..."
                />
              </div>
              <div>
                {fieldLabel(t("profile.member_since"))}
                <input className="input-c" style={{ background: "var(--pal-cream)", cursor: "not-allowed" }} value={memberSince} readOnly />
              </div>
            </div>
            <div className="mt-5 flex flex-wrap gap-2.5">
              <button type="button" className="btn-c btn-c-primary btn-c-sm" disabled={saving} onClick={saveProfile}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : t("profile.save")}
              </button>
            </div>
          </div>

          {/* Security */}
          <div className="dash-card card-pop p-6">
            <SectionLabel>{t("profile.section.security")}</SectionLabel>
            <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
              <div>
                {fieldLabel(t("profile.new_password"))}
                <div className="relative">
                  <KeyRound size={14} strokeWidth={1.7} className="absolute start-3 top-1/2 -translate-y-1/2" style={{ color: "var(--pal-muted)" }} />
                  <input
                    className="input-c"
                    style={{ paddingInlineStart: 34, paddingInlineEnd: 64 }}
                    type={showPw ? "text" : "password"}
                    value={newPw}
                    onChange={(e) => setNewPw(e.target.value)}
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw((v) => !v)}
                    className="absolute end-3 top-1/2 -translate-y-1/2 transition-colors"
                    style={{ fontSize: 11, fontWeight: 700, color: "var(--pal-muted)", background: "none", border: 0, cursor: "pointer" }}
                  >
                    {showPw ? (lang === "fr" ? "Masquer" : "Hide") : (lang === "fr" ? "Afficher" : "Show")}
                  </button>
                </div>
              </div>
              <div>
                {fieldLabel(t("profile.confirm_password"))}
                <div className="relative">
                  <KeyRound size={14} strokeWidth={1.7} className="absolute start-3 top-1/2 -translate-y-1/2" style={{ color: "var(--pal-muted)" }} />
                  <input
                    className="input-c"
                    style={{ paddingInlineStart: 34 }}
                    type={showPw ? "text" : "password"}
                    value={confirmPw}
                    onChange={(e) => setConfirmPw(e.target.value)}
                    placeholder="••••••••"
                  />
                </div>
              </div>
            </div>
            <div className="mt-5">
              <button
                type="button"
                className="btn-c btn-c-ghost btn-c-sm"
                disabled={changingPw || !newPw || !confirmPw}
                onClick={changePassword}
              >
                {changingPw ? <Loader2 className="h-4 w-4 animate-spin" /> : t("profile.change_password")}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
