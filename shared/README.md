# shared

Internal Python packages shared across workspace members. Each subdirectory is a [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) member with its own `pyproject.toml`.

| Package | Import as | Used by |
| --- | --- | --- |
| [`knowledge_base`](knowledge_base/) | `from knowledge_base import ...` | `backend`, `data/ingestion` |

## Adding a new shared package

1. Create the directory with the standard src layout:

```
shared/<name>/
├── pyproject.toml
├── .gitignore
└── src/
    └── <name>/
        ├── __init__.py
        └── py.typed
```

2. Add it to the workspace members in the root `pyproject.toml`:

```toml
[tool.uv.workspace]
members = ["shared/<name>", ...]
```

3. Declare it as a dependency in any workspace member that needs it:

```toml
# member/pyproject.toml
[project]
dependencies = ["<name>"]

[tool.uv.sources]
<name> = { workspace = true }
```

4. Run `uv sync` from the project root to update the lock file.
