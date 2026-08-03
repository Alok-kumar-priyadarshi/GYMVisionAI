/**
 * Shared UI components.
 *
 * `instructions/03_FRONTEND_RULES.md` section 10 requires consistent spacing
 * and reusable components, and section 4 keeps business logic out of them.
 * Every component here is presentational.
 *
 * Each page is required to have a loading, error and empty state, so those are
 * components rather than ad-hoc markup.
 */

import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

function cx(...classes: (string | false | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

// --- Button ----------------------------------------------------------------

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
  fullWidth?: boolean;
}

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 disabled:bg-brand-300",
  secondary:
    "bg-white text-ink border border-line hover:bg-surface-muted disabled:text-ink-muted",
  ghost: "text-brand-700 hover:bg-brand-50 disabled:text-ink-muted",
  danger: "bg-danger text-white hover:opacity-90 disabled:opacity-50",
};

export function Button({
  variant = "primary",
  loading = false,
  fullWidth = false,
  className,
  children,
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      // Communicates the busy state to assistive technology, not just visually.
      aria-busy={loading || undefined}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5",
        "text-sm font-medium transition-colors disabled:cursor-not-allowed",
        BUTTON_VARIANTS[variant],
        fullWidth && "w-full",
        className,
      )}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  );
}

// --- Feedback --------------------------------------------------------------

/**
 * A spinning indicator.
 *
 * Decorative by default. It always appears beside visible text or inside an
 * element marked `aria-busy`, so announcing it separately would be noise, and
 * giving it a status role would collide with real status messages.
 */
export function Spinner({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  const dimension = { sm: "h-4 w-4", md: "h-6 w-6", lg: "h-9 w-9" }[size];

  return (
    <span
      aria-hidden="true"
      className={cx(
        "inline-block animate-spin rounded-full border-2 border-current border-t-transparent",
        dimension,
      )}
    />
  );
}

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div
      role="status"
      className="flex flex-col items-center gap-3 py-16 text-ink-muted"
    >
      <Spinner size="lg" />
      <p className="text-sm">{label}…</p>
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: {
  title?: string;
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-card border border-line bg-white p-8 text-center"
    >
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      {message && <p className="mt-2 text-sm text-ink-muted">{message}</p>}
      {onRetry && (
        <Button variant="secondary" className="mt-5" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  message,
  action,
}: {
  title: string;
  message?: string;
  action?: ReactNode;
}) {
  return (
    <div className="rounded-card border border-dashed border-line bg-white p-10 text-center">
      <h2 className="text-base font-semibold text-ink">{title}</h2>
      {message && <p className="mt-2 text-sm text-ink-muted">{message}</p>}
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}

// --- Surfaces --------------------------------------------------------------

export function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cx(
        "rounded-card border border-line bg-white p-5 shadow-sm",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-muted">{subtitle}</p>}
      </div>
      {action}
    </header>
  );
}

export function StatTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <Card className="text-center">
      <p className="text-xs font-medium uppercase tracking-wide text-ink-muted">
        {label}
      </p>
      <p className="mt-2 text-3xl font-semibold tabular-nums text-ink">{value}</p>
      {hint && <p className="mt-1 text-xs text-ink-muted">{hint}</p>}
    </Card>
  );
}

const BADGE_TONES = {
  neutral: "bg-surface-muted text-ink-muted",
  brand: "bg-brand-50 text-brand-700",
  positive: "bg-positive/10 text-positive",
  warning: "bg-warning/15 text-warning",
} as const;

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: keyof typeof BADGE_TONES;
}) {
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        BADGE_TONES[tone],
      )}
    >
      {children}
    </span>
  );
}

// --- Form controls ---------------------------------------------------------

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
}

export function Field({ label, error, hint, id, ...rest }: FieldProps) {
  const fieldId = id ?? `field-${label.toLowerCase().replace(/\s+/g, "-")}`;
  const describedBy = error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined;

  return (
    <div>
      <label htmlFor={fieldId} className="block text-sm font-medium text-ink">
        {label}
      </label>
      <input
        {...rest}
        id={fieldId}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={cx(
          "mt-1.5 w-full rounded-lg border bg-white px-3 py-2 text-sm text-ink",
          "placeholder:text-ink-muted",
          error ? "border-danger" : "border-line",
        )}
      />
      {error && (
        <p id={`${fieldId}-error`} className="mt-1 text-xs text-danger">
          {error}
        </p>
      )}
      {!error && hint && (
        <p id={`${fieldId}-hint`} className="mt-1 text-xs text-ink-muted">
          {hint}
        </p>
      )}
    </div>
  );
}

interface SelectFieldProps {
  label: string;
  value: string;
  options: readonly string[];
  onChange: (value: string) => void;
  id?: string;
}

export function SelectField({
  label,
  value,
  options,
  onChange,
  id,
}: SelectFieldProps) {
  const fieldId = id ?? `select-${label.toLowerCase().replace(/\s+/g, "-")}`;

  return (
    <div>
      <label htmlFor={fieldId} className="block text-sm font-medium text-ink">
        {label}
      </label>
      <select
        id={fieldId}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1.5 w-full rounded-lg border border-line bg-white px-3 py-2 text-sm text-ink"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}
