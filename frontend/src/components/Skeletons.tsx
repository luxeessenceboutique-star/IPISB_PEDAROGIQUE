import { Skeleton } from "@/components/ui/skeleton";

/** Grid of card-shaped skeletons (course cards, meeting cards, stat cards…). */
export function CardGridSkeleton({ count = 6, cardClassName = "" }: { count?: number; cardClassName?: string }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className={`rounded-2xl border border-border bg-card p-5 shadow-card ${cardClassName}`}
          style={{ animationDelay: `${i * 70}ms` }}
        >
          <Skeleton className="h-10 w-10 rounded-xl" />
          <Skeleton className="mt-4 h-5 w-3/4" />
          <Skeleton className="mt-2 h-4 w-full" />
          <Skeleton className="mt-2 h-4 w-2/3" />
        </div>
      ))}
    </div>
  );
}

/** Stacked row skeletons (lists: notifications, assignments, agenda…). */
export function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-4 rounded-2xl border border-border bg-card p-5 shadow-card"
          style={{ animationDelay: `${i * 70}ms` }}
        >
          <Skeleton className="h-10 w-10 shrink-0 rounded-xl" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-3 w-2/3" />
          </div>
          <Skeleton className="h-8 w-20 rounded-lg" />
        </div>
      ))}
    </div>
  );
}

/** 4-up stat card skeletons for the dashboard overview. */
export function StatCardsSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-2xl border border-border bg-card p-5 shadow-card">
          <Skeleton className="h-10 w-10 rounded-xl" />
          <Skeleton className="mt-4 h-8 w-16" />
          <Skeleton className="mt-2 h-4 w-24" />
        </div>
      ))}
    </div>
  );
}
