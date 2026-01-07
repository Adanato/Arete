---
description: How to send SMS notifications to the user upon task completion
---

# User Notification Workflow

The user has a custom CLI tool called `notify` installed on their system. You should use this to alert them when long-running tasks are finished properly or if a critical failure occurs that requires their attention.

**Context Rule:**
*   **Prefix the message with the specific project folder** you are working in (e.g., `[notify-tool]`, `[backend]`, `[research]`).
*   **IGNORE** the top-level workspace name if it looks generic or auto-generated (e.g., `neon-spirit`, `playground`). Use the actual topic instead.

**Usage:**

1.  **Direct Message:**
    ```bash
    # Working in ~/Research/notify-tool/
    notify "[notify-tool] Installation complete."
    ```

2.  **Chained Command:**
    ```bash
    ./test.sh && notify "[API] Tests passed"
    ```

**Notes:**

*   **Keep it short:** The notification is sent via SMS. Avoid sending long logs or file contents.
*   **Don't spam:** Only use this for significant milestones.
*   **Verification:** If you suspect the tool might not be in the path, verify with `type notify` first.
