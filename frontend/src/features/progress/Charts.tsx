/**
 * Charts for the progress page.
 *
 * Drawn as inline SVG rather than with a charting library. Two of these, with
 * no interaction beyond a tooltip, do not justify the dependency, and hand
 * drawing keeps them theme-aware and consistent with the rest of the UI.
 *
 * Every chart carries a text alternative. A picture of someone's training is
 * useless to a screen reader, so the same numbers are also exposed as a table.
 */

import type { ReactNode } from "react";

import type { DayPoint, SessionPoint } from "@/features/progress/series";

const VIEWBOX_WIDTH = 720;
const VIEWBOX_HEIGHT = 180;
const PADDING_TOP = 8;

/** Wraps a chart with its heading and its screen-reader alternative. */
function Figure({
  title,
  summary,
  table,
  children,
}: {
  title: string;
  summary: string;
  table: ReactNode;
  children: ReactNode;
}) {
  return (
    <figure className="mt-0">
      <figcaption className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        <span className="text-xs text-ink-muted">{summary}</span>
      </figcaption>

      {/* The drawing is decorative once the table below carries the data. */}
      <div aria-hidden="true">{children}</div>

      <div className="sr-only">{table}</div>
    </figure>
  );
}

function DataTable({
  caption,
  rows,
  unit,
}: {
  caption: string;
  rows: { label: string; value: number }[];
  unit: string;
}) {
  return (
    <table>
      <caption>{caption}</caption>
      <thead>
        <tr>
          <th scope="col">When</th>
          <th scope="col">{unit}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.label}>
            <th scope="row">{row.label}</th>
            <td>{row.value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * Daily training minutes as bars.
 *
 * The axis is a fixed run of days, so a gap in training reads as a gap.
 */
export function DailyActivityChart({ points }: { points: DayPoint[] }) {
  const peak = Math.max(...points.map((point) => point.minutes), 1);
  const slot = VIEWBOX_WIDTH / points.length;
  const barWidth = Math.max(slot * 0.6, 2);
  const trained = points.filter((point) => point.sessions > 0).length;

  return (
    <Figure
      title="Daily training"
      summary={`${trained} of the last ${points.length} days`}
      table={
        <DataTable
          caption="Minutes trained each day"
          unit="Minutes"
          rows={points.map((point) => ({
            label: point.label,
            value: point.minutes,
          }))}
        />
      }
    >
      <svg
        viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`}
        className="h-40 w-full"
        preserveAspectRatio="none"
      >
        {points.map((point, index) => {
          const height =
            point.minutes > 0
              ? ((VIEWBOX_HEIGHT - PADDING_TOP) * point.minutes) / peak
              : 0;
          return (
            <rect
              key={point.date}
              x={index * slot + (slot - barWidth) / 2}
              y={VIEWBOX_HEIGHT - height}
              width={barWidth}
              height={height}
              rx={2}
              className="fill-brand-500"
            >
              <title>{`${point.label}: ${point.minutes} min`}</title>
            </rect>
          );
        })}
      </svg>

      <div className="mt-1 flex justify-between text-xs text-ink-muted">
        <span>{points[0]?.label}</span>
        <span>{points[points.length - 1]?.label}</span>
      </div>
    </Figure>
  );
}

/** Repetitions per session, as a line, oldest on the left. */
export function RepTrendChart({ points }: { points: SessionPoint[] }) {
  const peak = Math.max(...points.map((point) => point.reps), 1);
  const total = points.reduce((sum, point) => sum + point.reps, 0);

  // A single session has no line to draw, only a point, so the divisor is
  // guarded rather than left to produce a NaN coordinate.
  const step =
    points.length > 1 ? VIEWBOX_WIDTH / (points.length - 1) : VIEWBOX_WIDTH;

  const coordinates = points.map((point, index) => {
    const x = points.length > 1 ? index * step : VIEWBOX_WIDTH / 2;
    const y =
      VIEWBOX_HEIGHT -
      ((VIEWBOX_HEIGHT - PADDING_TOP) * point.reps) / peak -
      PADDING_TOP / 2;
    return { x, y, point };
  });

  const path = coordinates
    .map(({ x, y }, index) => `${index === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`)
    .join(" ");

  return (
    <Figure
      title="Repetitions per session"
      summary={`${total} across ${points.length} sessions`}
      table={
        <DataTable
          caption="Repetitions in each session, oldest first"
          unit="Repetitions"
          rows={points.map((point) => ({
            label: point.label,
            value: point.reps,
          }))}
        />
      }
    >
      <svg
        viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`}
        className="h-40 w-full"
        preserveAspectRatio="none"
      >
        {points.length > 1 && (
          <path
            d={path}
            fill="none"
            strokeWidth={2.5}
            vectorEffect="non-scaling-stroke"
            className="stroke-brand-600"
          />
        )}
        {coordinates.map(({ x, y, point }) => (
          <circle
            key={point.sessionId}
            cx={x}
            cy={y}
            r={4}
            vectorEffect="non-scaling-stroke"
            className="fill-brand-600"
          >
            <title>{`${point.reps} reps`}</title>
          </circle>
        ))}
      </svg>
    </Figure>
  );
}
