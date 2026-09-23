import { createFileRoute, redirect } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { CalendarDays, Plus, Loader2, Trash2, Pencil } from "lucide-react";
import { ListSkeleton } from "@/components/Skeletons";
import { PageHead, SectionLabel, EmptyHint } from "@/components/dashboard/ui";
import { useDeepLinkFocus } from "@/lib/deep-link";

export const Route = createFileRoute("/dashboard/agenda")({
  beforeLoad: async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) throw redirect({ to: "/auth" });
  },
  component: AgendaPage,
});

type CalEvent = {
  id: string; title: string; description: string | null;
  start_time: string; end_time: string | null;
  event_type: string; course_id: string | null;
  created_by: string | null; course_title?: string;
};
type Course = { id: string; title: string };

type EventForm = { title: string; description: string; start_time: string; end_time: string; event_type: string; course_id: string };

const EMPTY_FORM: EventForm = { title: "", description: "", start_time: "", end_time: "", event_type: "event", course_id: "" };

// IPISB Connect redesign event tones: Cours green, Contrôle continu amber, Examen red, Événement blue
const TYPE_CHIP: Record<string, string> = {
  course:     "chip-c-green",
  exam:       "chip-c-red",
  assignment: "chip-c-amber",
  event:      "chip-c-blue",
};
const TYPE_BAR: Record<string, string> = {
  course:     "var(--pal-primary)",
  exam:       "var(--pal-danger)",
  assignment: "var(--pal-accent)",
  event:      "oklch(55% 0.1 250)",
};

