# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Growth Chat is an AI engineering learning project structured as a monorepo with three planned modules:

- `documentation/` — DocMD static site (implemented)
- `agent-api/` — Python agent API (TODO)
- `chat-ui/` — React frontend (TODO)

Node version: v24.15.0 (see `.nvmrc`; use `nvm use` before working in `documentation/`).

## Documentation Module

All commands run from `documentation/`:

```bash
npm start        # dev server with live reload
npx docmd build  # build static site to site/
```

DocMD config lives in `docmd.config.js`. Content is Markdown in `docs/`. The generated `site/` directory is git-ignored.

## Architecture Notes

The repository is intentionally sparse at this stage — only the documentation module exists. When `agent-api/` and `chat-ui/` are added:

- The Python agent API will go in `agent-api/` (expect `pyproject.toml` or `requirements.txt`)
- The React UI will go in `chat-ui/` (expect its own `package.json`)
- Each module is independent; there is no root-level build system yet
