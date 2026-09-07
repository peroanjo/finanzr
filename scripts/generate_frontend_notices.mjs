#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const frontend = path.join(root, "frontend");
const lock = JSON.parse(
  fs.readFileSync(path.join(frontend, "package-lock.json"), "utf8"),
);
const outputPath = path.join(frontend, "public", "THIRD_PARTY_NOTICES.txt");
const queue = Object.keys(lock.packages[""].dependencies).map((name) => ({
  name,
  parent: "",
}));
const visited = new Set();
const packages = [];

function resolvePackage(name, parent) {
  let current = parent;
  while (true) {
    const candidate = path.posix.join(current, "node_modules", name);
    if (lock.packages[candidate]) return candidate;
    const marker = current.lastIndexOf("/node_modules/");
    if (marker === -1) break;
    current = current.slice(0, marker);
  }
  const candidate = path.posix.join("node_modules", name);
  if (lock.packages[candidate]) return candidate;
  throw new Error(
    `Unable to resolve ${name} from ${parent || "the application"}`,
  );
}

while (queue.length) {
  const request = queue.shift();
  const packagePath = resolvePackage(request.name, request.parent);
  if (visited.has(packagePath)) continue;
  visited.add(packagePath);
  const metadata = lock.packages[packagePath];
  packages.push({ name: request.name, packagePath, metadata });
  for (const name of Object.keys(metadata.dependencies ?? {})) {
    queue.push({ name, parent: packagePath });
  }
}

packages.sort((left, right) =>
  `${left.name}@${left.metadata.version}`.localeCompare(
    `${right.name}@${right.metadata.version}`,
  ),
);

const sections = packages.map(({ name, packagePath, metadata }) => {
  const directory = path.join(frontend, packagePath);
  let licenseDirectory = directory;
  let licenseName = fs
    .readdirSync(licenseDirectory)
    .find((entry) => /^licen[cs]e(?:\..+)?$/i.test(entry));
  if (!licenseName) {
    licenseDirectory = path.join(frontend, "node_modules", name);
    licenseName = fs
      .readdirSync(licenseDirectory)
      .find((entry) => /^licen[cs]e(?:\..+)?$/i.test(entry));
  }
  if (!licenseName) throw new Error(`No license file found for ${name}`);
  const license = fs
    .readFileSync(path.join(licenseDirectory, licenseName), "utf8")
    .trim();
  return [
    "=".repeat(78),
    `${name}@${metadata.version}`,
    `Source: ${metadata.resolved}`,
    "-".repeat(78),
    license,
  ].join("\n");
});

const output = `${[
  "Finanzr frontend third-party notices",
  "",
  "This file contains notices for the browser-runtime dependency graph resolved",
  "from frontend/package-lock.json. The corresponding source archives and package",
  "metadata are available from the registry URLs below.",
  "",
  ...sections,
].join("\n\n")}\n`;

if (process.argv.includes("--check")) {
  const current = fs.readFileSync(outputPath, "utf8");
  if (current !== output) {
    console.error("frontend/public/THIRD_PARTY_NOTICES.txt is stale");
    process.exit(1);
  }
} else {
  process.stdout.write(output);
}
