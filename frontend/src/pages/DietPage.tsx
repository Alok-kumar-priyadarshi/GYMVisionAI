/**
 * The user's diet plan.
 *
 * Shows the active plan, lets the user regenerate it, and opens any earlier
 * plan from history. Plans are stored when generated, so this page reads back
 * the same plan on every later visit rather than producing a new one.
 *
 * Everything here comes from the Diet Planning Engine, which is deterministic
 * and configuration-driven. `docs/03_business/23_DIET_PLANNING_ENGINE.md`
 * section 18 forbids generating diets with an LLM, so no figure on this page is
 * model-authored.
 */

import { useState } from "react";

import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingState,
  PageHeader,
} from "@/components/ui";
import {
  useCurrentDiet,
  useDietHistory,
  useDietPlan,
  useGenerateDiet,
} from "@/hooks/queries";
import { ApiError } from "@/services/api/client";
import type { DietPlan, DietPreference, Meal } from "@/types/api";

const PREFERENCES: DietPreference[] = [
  "Vegetarian",
  "Vegan",
  "Non Vegetarian",
];

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

/** Portions are planned in quarter servings, so 1 and 1.5 both read cleanly. */
function formatServings(servings: number): string {
  return Number.isInteger(servings) ? String(servings) : servings.toFixed(2).replace(/0$/, "");
}

function MacroSummary({ plan }: { plan: DietPlan }) {
  const macros = [
    { label: "Calories", value: `${Math.round(plan.totals.calories)} kcal` },
    { label: "Protein", value: `${plan.totals.proteinG} g` },
    { label: "Carbs", value: `${plan.totals.carbohydratesG} g` },
    { label: "Fat", value: `${plan.totals.fatG} g` },
    { label: "Water", value: `${(plan.waterTargetMl / 1000).toFixed(1)} L` },
  ];

  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {macros.map((macro) => (
        <Card key={macro.label} className="text-center">
          <dt className="text-xs font-medium uppercase tracking-wide text-ink-muted">
            {macro.label}
          </dt>
          <dd className="mt-1 text-lg font-semibold text-ink">{macro.value}</dd>
        </Card>
      ))}
    </dl>
  );
}

