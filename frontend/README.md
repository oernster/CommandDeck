# Command Deck frontend

The single-screen React and TypeScript UI for Command Deck, built with Vite. It talks to the backend only through `/api/*`; in development the Vite dev server proxies those requests to `http://127.0.0.1:8001` (see [`vite.config.ts`](vite.config.ts)).

Scripts, from this directory:

| Command | What it does |
|---|---|
| `npm run dev` | starts the Vite dev server |
| `npm run build` | type-checks with `tsc -b` and writes the production build to `dist/` |
| `npm run lint` | runs eslint |
| `npm run preview` | serves the production build locally |

The backend serves `dist/` itself when it exists, so the UI and the API share one address. Running both together and packaging the build are covered in [`DEVELOPMENT.md`](../DEVELOPMENT.md); the code map is in [`ARCHITECTURE.md`](../ARCHITECTURE.md).
