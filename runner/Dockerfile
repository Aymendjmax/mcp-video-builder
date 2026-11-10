# MCP video runner image: everything the GitHub Actions render jobs need, installed once.
# Rebuilt automatically (image.yml) whenever packages.json or this file changes. Edit packages.json via the MCP `libs` tool.
FROM node:22-trixie
ENV DEBIAN_FRONTEND=noninteractive PIP_BREAK_SYSTEM_PACKAGES=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    NPM_CONFIG_UPDATE_NOTIFIER=false HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_SKIP_SKILLS=1 HYPERFRAMES_NO_UPDATE_CHECK=1 \
    NODE_PATH=/opt/mcp/node_modules HYPERFRAMES_CACHE_DIR=/opt/mcp/cache PATH=/opt/mcp/bin:$PATH
WORKDIR /opt/mcp
COPY packages.json /opt/mcp/packages.json
COPY bin /opt/mcp/bin
COPY qa.py sheet.py /opt/mcp/

# 1) apt (bulk first; if one package is missing, retry one by one and skip only that one)
RUN apt-get update \
 && PK="$(node -p "require('/opt/mcp/packages.json').apt.join(' ')")" \
 && (apt-get install -y --no-install-recommends $PK || (for p in $PK; do apt-get install -y --no-install-recommends "$p" || echo "SKIPPED apt:$p"; done)) \
 && rm -rf /var/lib/apt/lists/*

# 2) npm: CLIs globally, libraries in /opt/mcp/node_modules (NODE_PATH)
RUN node -e "const p=require('/opt/mcp/packages.json').npm;console.log(Object.entries(p).map(([k,v])=>k+'@'+v).join(' '))" > /tmp/npm.txt \
 && npm init -y >/dev/null && npm install --save-exact --no-audit --no-fund $(cat /tmp/npm.txt) \
 && npm install -g --no-audit --no-fund hyperframes@$(node -p "require('/opt/mcp/packages.json').npm.hyperframes") \
 && rm /tmp/npm.txt

# 3) pip (system-wide, pinned)
RUN pip3 install --no-cache-dir $(node -p "Object.entries(require('/opt/mcp/packages.json').pip).map(([k,v])=>k+'=='+v).join(' ')")

# 4) fonts: fontsource woff2 files + a ready @font-face sheet (no Google Fonts at render time; Arabic included)
RUN mkdir -p /opt/mcp/fonts /tmp/fs && cd /tmp/fs && npm init -y >/dev/null \
 && npm install --no-audit --no-fund $(node -p "Object.entries(require('/opt/mcp/packages.json').fonts).map(([k,v])=>k+'@'+v).join(' ')") \
 && node /opt/mcp/bin/build-fonts.mjs /tmp/fs/node_modules /opt/mcp/fonts && rm -rf /tmp/fs

# 5) vendor browser libs that compositions load as local <script> files (copied into projects by mcp-prep)
RUN mkdir -p /opt/mcp/vendor && cd /opt/mcp/node_modules \
 && cp gsap/dist/gsap.min.js gsap/dist/ScrollTrigger.min.js /opt/mcp/vendor/ 2>/dev/null || true \
 && cp three/build/three.module.min.js /opt/mcp/vendor/ 2>/dev/null || cp three/build/three.module.js /opt/mcp/vendor/ || true \
 && (cp animejs/dist/bundles/anime.umd.min.js /opt/mcp/vendor/anime.min.js 2>/dev/null || true) \
 && (cp lottie-web/build/player/lottie.min.js /opt/mcp/vendor/ 2>/dev/null || true) \
 && (cp d3/dist/d3.min.js /opt/mcp/vendor/ 2>/dev/null || true) && ls -la /opt/mcp/vendor

# 6) our scripts + a headless Chrome for Hyperframes; the resolved paths are recorded in /opt/mcp/env.sh
RUN chmod +x /opt/mcp/bin/* \
 && (hyperframes browser ensure || echo "browser ensure failed: falling back to system chromium") \
 && { echo "export NODE_PATH=/opt/mcp/node_modules HYPERFRAMES_CACHE_DIR=/opt/mcp/cache HYPERFRAMES_NO_TELEMETRY=1 HYPERFRAMES_SKIP_SKILLS=1 HYPERFRAMES_NO_UPDATE_CHECK=1"; \
      H="$(find /opt/mcp/cache /root/.cache -type f -name chrome-headless-shell 2>/dev/null | head -1)"; \
      [ -n "$H" ] && echo "export PRODUCER_HEADLESS_SHELL_PATH=$H"; \
      [ -x /usr/bin/chromium ] && echo "export PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium"; } > /opt/mcp/env.sh \
 && cat /opt/mcp/env.sh && chmod -R a+rX /opt/mcp
LABEL org.opencontainers.image.source="https://github.com/Aymendjmax/mcp-video-builder"
