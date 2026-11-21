# Codex Usage

A small local dashboard for the same Codex quota percentage shown by the Codex Stats VS Code extension.

## Start it

Double-click `Start Dashboard.command`. It opens `http://127.0.0.1:8765` in your browser. Keep the Terminal window open while viewing the dashboard; press **Control+C** there to stop it.

The page refreshes every five minutes, with a **Refresh now** button for an immediate update. It displays the usage percentage and reset countdown returned by Codex. It does not estimate tokens per prompt.

## Local use and privacy

- The server listens only on `127.0.0.1`; it is not hosted or reachable from other computers.
- It reads `~/.codex/auth.json` (or `$CODEX_HOME/auth.json`) locally and sends an authenticated, read-only usage request to `chatgpt.com/backend-api/wham/usage`.
- Authentication tokens stay in the local server process and are never sent to the browser or written to logs or files.
- The repository contains the dashboard source only. It does not contain credentials, usage readings, or a hosted copy of the dashboard.
- No third-party libraries or external scripts are loaded.
- If Codex reports a sign-in error, run `codex login` in a terminal and refresh the page.

Python 3 is required. No packages need to be installed.
