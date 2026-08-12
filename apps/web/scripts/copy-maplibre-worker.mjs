// MapLibre localiza seu worker via `import.meta.url` do próprio chunk, o que não
// resolve para uma URL http(s) real sob o bundler do Next.js (Turbopack) - ver o
// comentário em src/components/choropleth-map.tsx. Servimos uma cópia estática do
// worker (e do chunk `shared` do qual ele importa) e apontamos para ela via
// `setWorkerUrl()`. Rodado no `postinstall` porque os arquivos vêm de
// node_modules/maplibre-gl/dist - não são código-fonte deste projeto.
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const distDir = join(here, "..", "node_modules", "maplibre-gl", "dist");
const publicDir = join(here, "..", "public");

mkdirSync(publicDir, { recursive: true });

for (const arquivo of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(join(distDir, arquivo), join(publicDir, arquivo));
}

console.log("maplibre-gl worker copiado para public/");
