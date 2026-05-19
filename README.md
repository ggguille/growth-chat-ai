# Growth Chat

AI Chat project to learn about AI engineering

## Requirements

### NodeJS + NVM

This project uses **[NodeJS](https://nodejs.org/es)** for documentation, version managed by **[NVM](https://github.com/nvm-sh/nvm)**

### Python + uv

The backend uses **Python 3.14+**, managed via **[uv](https://docs.astral.sh/uv/)** as a workspace.

## Documentation

All documentation about project is in `./documentation` folder.

Based on **[docmd framework](https://docs.docmd.io/)**

### Commands

```bash
# Move to documentation directory
cd ./documentation

# Start project on local
npx docmd dev

# Build project
npx docmd build
```

## Backend

FastAPI backend in `./backend` — streaming `POST /chat` endpoint via SSE, with LangGraph orchestration, RAG retrieval, and lead handoff delivery.

### Commands

```bash
# Install all workspace dependencies (from project root)
uv sync

# Start dev server with hot reload
uv run --package backend uvicorn backend.main:app --reload --port 8000
```

See [`backend/README.md`](./backend/README.md) for environment variables and full API docs.

## Frontend

React + TypeScript chat widget scaffolded in `./frontend`, built as a `<growth-chat>` Web Component with Shadow DOM.

### Commands

```bash
# Move to frontend directory
cd ./frontend

# Start dev server with HMR
npm run dev

# Build self-contained IIFE bundle to dist/growth_chat.js
npm run build
```

### Embed on any page

```html
<script src="dist/growth_chat.js" defer></script>
<growth-chat api-url="https://api.example.com/chat"></growth-chat>
```

See [`frontend/README.md`](./frontend/README.md) for attributes and full UI docs.
