# Publishing Guide

## Part 1: PyPI (The Python Package)

### 1. Check if it exists
Go to: [https://pypi.org/project/obsianki/](https://pypi.org/project/obsianki/)
*If you see a 404, it is NOT published yet.*

### 2. How to Publish
You need to upload the artifacts we built in `dist/`.

1.  **Create Account**: [Register on PyPI](https://pypi.org/account/register/).
2.  **Get Token**: [Account Settings](https://pypi.org/manage/account/) -> API Tokens -> Add API Token (Scope: Entire Account).
3.  **Run Command**:
    ```bash
    uv publish
    ```
    *   **Username**: `__token__`
    *   **Password**: `pypi-AgEIpy...` (Your full token)

Once successful, `pip install obsianki` will work for everyone.

---

## Part 2: GitHub Actions (CI/CD)

The project uses GitHub Actions to automate testing and releases.

-   **Test Workflow**: Runs on every PR and push to `main`. It executes `pytest` (with Dockerized Anki) and `ruff`.
-   **Release Workflow**: Trigged when a new GitHub Release is created.
    -   Automatically builds the Python `dist/` artifacts.
    -   Automatically builds the Obsidian Plugin (`main.js`, `manifest.json`, `styles.css`).
    -   Attaches all binaries to the release.

---

## Part 3: Obsidian Community Plugins (The GUI)

To get your plugin into the official list inside Obsidian, you must submit a Pull Request to the Obsidian team.

### Prerequisites
1.  **GitHub Release**: You must have a published Release (e.g., `1.0.0`) with `main.js`, `manifest.json`, and `styles.css` attached as binaries.
2.  **Repo Structure**: `manifest.json` must be at the root of the repo (or root of released files). *Note: We release from `obsidian-plugin/`, but `main.js` etc. are attached directly to the release, so this is fine.*

### Submission Steps
1.  **Fork** the [obsidian-releases](https://github.com/obsidianmd/obsidian-releases) repository.
2.  **Add Entry**: Add your plugin to `community-plugins.json` in their repo.
    *   Format:
        ```json
        {
          "id": "obsianki",
          "name": "ObsiAnki",
          "author": "Adam Nguyen",
          "description": "Sync Obsidian vault to Anki using the o2a CLI.",
          "repo": "Adanato/obsidian_2_anki"
        }
        ```
3.  **Submit PR**: Open a Pull Request on their repo.

---

## Part 4: Versioning Strategy

We follow **Semantic Versioning (SemVer)**: `MAJOR.MINOR.PATCH`.

-   **MAJOR**: Breaking changes (e.g., changes to the Markdown card syntax).
-   **MINOR**: New features (e.g., support for a new Anki field type).
-   **PATCH**: Bug fixes and documentation updates.

Always update `version` in `pyproject.toml` and `manifest.json` simultaneously to keep the CLI and Plugin in sync.
