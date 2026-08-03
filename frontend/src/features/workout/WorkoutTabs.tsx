/**
 * Switching between a user's workout plans.
 *
 * Generating a plan keeps the previous one, so a user accumulates several. This
 * is how they reach them: the current plan first, then earlier ones newest
 * first.
 *
 * Implemented as a real tablist rather than styled buttons, so arrow keys move
 * between tabs and assistive technology announces the position. Selection
 * follows focus, which is the expected behaviour when switching a tab is cheap.
 */

import { useRef } from "react";

import type { WorkoutTab } from "@/features/workout/tabs";

export function WorkoutTabs({
  tabs,
  selectedId,
  onSelect,
}: {
  tabs: WorkoutTab[];
  selectedId: string;
  onSelect: (workoutId: string) => void;
}) {
  const listRef = useRef<HTMLDivElement>(null);

  // One plan is not a choice, so there is nothing to switch between.
  if (tabs.length < 2) return null;

  function moveFocus(from: number, delta: number) {
    const next = (from + delta + tabs.length) % tabs.length;
    onSelect(tabs[next].workoutId);
    // Roving tabindex: only the selected tab is reachable by Tab, so focus has
    // to be moved deliberately when the selection changes.
    listRef.current
      ?.querySelectorAll<HTMLButtonElement>('[role="tab"]')
      ?.[next]?.focus();
  }

  function onKeyDown(event: React.KeyboardEvent, index: number) {
    if (event.key === "ArrowRight") {
      event.preventDefault();
      moveFocus(index, 1);
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      moveFocus(index, -1);
    } else if (event.key === "Home") {
      event.preventDefault();
      moveFocus(0, 0);
    } else if (event.key === "End") {
      event.preventDefault();
      moveFocus(tabs.length - 1, 0);
    }
  }

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label="Your workouts"
      className="mb-6 flex gap-2 overflow-x-auto border-b border-line pb-px"
    >
      {tabs.map((tab, index) => {
        const selected = tab.workoutId === selectedId;

        return (
          <button
            key={tab.workoutId}
            role="tab"
            type="button"
            id={`workout-tab-${tab.workoutId}`}
            aria-selected={selected}
            aria-controls={`workout-panel-${tab.workoutId}`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onSelect(tab.workoutId)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={
              selected
                ? "shrink-0 border-b-2 border-brand-600 px-3 py-2 text-left text-sm font-medium text-brand-700"
                : "shrink-0 border-b-2 border-transparent px-3 py-2 text-left text-sm text-ink-muted hover:text-ink"
            }
          >
            <span className="block whitespace-nowrap">{tab.label}</span>
            <span className="block text-xs font-normal text-ink-muted">
              {tab.detail}
            </span>
          </button>
        );
      })}
    </div>
  );
}
