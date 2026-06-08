import { cpSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const publicDir = join(root, "public");
const pathwayApp = join(root, "pathwayApp");

const htmlSource = join(pathwayApp, "pathwaylog2foldchange3d.html");
const imageSource = join(pathwayApp, "map05171@2x_20260606_220006.png");

mkdirSync(publicDir, { recursive: true });
cpSync(htmlSource, join(publicDir, "index.html"));
cpSync(imageSource, join(publicDir, "map05171@2x_20260606_220006.png"));

console.log("Synced pathwayApp → public/ (index.html + map image)");
