# growth-chat-frontend

React + TypeScript + Vite chat widget, delivered as a `<growth-chat>` Custom Element with Shadow DOM.

## Development

```bash
npm install
npm run dev      # HMR dev server at http://localhost:5173
```

Open `http://localhost:5173` — the `<growth-chat>` element renders inside its Shadow DOM.

## Build

```bash
npm run build    # type-check + IIFE bundle → dist/growth_chat.js
```

## Embed

Two lines of HTML, no framework required on the host page:

```html
<script src="https://cdn.example.com/growth_chat.js" defer></script>
<growth-chat api-url="https://api.example.com/chat"></growth-chat>
```

## Structure

```
src/
├── main.ts                    # registers <growth-chat> custom element
├── GrowthChat.ts              # Web Component: Shadow DOM + React lifecycle
└── components/
    └── ChatWidget.tsx         # React component (placeholder — Phase 2 target)
```

## Attributes

| Attribute | Required | Description |
|-----------|----------|-------------|
| `api-url` | yes | Backend streaming endpoint URL |
