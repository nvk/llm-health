import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const indexPath = resolve(here, '../../../src/llm_health/assessment_v2/web_static_v3/index.html');
let html = readFileSync(indexPath, 'utf8');
html = html.replace(/<script type="module" crossorigin src="(\.\/assets\/index-[^"]+\.js)"><\/script>/, '<script defer src="$1"></script>');
html = html.replace(/<link rel="stylesheet" crossorigin href="(\.\/assets\/index-[^"]+\.css)">/, '<link rel="stylesheet" href="$1">');
writeFileSync(indexPath, html);
