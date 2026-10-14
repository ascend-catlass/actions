# Build and maintain the documentation

[中文](../zh/maintaining.md) · [English](../en/maintaining.md)

The documentation uses ordinary Markdown: `docs/zh/` contains Chinese and `docs/en/` contains English, with one page per Action in each language. The files are also readable directly on GitHub.

## Local preview

Install documentation dependencies in a Python virtual environment if possible. From the repository root, run:

```text
python -m pip install -r requirements-docs.txt
python -m mkdocs serve
```

Open the local address shown in the terminal, usually `http://127.0.0.1:8000/`. Markdown changes refresh the preview automatically.

## Checks before pushing

```text
python scripts/check_docs.py
python -m mkdocs build --strict
git diff --check
```

The first check verifies bilingual coverage, input/output tables against Action interfaces and valid example parameters. The second checks navigation and links and generates static files in `site/`. The build directory is not committed.

`docs-build.yml` runs the same checks after documentation-related changes on `main` or on manual dispatch. It saves the site as the `automation-docs-site` artifact for seven days. Download and extract it into a `site/` directory, then preview with a static HTTP server, for example `python -m http.server --directory site 8000`. The files are not automatically published to GitHub Pages.

## Add or update an Action guide

1. Read `.github/actions/<name>/action.yml` and its actual script to confirm behavior.
2. Update both `docs/zh/actions/<name>.md` and `docs/en/actions/<name>.md`. Explain purpose, use cases, prerequisites, steps, example, inputs, outputs and limits.
3. Match interface names, required flags and defaults to `action.yml`. Explain operation-specific requirements in the narrative.
4. Add links to both overview pages, `mkdocs.yml` navigation and the Action README.
5. Run the checks, review the diff, then commit and push. Runtime changes also require the appropriate behavior tests.

Use secret references rather than real credentials. Distinguish implemented steps from outcomes guaranteed by another system: posting an assignment command does not by itself verify that the platform changed the assignee.

## Framework and sources

The site uses MkDocs 1.6.1 with its built-in theme and search, without extra theme or translation plugins. Chinese and English have separate navigation sections, and each page links to its counterpart. Historical design notes remain in `docs/plans/` outside the user guide.

Configuration and strict builds follow the [MkDocs configuration guide](https://www.mkdocs.org/user-guide/configuration/). See the [MkDocs user guide](https://www.mkdocs.org/user-guide/) for local preview and Markdown authoring.
