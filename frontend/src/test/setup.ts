/** Vitest setup: jest-dom matchers and browser APIs jsdom does not provide. */

import "@testing-library/jest-dom/vitest";

// jsdom lacks crypto.randomUUID in some versions; the coach page relies on it.
if (!globalThis.crypto?.randomUUID) {
  Object.defineProperty(globalThis, "crypto", {
    value: {
      ...globalThis.crypto,
      randomUUID: () => `test-${Math.random().toString(36).slice(2)}`,
    },
    configurable: true,
  });
}

// Neither is implemented by jsdom.
window.scrollTo = () => {};
Element.prototype.scrollIntoView = () => {};
