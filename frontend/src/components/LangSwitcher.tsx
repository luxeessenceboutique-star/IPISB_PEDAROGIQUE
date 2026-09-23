import { useI18n } from "@/lib/i18n";

const LANGS = [
  { code: "fr", label: "FR" },
  { code: "en", label: "EN" },
  { code: "ar", label: "ع" },
] as const;

export function LangSwitcher() {
  const { lang, setLang } = useI18n();

  return (
    <div className="flex items-center rounded-full border border-border bg-muted/50 p-0.5 text-xs font-medium">
      {LANGS.map((l) => (
        <button
          key={l.code}
          onClick={() => setLang(l.code)}
          className={`rounded-full px-2.5 py-1 transition-all ${
            lang === l.code
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          {l.label}
        </button>
      ))}
    </div>
  );
}