function MealCard({ meal }: { meal: Meal }) {
  return (
    <Card>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-semibold text-ink">{meal.mealType}</h3>
        <span className="text-sm text-ink-muted">
          about {meal.targetCalories} kcal
        </span>
      </div>

      <ul className="mt-3 divide-y divide-line">
        {meal.items.map((item) => (
          <li
            key={item.foodId}
            className="flex flex-wrap items-baseline justify-between gap-2 py-2"
          >
            <div className="min-w-0">
              <p className="text-sm font-medium text-ink">{item.name}</p>
              <p className="text-xs text-ink-muted">
                {formatServings(item.servings)} × {item.servingSize}
              </p>
            </div>
            <p className="text-sm text-ink-muted">
              {Math.round(item.calories)} kcal
              <span className="ml-2 text-xs">
                P {item.proteinG} · C {item.carbohydratesG} · F {item.fatG}
              </span>
            </p>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function PlanView({ plan }: { plan: DietPlan }) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap gap-2">
        <Badge tone="brand">{plan.goal}</Badge>
        <Badge>{plan.dietPreference}</Badge>
        {plan.status === "Archived" && <Badge tone="warning">Archived</Badge>}
        <Badge>Created {formatDate(plan.createdAt)}</Badge>
      </div>

      <MacroSummary plan={plan} />

      <div className="space-y-3">
        {plan.meals.map((meal) => (
          <MealCard key={meal.mealId} meal={meal} />
        ))}
      </div>

      {/* Required by `23_DIET_PLANNING_ENGINE.md` section 10. */}
      <p className="text-xs leading-relaxed text-ink-muted">
        This plan is an estimate generated from your profile to guide food
        choices. It is not medical or dietary advice. Speak to a qualified
        professional before making significant changes to what you eat,
        particularly if you have a health condition.
      </p>
    </div>
  );
}

function PreferencePicker({
  value,
  onChange,
  disabled,
}: {
  value: DietPreference | null;
  onChange: (next: DietPreference) => void;
  disabled: boolean;
}) {
  return (
    <fieldset className="flex flex-wrap items-center gap-2" disabled={disabled}>
      <legend className="sr-only">Dietary preference</legend>
      {PREFERENCES.map((preference) => {
        const selected = preference === value;
        return (
          <button
            key={preference}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(preference)}
            className={
              selected
                ? "rounded-full border border-brand-600 bg-brand-50 px-3 py-1 text-sm font-medium text-brand-700"
                : "rounded-full border border-line px-3 py-1 text-sm text-ink-muted hover:bg-surface-muted disabled:opacity-50"
            }
          >
            {preference}
          </button>
        );
      })}
    </fieldset>
  );
}

export default function DietPage() {
  const current = useCurrentDiet();
  const generate = useGenerateDiet();
  const history = useDietHistory(1);
  const [viewing, setViewing] = useState<string | null>(null);
  const archived = useDietPlan(viewing);
  const [preference, setPreference] = useState<DietPreference | null>(null);

  if (current.isPending) return <LoadingState label="Loading your diet plan" />;

  // A 404 is the documented answer for "no plan yet", not a failure.
  const hasNoPlan =
    current.error instanceof ApiError && current.error.status === 404;

  function build() {
    generate.mutate(preference ?? undefined, {
      onSuccess: () => setViewing(null),
    });
  }

  if (hasNoPlan) {
    return (
      <>
        <PageHeader title="Diet" />
        <EmptyState
          title="No diet plan yet"
          message="Build a day of meals from your profile, using only foods in the catalogue."
          action={
            <div className="space-y-4">
              <PreferencePicker
                value={preference}
                onChange={setPreference}
                disabled={generate.isPending}
              />
              <Button loading={generate.isPending} onClick={build}>
                Build my diet plan
              </Button>
            </div>
          }
        />
        {generate.isError && (
          <p role="alert" className="mt-3 text-center text-sm text-danger">
            {generate.error instanceof ApiError
              ? generate.error.message
              : "We could not build a diet plan."}
          </p>
        )}
      </>
    );
  }

  if (current.isError || !current.data) {
    return (
      <ErrorState
        message="We could not load your diet plan."
        onRetry={() => void current.refetch()}
      />
    );
  }

  const plan = current.data;
  const earlier = (history.data?.data ?? []).filter(
    (entry) => entry.dietPlanId !== plan.dietPlanId,
  );

  return (
    <>
      <PageHeader
        title="Diet"
        subtitle={`${plan.meals.length} meals · about ${plan.estimatedCalories} kcal a day`}
        action={
          <Button
            variant="secondary"
            loading={generate.isPending}
            onClick={build}
          >
            Generate a new one
          </Button>
        }
      />

      <div className="mb-6">
        <PreferencePicker
          value={preference ?? (plan.dietPreference as DietPreference)}
          onChange={setPreference}
          disabled={generate.isPending}
        />
      </div>

      {generate.isError && (
        <p role="alert" className="mb-4 text-sm text-danger">
          {generate.error instanceof ApiError
            ? generate.error.message
            : "We could not build a diet plan."}
        </p>
      )}

      {viewing && archived.data ? (
        <section aria-label="Archived diet plan" className="space-y-4">
          <Button variant="ghost" onClick={() => setViewing(null)}>
            ← Back to my current plan
          </Button>
          <PlanView plan={archived.data} />
        </section>
      ) : viewing && archived.isPending ? (
        <LoadingState label="Loading that plan" />
      ) : (
        <PlanView plan={plan} />
      )}

      {earlier.length > 0 && (
        <section aria-label="Earlier plans" className="mt-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-ink-muted">
            Earlier plans
          </h2>
          <ul className="space-y-2">
            {earlier.map((entry) => (
              <li key={entry.dietPlanId}>
                <Card>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-ink">
                        {formatDate(entry.createdAt)}
                      </p>
                      <p className="text-xs text-ink-muted">
                        {entry.dietPreference} · {entry.mealCount} meals ·{" "}
                        {entry.estimatedCalories} kcal
                      </p>
                    </div>
                    <Button
                      variant="secondary"
                      onClick={() => setViewing(entry.dietPlanId)}
                    >
                      View
                    </Button>
                  </div>
                </Card>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
