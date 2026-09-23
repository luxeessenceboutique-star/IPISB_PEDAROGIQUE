import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { toast } from "sonner";
import { Bell, Loader2, CheckCheck, Info, CheckCircle2, AlertTriangle, XCircle, Trash2 } from "lucide-react";
import { ListSkeleton } from "@/components/Skeletons";
import { PageHead, EmptyHint } from "@/components/dashboard/ui";

export const Route = createFileRoute("/dashboard/notifications")({
  beforeLoad: async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) throw redirect({ to: "/auth" });
  },
  component: NotificationsPage,
});

type Notification = { id: string; title: string; message: string | null; type: string; read: boolean; link: string | null; created_at: string };

const TYPE_ICON: Record<string, typeof Info> = { info: Info, success: CheckCircle2, warning: AlertTriangle, error: XCircle };
const TYPE_CHIP: Record<string, string> = { info: "chip-c-blue", success: "chip-c-green", warning: "chip-c-amber", error: "chip-c-red" };

function NotificationsPage() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [marking, setMarking] = useState<string | null>(null);

  async function load() {
    if (!user) return;
    setLoading(true);
    const { data } = await supabase.from("notifications").select("*").eq("user_id", user.id).order("created_at", { ascending: false });
    setNotifications((data ?? []) as Notification[]);
    setLoading(false);
  }

  useEffect(() => {
    if (!user) return;
    load();
    const channel = supabase.channel("notifications-realtime")
      .on("postgres_changes", { event: "INSERT", schema: "public", table: "notifications", filter: `user_id=eq.${user.id}` }, payload => {
        const n = payload.new as Notification;
        setNotifications(prev => [n, ...prev]);
        toast.info(n.title, n.link ? {
          action: {
            label: lang === "fr" ? "Ouvrir" : lang === "ar" ? "فتح" : "Open",
            onClick: () => { if (!n.read) markRead(n.id); navigate({ href: n.link! }); },
          },
        } : undefined);
      })
      .subscribe();
    return () => { supabase.removeChannel(channel); };
  }, [user]);

  async function markRead(id: string) {
    if (!user) return;
    setMarking(id);
    await supabase.from("notifications").update({ read: true }).eq("id", id).eq("user_id", user.id);
    setMarking(null);
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
  }

  async function markAllRead() {
    if (!user) return;
    await supabase.from("notifications").update({ read: true }).eq("user_id", user.id).eq("read", false);
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    toast.success(t("notifications.mark_all_read"));
  }

  async function deleteNotification(id: string) {
    if (!user) return;
    await supabase.from("notifications").delete().eq("id", id).eq("user_id", user.id);
    setNotifications(prev => prev.filter(n => n.id !== id));
  }

  const unreadCount = notifications.filter(n => !n.read).length;
  const fmtDate = (d: string) => new Date(d).toLocaleDateString(lang === "fr" ? "fr-FR" : "en-US", { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  const typeLabel = (type: string) => {
    const map: Record<string, { fr: string; en: string }> = { info: { fr: "Info", en: "Info" }, success: { fr: "Succès", en: "Success" }, warning: { fr: "Alerte", en: "Warning" }, error: { fr: "Erreur", en: "Error" } };
    return map[type]?.[lang as "fr" | "en"] ?? type;
  };

  return (
    <div>
      <PageHead
        eyebrow={lang === "fr" ? "Activité récente" : lang === "ar" ? "النشاط الأخير" : "Recent activity"}
        title={t("dash.notifications")}
        sub={t("notifications.subtitle")}
        actions={unreadCount > 0 ? (
          <button type="button" className="btn-c btn-c-ghost btn-c-sm" onClick={markAllRead}>
            <CheckCheck size={14} strokeWidth={1.7} />{t("notifications.mark_all_read")}
          </button>
        ) : undefined}
      />

      {loading ? (
        <ListSkeleton rows={4} />
      ) : notifications.length === 0 ? (
        <div className="dash-card">
          <EmptyHint icon={<Bell size={28} strokeWidth={1.7} />} text={t("notifications.empty")} />
        </div>
      ) : (
        <div className="dash-card card-pop overflow-hidden">
          {notifications.map(n => {
            const Icon = TYPE_ICON[n.type] ?? Info;
            return (
              <div
                key={n.id}
                className="row-c"
                style={{ ...(n.read ? undefined : { background: "oklch(97% 0.015 165 / .6)" }), cursor: n.link ? "pointer" : undefined }}
                onClick={() => {
                  if (!n.link) return;
                  if (!n.read) markRead(n.id);
                  // `href` (et non `to`) : TanStack Router découpe la chaîne en
                  // pathname + search + hash. Indispensable pour les liens du type
                  // "/dashboard/accounting?tab=validations".
                  navigate({ href: n.link });
                }}
              >
                <span
                  className="flex shrink-0 items-center justify-center rounded-full"
                  style={{
                    width: 38, height: 38,
                    background: n.read ? "var(--pal-cream)" : "var(--pal-pale)",
                    color: "var(--pal-primary-deep)",
                  }}
                >
                  <Icon size={17} strokeWidth={1.7} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p style={{ fontSize: 13.5, fontWeight: n.read ? 600 : 800, color: "var(--pal-ink)" }}>{n.title}</p>
                    <span className={`chip-c ${TYPE_CHIP[n.type] ?? ""}`}>{typeLabel(n.type)}</span>
                  </div>
                  {n.message && <p className="mt-0.5" style={{ fontSize: 12.5, color: "var(--pal-muted)" }}>{n.message}</p>}
                </div>
                <span className="shrink-0 whitespace-nowrap" style={{ fontSize: 11.5, color: "var(--pal-muted)" }}>{fmtDate(n.created_at)}</span>
                <div className="flex shrink-0 items-center gap-1">
                  {!n.read && (
                    <button type="button" disabled={marking === n.id} onClick={e => { e.stopPropagation(); markRead(n.id); }} className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground" title={t("notifications.mark_read")}>
                      {marking === n.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCheck className="h-3.5 w-3.5" />}
                    </button>
                  )}
                  <button type="button" onClick={e => { e.stopPropagation(); deleteNotification(n.id); }} className="rounded-lg p-1.5 text-muted-foreground hover:bg-destructive/10 hover:text-destructive" aria-label="Delete">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
                {!n.read && <span className="shrink-0 rounded-full" style={{ width: 7, height: 7, background: "var(--pal-primary)" }} />}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
