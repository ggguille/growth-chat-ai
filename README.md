# Growth Chat

AI Chat project to learn about AI engineering

## Requirements

### NodeJS + NVM

This project uses **[NodeJS](https://nodejs.org/es)** for documentation, version managed by **[NVM](https://github.com/nvm-sh/nvm)**

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

## Agent API

> TODO: python agent api in `./agent-api`

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
