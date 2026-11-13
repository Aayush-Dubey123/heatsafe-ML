// Fails the build when the app's own JavaScript grows past its gzip budget.
// The map library is a separate lazy chunk and is reported but not counted against the app budget.
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { gzipSync } from "node:zlib";

const ASSETS = new URL("../dist/assets/", import.meta.url);
const APP_BUDGET_KB = 250;

const files = readdirSync(ASSETS).filter((name) => name.endsWith(".js"));
if (files.length === 0) {
  console.error("No built JavaScript found. Run `npm run build` first.");
  process.exit(1);
}

let appBytes = 0;
for (const name of files) {
  const gz = gzipSync(readFileSync(join(ASSETS.pathname.replace(/^\/([A-Za-z]:)/, "$1"), name))).length;
  const isMap = name.startsWith("maplibre");
  console.log(`${isMap ? "map " : "app "} ${(gz / 1024).toFixed(1).padStart(7)} KB gzip  ${name}`);
  if (!isMap) appBytes += gz;
}

const appKb = appBytes / 1024;
console.log(`App JavaScript total: ${appKb.toFixed(1)} KB gzip (budget ${APP_BUDGET_KB} KB)`);
if (appKb > APP_BUDGET_KB) {
  console.error("Over budget.");
  process.exit(1);
}
