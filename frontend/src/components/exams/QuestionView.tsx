/**
 * Shared question-rendering component — used by BOTH the student's real
 * exam-taking screen (dashboard.exams.tsx) and the professor's "Preview"
 * inside the exam editor (dashboard.exams_.$examId_.editor.tsx). Spec §21
 * is explicit that preview must not be a fake mockup: it must render with
 * the exact same code path a student sees, so this is the one place that
 * logic lives.
 */
export type QuestionViewData = {
  id: string;
  question: string;
  options: string[];
  type?: string;
  image_url?: string | null;
  image_caption?: string | null;
};

export function QuestionView({
  q,
  index,
  selectedOption,
  onSelect,
  disabled,
  revealCorrect,
  correctIndex,
}: {
  q: QuestionViewData;
  index: number;
  selectedOption?: number;
  onSelect?: (optionIndex: number) => void;
  disabled?: boolean;
  revealCorrect?: boolean;
  correctIndex?: number;
}) {
  return (
    <div>
      <p className="font-medium">
        <span className="mr-2 text-muted-foreground">{index + 1}.</span>
        {q.question || <span className="italic text-muted-foreground">—</span>}
      </p>
      {q.image_url && (
        <figure className="mt-3">
          <img src={q.image_url} alt="" className="max-h-72 w-auto rounded-xl border border-border object-contain" />
          {q.image_caption && <figcaption className="mt-1 text-xs text-muted-foreground">{q.image_caption}</figcaption>}
        </figure>
      )}
      <div className="mt-3 space-y-2">
        {q.options.map((opt, oi) => {
          const isSelected = selectedOption === oi;
          const isCorrect = revealCorrect && correctIndex === oi;
          const isWrongPick = revealCorrect && isSelected && correctIndex !== oi;
          return (
            <button
              key={oi}
              type="button"
              disabled={disabled}
              onClick={() => onSelect?.(oi)}
              className={`w-full rounded-xl border px-4 py-2.5 text-left text-sm transition-all ${
                isCorrect
                  ? "border-green-400 bg-green-50 font-medium text-green-800"
                  : isWrongPick
                  ? "border-red-300 bg-red-50 text-red-700 line-through"
                  : isSelected
                  ? "border-primary bg-primary/10 font-medium text-primary"
                  : "border-border hover:border-primary/40 hover:bg-muted/60"
              } ${disabled ? "cursor-default" : ""}`}
            >
              <span className="mr-2 font-mono text-xs text-muted-foreground">{String.fromCharCode(65 + oi)}.</span>
              {opt || <span className="italic text-muted-foreground/70">—</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}
