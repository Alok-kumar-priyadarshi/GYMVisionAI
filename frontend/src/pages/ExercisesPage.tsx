/**
 * Exercise library.
 *
 * Filtering happens in the browser: the library is 29 items, fetched once and
 * cached for the session, so a round trip per keystroke would be wasteful.
 */

import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  Field,
  LoadingState,
  PageHeader,
} from "@/components/ui";
import { useExercises } from "@/hooks/queries";
import type { ExerciseSummary } from "@/types/api";

const ALL = "All";

function categoriesOf(exercises: ExerciseSummary[]): string[] {
  return [ALL, ...Array.from(new Set(exercises.map((item) => item.category)))];
}

export default function ExercisesPage() {
  const { data, isPending, isError, refetch } = useExercises();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState(ALL);

  const exercises = useMemo(() => data ?? [], [data]);

  const visible = useMemo(() => {
    const term = search.trim().toLowerCase();
    return exercises.filter((item) => {
      const matchesCategory = category === ALL || item.category === category;
      const matchesSearch =
        !term ||
        item.name.toLowerCase().includes(term) ||
        item.category.toLowerCase().includes(term) ||
        item.difficulty.toLowerCase().includes(term);
      return matchesCategory && matchesSearch;
    });
  }, [exercises, search, category]);

  if (isPending) return <LoadingState label="Loading exercises" />;
  if (isError) {
    return (
      <ErrorState
        message="We could not load the exercise library."
        onRetry={() => void refetch()}
      />
    );
  }

  return (
    <>
      <PageHeader
        title="Exercises"
        subtitle={`${exercises.length} exercises you can do at home`}
      />

      <div className="mb-5 grid gap-3 sm:grid-cols-[1fr_auto]">
        <Field
          label="Search"
          type="search"
          placeholder="Push-ups, core, beginner…"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <div
          role="group"
          aria-label="Filter by category"
          className="flex flex-wrap items-end gap-2"
        >
          {categoriesOf(exercises).map((item) => (
            <button
              key={item}
              type="button"
              aria-pressed={category === item}
              onClick={() => setCategory(item)}
              className={[
                "rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                category === item
                  ? "bg-brand-600 text-white"
                  : "bg-white text-ink-muted border border-line hover:bg-surface-muted",
              ].join(" ")}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      {visible.length === 0 ? (
        <EmptyState
          title="No exercises match"
          message="Try a different search term or category."
        />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {visible.map((exercise) => (
            <li key={exercise.exerciseId}>
              <Link
                to={`/exercises/${exercise.exerciseId}`}
                className="block h-full rounded-card transition-shadow hover:shadow-md"
              >
                <Card className="h-full">
                  <p className="font-semibold text-ink">{exercise.name}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    <Badge tone="brand">{exercise.category}</Badge>
                    <Badge>{exercise.difficulty}</Badge>
                    <Badge
                      tone={
                        exercise.exerciseType === "Duration" ? "warning" : "neutral"
                      }
                    >
                      {exercise.exerciseType === "Duration" ? "Timed" : "Reps"}
                    </Badge>
                  </div>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
