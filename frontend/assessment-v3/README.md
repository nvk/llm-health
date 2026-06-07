# Assessment v3 static cockpit frontend

This is the source for the polished static `health ui` cockpit. It is built once during development and the compiled assets are packaged under:

```text
src/llm_health/assessment_v2/web_static_v3/
```

End users do **not** need Node, Vite, React, or a web server. The Python export writes `data.js`, copies the prebuilt bundle, and opens `index.html` locally.

Development build:

```sh
cd frontend/assessment-v3
npm install
npm run typecheck
npm run build
```

Privacy rule: never put real health data, raw source paths, legal names, full dates of birth, or raw medical file names in this frontend tree. It should read only the generated de-identified `window.HEALTH_ASSESSMENT_V2` payload at runtime.

`npm run build` post-processes the generated Vite HTML so it can be opened directly from `file://` in Chrome/Safari: the app bundle is loaded as a deferred classic script, and asset tags omit `crossorigin`.
