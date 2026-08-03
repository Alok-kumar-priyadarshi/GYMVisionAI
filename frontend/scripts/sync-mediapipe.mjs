/**
 * Copy the MediaPipe WASM runtime out of node_modules and into public/.
 *
 * The runtime must be the exact version of the installed
 * `@mediapipe/tasks-vision` package: its JavaScript glue and its WASM binary
 * are built together, and mixing versions fails to load. Pointing at a
 * version-pinned CDN meant the two drifted apart the moment npm resolved a
 * newer package.
 *
 * Copying from the installed package makes that impossible, and removes the
 * runtime dependency on a third-party CDN. The copied files are generated
 * output, so they are gitignored rather than committed.
 *
 * Runs automatically before `dev` and `build`.
 */

import { cp, mkdir, readFile, rm, stat } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const source = join(root, "node_modules", "@mediapipe", "tasks-vision", "wasm");
const target = join(root, "public", "mediapipe", "wasm");
const stamp = join(root, "public", "mediapipe", "version.txt");

async function installedVersion() {
  const manifest = join(
    root,
    "node_modules",
    "@mediapipe",
    "tasks-vision",
    "package.json",
  );
  return JSON.parse(await readFile(manifest, "utf8")).version;
}

async function alreadyCurrent(version) {
  try {
    return (await readFile(stamp, "utf8")).trim() === version;
  } catch {
    return false;
  }
}

async function main() {
  try {
    await stat(source);
  } catch {
    console.error(
      "MediaPipe runtime not found. Run `npm install` first.\n" +
        `Looked in: ${source}`,
    );
    process.exit(1);
  }

  const version = await installedVersion();

  if (await alreadyCurrent(version)) {
    console.log(`MediaPipe runtime ${version} already in place.`);
    return;
  }

  // Remove the old copy so a downgrade cannot leave stale files behind.
  await rm(join(root, "public", "mediapipe"), {
    recursive: true,
    force: true,
  });
  await mkdir(target, { recursive: true });
  await cp(source, target, { recursive: true });
  await (await import("node:fs/promises")).writeFile(stamp, version, "utf8");

  console.log(`Copied MediaPipe runtime ${version} to public/mediapipe/wasm.`);
}

await main();
