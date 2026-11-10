# mcp-video-builder

Build-only repository for the MCP video studio. It is **public on purpose** (GitHub Actions minutes are unlimited for public repos) and therefore contains **no user media**:

- `.github/workflows/build.yml` checks out the *private* hub with a secret token, runs the requested command in the prebuilt runner image and publishes outputs as releases of the private hub.
- `.github/workflows/image.yml` builds the runner image (Chromium, FFmpeg, Hyperframes, Remotion, fonts, Python libs) whenever `runner/packages.json` or the scripts change.
- `runner/` holds the image definition and helper scripts. Managed by the MCP server; manual edits may be overwritten.

Build logs of this repo are public: the MCP never prints secrets or media names it was not asked to.
