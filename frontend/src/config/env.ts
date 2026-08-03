/**
 * Environment access.
 *
 * A variable declared but left blank in `.env` arrives as an empty string, not
 * as `undefined`. `??` therefore keeps the empty value and silently defeats the
 * fallback, which is exactly the shape of bug that only appears in a real
 * deployment. Everything reads its configuration through here instead.
 */

/**
 * Return a configured value, treating blank as absent.
 *
 * @param value The raw value from `import.meta.env`.
 * @param fallback Used when the value is missing or blank.
 */
export function configured(value: unknown, fallback: string): string {
  if (typeof value !== "string") return fallback;

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : fallback;
}

/** Return a configured value, or null when it is missing or blank. */
export function optional(value: unknown): string | null {
  if (typeof value !== "string") return null;

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}
