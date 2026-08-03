/** Tests for environment access. */

import { describe, expect, it } from "vitest";

import { configured, optional } from "@/config/env";

describe("configured", () => {
  it("returns the supplied value", () => {
    expect(configured("https://cdn.test/wasm", "fallback")).toBe(
      "https://cdn.test/wasm",
    );
  });

  it("falls back when the variable is declared but blank", () => {
    // `VITE_POSE_MODEL_URL=` in a .env file arrives as an empty string, and
    // `?? fallback` would keep it. That silently broke the pose model.
    expect(configured("", "fallback")).toBe("fallback");
    expect(configured("   ", "fallback")).toBe("fallback");
  });

  it("falls back when the variable is absent", () => {
    expect(configured(undefined, "fallback")).toBe("fallback");
    expect(configured(null, "fallback")).toBe("fallback");
  });

  it("trims surrounding whitespace", () => {
    expect(configured("  /api/v1  ", "fallback")).toBe("/api/v1");
  });
});

describe("optional", () => {
  it("returns the supplied value", () => {
    expect(optional("client-id")).toBe("client-id");
  });

  it("treats blank as absent", () => {
    expect(optional("")).toBeNull();
    expect(optional("  ")).toBeNull();
    expect(optional(undefined)).toBeNull();
  });
});
