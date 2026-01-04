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

## Part 2: Obsidian Community Plugins (The GUI)

To get your plugin into the official list inside Obsidian, you must submit a Pull Request to the Obsidian team.

### Prerequisites
1.  **GitHub Release**: You must have a published Release (e.g., `1.0.0`) with `main.js`, `manifest.json`, and `styles.css` attached as binaries.
2.  **Repo Structure**: `manifest.json` must be at the root of the repo (or root of released files). *Note: We release from `obsidian-plugin/`, but `main.js` etc. are attached directly to the release, so this is fine.*

### Submission Steps
1.  **Fork** the [obsidian-releases](https://github.com/obsidianmd/obsidian-releases) repository.
2.  **Add File**: Create a new file `community-plugins.json` entry in your fork.
    *   Actually, you add your plugin to the end of the `community-plugins.json` file in their repo.
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
4.  **Review**: The Obsidian team will review your code (security, guidelines).
    *   *Tip: They are strict about `eval()`, `innerHTML` usage, and network calls.*
5.  **Approval**: Once merged, it appears in the Community Plugins list for everyone!

### Detailed Policy
Read the [Developer Policies](https://docs.obsidian.md/Plugins/Releasing/Plugin+guidelines) to ensure you pass review.
