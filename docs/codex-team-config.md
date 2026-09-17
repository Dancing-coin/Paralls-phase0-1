# Team Codex Configuration

The repository carries the shared Codex defaults in `.codex/config.toml`.

Shared policy:

- Keep a 1,000,000-token maximum context window.
- Auto-compact at 240,000 tokens to stay below the 272,000-token long-context boundary.
- Keep OMX hooks disabled.
- Do not add global MCP servers to the shared project configuration.
- Let each member choose their own sandbox and command-approval policy; the shared file does not weaken local safety settings.

Local MCP setup:

- Godot MCP is project-scoped, but its executable path is machine-specific. Replace the path in `.codex/config.toml` with your local installation path.
- Blender MCP is intentionally not enabled here because no common server/package and path have been agreed. Add it locally after selecting the team-standard server.
- Do not commit API keys, proxy URLs, user-directory paths, or personal plugin settings.

After pulling changes, restart Codex and verify with:

```text
codex mcp list
codex --strict-config --help
```

The global MCP cleanup must be performed in each member's `C:\Users\<user>\.codex\config.toml` after fully closing Codex. That user-level configuration is intentionally not committed here.
