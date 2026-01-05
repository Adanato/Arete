# Publishing `arete` to PyPI

Since your `release.yml` is already configured for **Trusted Publishing** (OIDConnect), you do not need hardcoded API tokens. You just need to tell PyPI to trust your GitHub repository.

## Prerequisites
1.  A **[PyPI Account](https://pypi.org/account/register/)**.
2.  Your project on GitHub: `Adanato/obsidian_2_anki`.

## Step 1: Configure PyPI (One-Time Setup)

1.  Log in to **[PyPI.org](https://pypi.org)**.
2.  Go to **[Publishing](https://pypi.org/manage/account/publishing/)**.
3.  Scroll to **"Add a new pending publisher"**.
4.  Fill in the details:
    *   **PyPI Project Name**: `arete`
    *   **Owner**: `Adanato` (your GitHub username)
    *   **Repository name**: `obsidian_2_anki`
    *   **Workflow name**: `release.yml`
    *   **Environment name**: Leave blank (unless you configured one in GitHub).
5.  Click **Add**.

> **Note**: If the name `arete` is taken, PyPI will warn you here. If so, we might need to scope it (e.g., `arete-sync` or `adanato-arete`).

## Step 2: Trigger the Release

Once PyPI is configured, you simply push a tag.

1.  **Tag the release**:
    ```bash
    git tag v1.0.0
    ```

2.  **Push to GitHub**:
    ```bash
    git push origin v1.0.0
    ```

## Step 3: Verify

1.  Go to your **GitHub Actions** tab. You should see a workflow named "Release to PyPI" running.
2.  Once green, go to **PyPI.org/project/arete** to see your package!
3.  Users can now install it via `pip install arete` or `uv tool install arete`.
