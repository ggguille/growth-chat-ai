---
description: "Operations runbook for the Growth Chat documentation site — deploy pipeline, local preview, adding content, and configuration."
---

# Documentation Site

The documentation site is a static site built with DocMD and hosted on GitHub Pages. It deploys automatically when content in the `documentation/` directory is pushed to `main`.

---

## Platform

| Parameter | Value |
| --- | --- |
| Platform | GitHub Pages |
| Domain | Custom domain (configured via CNAME in the deploy workflow) |
| Build tool | DocMD (`@docmd/core`) |
| Node version | Pinned in `.nvmrc` — use `nvm use` before running commands locally |
| Source | `documentation/docs/` |
| Build output | `documentation/site/` (git-ignored) |

---

## Deploy Pipeline

**Trigger:** Automatic on push to `main` touching any file under `documentation/**`.

**Pipeline steps:**

```text
1. Install Node (version from .nvmrc)
2. npm ci — install dependencies
3. npx @docmd/core build — generate static site to documentation/site/
4. Write CNAME file (custom domain)
5. Upload site/ as a GitHub Pages artifact
6. Deploy to GitHub Pages
```

No secrets are required. The workflow uses the `github-pages` GitHub Actions environment with `pages: write` and `id-token: write` permissions.

**To trigger manually:** `workflow_dispatch` on `deploy-documentation.yml` from the GitHub Actions UI.

---

## Local Preview

```bash
# From the repository root
cd documentation
nvm use              # switch to the pinned Node version
npm install          # first time only
npm start            # dev server with live reload — opens at localhost:3000 (or similar)
```

To check the production build locally:

```bash
npx docmd build      # output to documentation/site/
```

---

## Adding or Updating Content

### Editing an existing page

1. Find the Markdown file in `documentation/docs/` that corresponds to the page.
2. Edit the file.
3. Push to `main` — the site deploys automatically.

### Adding a new page

1. Create a new `.md` file in the appropriate subdirectory under `documentation/docs/`.
2. Add a YAML frontmatter block at the top:

   ```yaml
   ---
   title: "Page Title"
   description: "One-sentence description for SEO and search."
   ---
   ```

3. Add the page to the `navigation` array in `documentation/docmd.config.js`:

   ```js
   { title: 'My New Page', path: '/my-section/my-new-page' }
   ```

   The `path` must match the file path relative to `docs/`, without the `.md` extension.
4. Push to `main`.

### Adding a new section

Add a group entry with `children` to the `navigation` array in `docmd.config.js`:

```js
{
  title: 'New Section',
  path: '/new-section',
  icon: 'file-text',
  children: [
    { title: 'Overview', path: '/new-section/' },
    { title: 'Child Page', path: '/new-section/child-page' },
  ]
}
```

The `icon` value is a Lucide icon name. See the DocMD documentation for supported icons.

---

## Configuration

`documentation/docmd.config.js` controls the entire site:

| Setting | What it controls |
| --- | --- |
| `title` | Site title in the header and browser tab |
| `url` | Canonical URL — used for sitemap and SEO |
| `navigation` | Sidebar structure and all page paths |
| `theme` | Visual theme and appearance mode |
| `layout` | Sidebar, header, footer, options menu |
| `plugins.analytics` | Google Analytics measurement ID |
| `plugins.seo` | Default OG description and Twitter card settings |

Changes to `docmd.config.js` take effect on the next deploy.