function AgendaPage() {
  const { t, lang } = useI18n();
  const { user, roles } = useAuth();
  const isAdmin   = roles.includes("admin");
  const isProf    = roles.includes("professor");
  const canCreate = isAdmin || isProf;

  const [events,     setEvents]     = useState<CalEvent[]>([]);
  const [courses,    setCourses]    = useState<Course[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [selected,   setSelected]   = useState<Date>(new Date());
  // Deep-link depuis une notification (?focus=<id>) : la vue liste est la seule
  // où une ligne se surligne/défile proprement — on l'ouvre d'office.
  const { focusId, attachFocus } = useDeepLinkFocus();
  const [view,       setView]       = useState<"week" | "month" | "list">(focusId ? "list" : "week");
  const [weekStart,  setWeekStart]  = useState<Date>(() => {
    const d = new Date();
    d.setHours(0, 0, 0, 0);
    d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    return d;
  });

  // Create dialog
  const [showCreate, setShowCreate] = useState(false);
  const [creating,   setCreating]   = useState(false);
  const [form,       setForm]       = useState<EventForm>(EMPTY_FORM);

  // Edit dialog
  const [editEvent,  setEditEvent]  = useState<CalEvent | null>(null);
  const [editForm,   setEditForm]   = useState<EventForm>(EMPTY_FORM);
  const [updating,   setUpdating]   = useState(false);

  // Deleting
  const [deletingId, setDeletingId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const [evRes, coRes] = await Promise.all([
        supabase.from("calendar_events").select("*, courses(title)").order("start_time"),
        supabase.from("courses").select("id, title").order("title"),
      ]);
      setEvents((evRes.data ?? []).map((e: any) => ({ ...e, course_title: e.courses?.title ?? null, courses: undefined })));
      setCourses((coRes.data ?? []) as Course[]);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (!user) return null;

  function eventsForDate(date: Date) {
    return events.filter(e => {
      const d = new Date(e.start_time);
      return d.getFullYear() === date.getFullYear() && d.getMonth() === date.getMonth() && d.getDate() === date.getDate();
    });
  }

  // Convert a datetime-local string (treated as local time by the browser) to UTC ISO
  const localToUTC = (s: string) => s ? new Date(s).toISOString() : s;
  // Convert a UTC ISO string to a datetime-local input value (local time)
  const utcToLocal = (s: string) => {
    if (!s) return "";
    const d = new Date(s);
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  };

  // ---------- Create ----------
  async function createEvent() {
    if (!user) return;
    if (!form.title.trim())   { toast.error(t("agenda.title_required"));  return; }
    if (!form.start_time)     { toast.error(t("agenda.start_required"));  return; }
    setCreating(true);
    const { error } = await supabase.from("calendar_events").insert({
      title:       form.title,
      description: form.description || null,
      start_time:  localToUTC(form.start_time),
      end_time:    form.end_time ? localToUTC(form.end_time) : null,
      event_type:  form.event_type,
      course_id:   form.course_id || null,
      created_by:  user.id,
    });
    setCreating(false);
    if (error) { toast.error(error.message); return; }
    toast.success(t("agenda.created"));
    setShowCreate(false);
    setForm(EMPTY_FORM);
    load();
  }

  // ---------- Edit ----------
  function openEdit(ev: CalEvent) {
    setEditEvent(ev);
    setEditForm({
      title:       ev.title,
      description: ev.description ?? "",
      start_time:  utcToLocal(ev.start_time),
      end_time:    utcToLocal(ev.end_time ?? ""),
      event_type:  ev.event_type,
      course_id:   ev.course_id ?? "",
    });
  }

  async function updateEvent() {
    if (!editEvent) return;
    if (!editForm.title.trim())  { toast.error(t("agenda.title_required")); return; }
    if (!editForm.start_time)    { toast.error(t("agenda.start_required")); return; }
    setUpdating(true);
    const { error } = await supabase.from("calendar_events").update({
      title:       editForm.title,
      description: editForm.description || null,
      start_time:  localToUTC(editForm.start_time),
      end_time:    editForm.end_time ? localToUTC(editForm.end_time) : null,
      event_type:  editForm.event_type,
      course_id:   editForm.course_id || null,
    }).eq("id", editEvent.id);
    setUpdating(false);
    if (error) { toast.error(error.message); return; }
    toast.success(t("agenda.updated"));
    setEditEvent(null);
    load();
  }

  // ---------- Delete ----------
  async function deleteEvent(id: string) {
    setDeletingId(id);
    const { error } = await supabase.from("calendar_events").delete().eq("id", id);
    setDeletingId(null);
    if (error) { toast.error(error.message); return; }
    setEvents(prev => prev.filter(e => e.id !== id));
  }

  const selectedEvents = eventsForDate(selected);
  const eventDates     = events.map(e => new Date(e.start_time));
  const upcomingEvents = events.filter(e => new Date(e.start_time) >= new Date()).slice(0, 6);
  const listEvents     = events.filter(e => new Date(e.start_time) >= new Date());

  // Week grid (IPISB Connect redesign): 8:00–18:00, one column per day
  const FIRST_HOUR = 8;
  const LAST_HOUR  = 18;
  const HOUR_H     = 56;
  const gridHours  = Array.from({ length: LAST_HOUR - FIRST_HOUR }, (_, i) => FIRST_HOUR + i);
  const weekDays   = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + i);
    return d;
  });
  const isSameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  const shiftWeek = (dir: -1 | 1) => {
    setWeekStart(prev => {
      const d = new Date(prev);
      d.setDate(d.getDate() + dir * 7);
      return d;
    });
  };
  const viewLabel = (v: "week" | "month" | "list") => {
    const map = {
      week:  { fr: "Semaine", en: "Week",  ar: "أسبوع" },
      month: { fr: "Mois",    en: "Month", ar: "شهر"   },
      list:  { fr: "Liste",   en: "List",  ar: "قائمة" },
    };
    return map[v][lang as "fr" | "en" | "ar"] ?? map[v].fr;
  };
  const locale = lang === "fr" ? "fr-FR" : lang === "ar" ? "ar-MA" : "en-US";
  const weekMonthLabel = weekDays[3].toLocaleDateString(locale, { month: "long", year: "numeric" });

  const fmtTime = (d: string) => new Date(d).toLocaleTimeString(lang === "fr" ? "fr-FR" : lang === "ar" ? "ar-MA" : "en-US", { hour: "2-digit", minute: "2-digit" });
  const fmtDate = (date: Date) => date.toLocaleDateString(lang === "fr" ? "fr-FR" : lang === "ar" ? "ar-MA" : "en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" });
  const typeLabel = (type: string) => {
    const map: Record<string, { fr: string; en: string; ar: string }> = {
      course:     { fr: "Cours",       en: "Class",      ar: "درس"     },
      exam:       { fr: "Examen",      en: "Exam",       ar: "امتحان"  },
      assignment: { fr: "Contrôle continu", en: "Continuous assessment", ar: "مراقبة مستمرة" },
      event:      { fr: "Événement",   en: "Event",      ar: "حدث"     },
    };
    return map[type]?.[lang as "fr" | "en" | "ar"] ?? type;
  };

  // Shared form fields renderer (used for both create and edit dialogs)
  function FormFields({ values, onChange }: { values: EventForm; onChange: (f: EventForm) => void }) {
    return (
      <div className="space-y-4">
        <div>
          <label className="text-sm font-medium">{t("agenda.form.title")} *</label>
          <Input className="mt-1.5" value={values.title} onChange={e => onChange({ ...values, title: e.target.value })} />
        </div>
        <div>
          <label className="text-sm font-medium">{t("agenda.form.type")}</label>
          <Select value={values.event_type} onValueChange={v => onChange({ ...values, event_type: v })}>
            <SelectTrigger className="mt-1.5"><SelectValue /></SelectTrigger>
            <SelectContent>
              {["course", "exam", "assignment", "event"].map(type => (
                <SelectItem key={type} value={type}>{typeLabel(type)}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-sm font-medium">{t("agenda.form.start")} *</label>
            <Input className="mt-1.5" type="datetime-local" value={values.start_time} onChange={e => onChange({ ...values, start_time: e.target.value })} />
          </div>
          <div>
            <label className="text-sm font-medium">{t("agenda.form.end")}</label>
            <Input className="mt-1.5" type="datetime-local" value={values.end_time} onChange={e => onChange({ ...values, end_time: e.target.value })} />
          </div>
        </div>
        <div>
          <label className="text-sm font-medium">{t("agenda.form.course")}</label>
          <Select value={values.course_id || "none"} onValueChange={v => onChange({ ...values, course_id: v === "none" ? "" : v })}>
            <SelectTrigger className="mt-1.5">
              <SelectValue placeholder={lang === "fr" ? "Aucun cours lié" : lang === "ar" ? "لا يوجد درس" : "No linked course"} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">{lang === "fr" ? "Aucun" : lang === "ar" ? "لا شيء" : "None"}</SelectItem>
              {courses.map(c => <SelectItem key={c.id} value={c.id}>{c.title}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-sm font-medium">{t("agenda.form.description")}</label>
          <Textarea className="mt-1.5" rows={2} value={values.description} onChange={e => onChange({ ...values, description: e.target.value })} />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHead
        eyebrow={lang === "fr" ? "Calendrier" : lang === "ar" ? "التقويم" : "Calendar"}
        title={t("dash.agenda")}
        sub={t("agenda.subtitle")}
        actions={canCreate ? (
          <button type="button" onClick={() => setShowCreate(true)} className="btn-c btn-c-primary">
            <Plus size={15} strokeWidth={1.7} />{t("agenda.create")}
          </button>
        ) : undefined}
      />

      {/* View toggle pills + week navigation (per redesign) */}
      <div className="flex flex-wrap items-center gap-2">
        {(["week", "month", "list"] as const).map(v => (
          <button
            key={v}
            type="button"
            onClick={() => setView(v)}
            className={`btn-c btn-c-sm ${view === v ? "btn-c-primary" : "btn-c-ghost"}`}
          >
            {viewLabel(v)}
          </button>
        ))}
        {view === "week" && (
          <div className="ms-auto flex items-center gap-2">
            <button type="button" onClick={() => shiftWeek(-1)} aria-label="prev" className="btn-c btn-c-ghost" style={{ width: 32, height: 32, padding: 0, borderRadius: 999 }}>‹</button>
            <span className="h-serif capitalize" style={{ fontSize: 20 }}>{weekMonthLabel}</span>
            <button type="button" onClick={() => shiftWeek(1)} aria-label="next" className="btn-c btn-c-ghost" style={{ width: 32, height: 32, padding: 0, borderRadius: 999 }}>›</button>
          </div>
        )}
      </div>

      {/* Color legend */}
      <div className="flex flex-wrap items-center gap-4">
        {Object.entries(TYPE_BAR).map(([type, color]) => (
          <span key={type} className="flex items-center gap-1.5" style={{ fontSize: 11.5, fontWeight: 600, color: "var(--pal-muted)" }}>
            <span style={{ width: 10, height: 10, borderRadius: 3, background: color }} />{typeLabel(type)}
          </span>
        ))}
      </div>

      {loading ? (
        <ListSkeleton rows={4} />
      ) : view === "week" ? (
        <div className="dash-card card-pop overflow-x-auto" style={{ padding: 0 }}>
          <div style={{ minWidth: 820 }}>
            {/* Day header row */}
            <div style={{ display: "grid", gridTemplateColumns: "52px repeat(7, 1fr)", borderBottom: "1px solid var(--pal-line)" }}>
              <div />
              {weekDays.map(d => {
                const today = isSameDay(d, new Date());
                return (
                  <div key={d.toISOString()} style={{ padding: "12px 10px", borderInlineStart: "1px solid var(--pal-line)" }}>
                    <div className="eyebrow" style={{ fontSize: 10.5 }}>
                      {d.toLocaleDateString(locale, { weekday: "short" })}
                    </div>
                    <div className="h-serif" style={{ fontSize: 23, marginTop: 2, color: today ? "var(--pal-primary)" : "var(--pal-ink)" }}>
                      {d.getDate()}
                    </div>
                  </div>
                );
              })}
            </div>
            {/* Hour grid + events */}
            <div style={{ display: "grid", gridTemplateColumns: "52px repeat(7, 1fr)" }}>
              <div>
                {gridHours.map(h => (
                  <div key={h} style={{ height: HOUR_H, padding: "4px 6px", fontFamily: "var(--font-mono, monospace)", fontSize: 10, fontWeight: 600, color: "var(--pal-muted)" }}>
                    {String(h).padStart(2, "0")}:00
                  </div>
                ))}
              </div>
              {weekDays.map(day => (
                <div key={day.toISOString()} style={{ position: "relative", borderInlineStart: "1px solid var(--pal-line)" }}>
                  {gridHours.map(h => <div key={h} style={{ height: HOUR_H, borderTop: "1px solid var(--pal-line-soft, var(--pal-line))" }} />)}
                  {eventsForDate(day).map(ev => {
                    const start = new Date(ev.start_time);
                    const end   = ev.end_time ? new Date(ev.end_time) : null;
                    const startH = Math.min(Math.max(start.getHours() + start.getMinutes() / 60, FIRST_HOUR), LAST_HOUR - 0.5);
                    const endH   = end ? Math.min(Math.max(end.getHours() + end.getMinutes() / 60, startH + 0.5), LAST_HOUR) : startH + 1;
                    const color  = TYPE_BAR[ev.event_type] ?? "var(--pal-mid)";
                    const editable = canCreate && ev.created_by === user.id;
                    return (
                      <div
                        key={ev.id}
                        role={editable ? "button" : undefined}
                        onClick={() => { setSelected(start); if (editable) openEdit(ev); }}
                        title={`${fmtTime(ev.start_time)}${ev.end_time ? "–" + fmtTime(ev.end_time) : ""} · ${ev.title}`}
                        style={{
                          position: "absolute",
                          top: (startH - FIRST_HOUR) * HOUR_H + 2,
                          insetInline: 4,
                          height: Math.max((endH - startH) * HOUR_H - 4, 24),
                          background: `color-mix(in oklab, ${color} 18%, white)`,
                          borderInlineStart: `3px solid ${color}`,
                          borderRadius: 8,
                          padding: "6px 9px",
                          fontSize: 12,
                          fontWeight: 600,
                          color: "var(--pal-ink)",
                          overflow: "hidden",
                          cursor: editable ? "pointer" : "default",
                        }}
                      >
                        {ev.title}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : view === "list" ? (
        listEvents.length === 0 ? (
          <div className="dash-card">
            <EmptyHint icon={<CalendarDays size={28} strokeWidth={1.7} />} text={t("agenda.empty_day")} />
          </div>
        ) : (
          <div className="dash-card card-pop overflow-hidden">
            {listEvents.map(ev => (
              <div key={ev.id} ref={ev.id === focusId ? attachFocus : undefined} className="row-c">
                <span className="shrink-0" style={{ width: 10, height: 10, borderRadius: 3, background: TYPE_BAR[ev.event_type] ?? "var(--pal-mid)" }} />
                <div className="min-w-0 flex-1">
                  <p className="truncate" style={{ fontSize: 13.5, fontWeight: 700, color: "var(--pal-ink)" }}>{ev.title}</p>
                  <p style={{ fontSize: 12, color: "var(--pal-muted)" }}>
                    {new Date(ev.start_time).toLocaleDateString(locale, { weekday: "long", month: "long", day: "numeric" })} · {fmtTime(ev.start_time)}
                    {ev.course_title ? ` · ${ev.course_title}` : ""}
                  </p>
                </div>
                <span className={`chip-c ${TYPE_CHIP[ev.event_type] ?? ""}`}>{typeLabel(ev.event_type)}</span>
                {canCreate && ev.created_by === user.id && (
                  <div className="flex shrink-0 items-center gap-1">
                    <button type="button" onClick={() => openEdit(ev)} className="rounded p-1 text-muted-foreground hover:text-foreground">
                      <Pencil className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      disabled={deletingId === ev.id}
                      onClick={() => { if (window.confirm(t("agenda.deleted"))) deleteEvent(ev.id); }}
                      className="rounded p-1 text-muted-foreground hover:text-destructive disabled:opacity-50"
                    >
                      {deletingId === ev.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )
      ) : (
        <div className="grid gap-5 lg:grid-cols-[auto,1fr]">
          {/* Calendar picker */}
          <div className="dash-card card-pop p-4">
            <Calendar
              mode="single"
              selected={selected}
              onSelect={d => d && setSelected(d)}
              modifiers={{ hasEvent: eventDates }}
              modifiersClassNames={{ hasEvent: "font-bold underline decoration-primary/60" }}
              className="rounded-xl"
            />
          </div>

          {/* Day events panel */}
          <div className="min-w-0 space-y-4">
            <div>
              <h2 className="h-serif capitalize" style={{ fontSize: 21 }}>{fmtDate(selected)}</h2>
              <p className="text-sm" style={{ color: "var(--pal-muted)" }}>
                {selectedEvents.length}{" "}
                {lang === "fr"
                  ? selectedEvents.length === 1 ? "événement" : "événements"
                  : lang === "ar"
                  ? selectedEvents.length === 1 ? "حدث" : "أحداث"
                  : selectedEvents.length === 1 ? "event" : "events"}
              </p>
            </div>

            {selectedEvents.length === 0 ? (
              <div className="dash-card">
                <EmptyHint
                  icon={<CalendarDays size={28} strokeWidth={1.7} />}
                  text={
                    <span className="flex flex-col items-center gap-3">
                      {t("agenda.empty_day")}
                      {canCreate && (
                        <button
                          type="button"
                          className="btn-c btn-c-ghost btn-c-sm"
                          onClick={() => { setForm(f => ({ ...f, start_time: utcToLocal(selected.toISOString()) })); setShowCreate(true); }}
                        >
                          <Plus size={13} strokeWidth={1.7} />{t("agenda.create")}
                        </button>
                      )}
                    </span>
                  }
                />
              </div>
            ) : (
              <div className="dash-card card-pop overflow-hidden">
                {selectedEvents.map(ev => (
                  <div key={ev.id} className="row-c">
                    <div className="flex flex-col items-end" style={{ minWidth: 52 }}>
                      <span style={{ fontWeight: 800, fontSize: 13.5, fontVariantNumeric: "tabular-nums", color: "var(--pal-ink)" }}>{fmtTime(ev.start_time)}</span>
                      {ev.end_time && <span style={{ fontSize: 11, color: "var(--pal-muted)" }}>{fmtTime(ev.end_time)}</span>}
                    </div>
                    <div className="self-stretch" style={{ width: 3, borderRadius: 99, background: TYPE_BAR[ev.event_type] ?? "var(--pal-mid)" }} />
                    <div className="min-w-0 flex-1">
                      <div style={{ fontWeight: 700, fontSize: 13.5, color: "var(--pal-ink)" }}>{ev.title}</div>
                      {(ev.course_title || ev.description) && (
                        <div className="mt-0.5" style={{ fontSize: 12, color: "var(--pal-muted)" }}>
                          {[ev.course_title, ev.description].filter(Boolean).join(" · ")}
                        </div>
                      )}
                    </div>
                    <span className={`chip-c ${TYPE_CHIP[ev.event_type] ?? ""}`}>{typeLabel(ev.event_type)}</span>
                    {canCreate && ev.created_by === user.id && (
                      <div className="flex shrink-0 items-center gap-1">
                        <button
                          type="button"
                          onClick={() => openEdit(ev)}
                          className="rounded p-1 text-muted-foreground hover:text-foreground"
                          title={lang === "fr" ? "Modifier" : "Edit"}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          type="button"
                          disabled={deletingId === ev.id}
                          onClick={() => { if (window.confirm(t("agenda.deleted"))) deleteEvent(ev.id); }}
                          className="rounded p-1 text-muted-foreground hover:text-destructive disabled:opacity-50"
                        >
                          {deletingId === ev.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Upcoming events strip */}
      {!loading && view === "month" && upcomingEvents.length > 0 && (
        <div>
          <SectionLabel>{t("agenda.upcoming")}</SectionLabel>
          <div className="dash-card overflow-hidden">
            {upcomingEvents.map((ev, idx) => (
              <button
                key={ev.id}
                type="button"
                onClick={() => setSelected(new Date(ev.start_time))}
                className="row-c w-full cursor-pointer text-start"
                style={{ background: "transparent", border: 0, borderTop: idx === 0 ? undefined : "1px solid var(--pal-line-soft)" }}
              >
                <span className="shrink-0" style={{ width: 10, height: 10, borderRadius: 3, background: TYPE_BAR[ev.event_type] ?? "var(--pal-mid)" }} />
                <div className="min-w-0 flex-1">
                  <p className="truncate" style={{ fontSize: 13.5, fontWeight: 700, color: "var(--pal-ink)" }}>{ev.title}</p>
                  <p style={{ fontSize: 12, color: "var(--pal-muted)" }}>
                    {new Date(ev.start_time).toLocaleDateString(lang === "fr" ? "fr-FR" : lang === "ar" ? "ar-MA" : "en-US", { month: "short", day: "numeric" })} · {fmtTime(ev.start_time)}
                  </p>
                </div>
                <span className={`chip-c ${TYPE_CHIP[ev.event_type] ?? ""}`}>{typeLabel(ev.event_type)}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Create Dialog ── */}
      <Dialog open={showCreate} onOpenChange={v => { setShowCreate(v); if (!v) setForm(EMPTY_FORM); }}>
        <DialogContent>
          <DialogHeader><DialogTitle className="font-display">{t("agenda.create")}</DialogTitle></DialogHeader>
          <FormFields values={form} onChange={setForm} />
          <DialogFooter>
            <Button variant="outline" onClick={() => { setShowCreate(false); setForm(EMPTY_FORM); }}>{t("common.cancel")}</Button>
            <Button className="border-0 bg-gradient-brand text-white" disabled={creating} onClick={createEvent}>
              {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : t("agenda.create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Edit Dialog ── */}
      <Dialog open={!!editEvent} onOpenChange={v => { if (!v) setEditEvent(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-display">
              {lang === "fr" ? "Modifier l'événement" : lang === "ar" ? "تعديل الحدث" : "Edit event"}
            </DialogTitle>
          </DialogHeader>
          <FormFields values={editForm} onChange={setEditForm} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditEvent(null)}>{t("common.cancel")}</Button>
            <Button className="border-0 bg-gradient-brand text-white" disabled={updating} onClick={updateEvent}>
              {updating ? <Loader2 className="h-4 w-4 animate-spin" /> : t("common.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
