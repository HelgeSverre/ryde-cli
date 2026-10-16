# Dashboard source

This directory contains the React/MapLibre/deck.gl dashboard copied from a private
prototype. It contains no personal datasets or auth state. The Python package
ships the compiled output under `src/ryde_cli/web/`; end users only need uv.

Frontend development requires Node.js 22+ and npm:

```sh
cd web
npm ci
npm test
npm run build
npm run test:e2e
```

Commit the rebuilt UI assets alongside source changes. CI rebuilds and verifies
that the checked-in bundle matches. `publicDir: false` is mandatory: Vite must
never copy private `public/data` files into the package. Source maps are disabled.
Browser tests use generated synthetic records, never a personal account.

For the complete application, from the repository root run:

```sh
uv run ryde stats
```
