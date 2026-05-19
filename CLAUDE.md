# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Growth Chat is an AI engineering learning project structured as a monorepo with three planned modules:

- `documentation/` — DocMD static site (implemented)
- `agent-api/` — Python agent API (TODO)
- `frontend/` — React + TypeScript + Vite chat widget (scaffolded)

Node version: v24.15.0 (see `.nvmrc`; use `nvm use` before working in `documentation/`).

## Documentation Module

All commands run from `documentation/`:

```bash
npm start        # dev server with live reload
npx docmd build  # build static site to site/
```

DocMD config lives in `docmd.config.js`. Content is Markdown in `docs/`. The generated `site/` directory is git-ignored.

## Frontend Module

All commands run from `frontend/`:

```bash
npm run dev    # dev server with HMR at localhost:5173
npm run build  # type-check + IIFE bundle to dist/chat.js
```

The widget is a `<growth-chat>` Custom Element (Web Component) that mounts React inside a Shadow DOM. `src/GrowthChat.ts` is the wrapper; `src/components/ChatWidget.tsx` is the React component. `vite build` produces a single self-contained `dist/chat.js` IIFE for CDN distribution.

## Architecture Notes

The repository is intentionally sparse at this stage. When `agent-api/` is added:

- The Python agent API will go in `agent-api/` (expect `pyproject.toml` or `requirements.txt`)
- Each module is independent; there is no root-level build system yet
