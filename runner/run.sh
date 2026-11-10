#!/usr/bin/env bash
# MCP video builder (v2): runs $BUILD_CMD inside hub/projects/$BUILD_PROJECT, streams the log to $BUILD_HOOK every 2 s,
# publishes files matching $BUILD_ARTIFACTS as a release of the (private) hub repo, then reports the result.
set -u
[ -f /opt/mcp/env.sh ] && . /opt/mcp/env.sh
export HUB_REPO="${HUB_REPO:?HUB_REPO missing}" GH_TOKEN="${HUB_TOKEN:-${GH_TOKEN:-}}" GITHUB_WORKSPACE="${GITHUB_WORKSPACE:-$PWD}"
export HUB_DIR="$GITHUB_WORKSPACE/hub" PATH="/opt/mcp/bin:$PATH"
cd "$HUB_DIR/projects/$BUILD_PROJECT" 2>/dev/null || { echo "project folder projects/$BUILD_PROJECT not found in the hub"; exit 2; }
LOG="$(mktemp)"; : > "$LOG"
have_hook() { [ -n "${BUILD_HOOK:-}" ] && [ -n "${BUILD_KEY:-}" ]; }
post() { # post <path+query> <file> [content-type]
  curl -fsS -m 15 -X POST -H "Authorization: Bearer $BUILD_KEY" -H "Content-Type: ${3:-text/plain}" \
       --data-binary "@$2" "$BUILD_HOOK/hooks/build/$BUILD_ID/$1" >/dev/null 2>&1 && touch "$LOG.ok"
}
ship() { # background: send new log bytes every 2 s; stops once the build is done and everything is delivered
  local off=0 size n fails=0
  while true; do
    sleep 2; size=$(stat -c %s "$LOG")
    if [ "$size" -gt "$off" ]; then
      tail -c +"$((off + 1))" "$LOG" | head -c 200000 > "$LOG.chunk"; n=$(stat -c %s "$LOG.chunk")
      if post "log?off=$off" "$LOG.chunk"; then off=$((off + n)); fails=0; else fails=$((fails + 1)); fi
    elif [ -e "$LOG.done" ]; then break; fi
    if [ -e "$LOG.done" ] && [ "$fails" -ge 3 ]; then break; fi
  done
}
have_hook && { ship & SHIP=$!; }

{
  echo "== MCP build $BUILD_ID | project $BUILD_PROJECT | $(date -u +%FT%TZ)"
  echo "== runner: $(. /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-linux}") | $(nproc) CPU | $(free -m 2>/dev/null | awk '/Mem:/{print $2}') MB RAM | hyperframes $(hyperframes --version 2>/dev/null | head -1)"
  echo "== command:"; echo "$BUILD_CMD" | sed 's/^/   /'
} | tee -a "$LOG"

start=$(date +%s)
export NO_COLOR=1 TERM=dumb CI=true
if [ "${BUILD_PREP:-1}" != "0" ]; then mcp-prep . 2>&1 | tee -a "$LOG"; fi
# the command is written to a file first: no quoting problems, and `bash -e` stops at the first failing line
printf '%s\n' "$BUILD_CMD" > "$LOG.cmd.sh"
if command -v script >/dev/null 2>&1; then   # a pty makes tools flush line by line, so the stream is truly live
  script -qefc "bash -eo pipefail $LOG.cmd.sh" /dev/null 2>&1 | tr -d '\r' | tee -a "$LOG"
else
  bash -eo pipefail "$LOG.cmd.sh" 2>&1 | tee -a "$LOG"
fi
rc=${PIPESTATUS[0]}
dur=$(( $(date +%s) - start ))
echo "== exit code $rc after ${dur}s" | tee -a "$LOG"

# ---- publish artifacts as a release of the hub (no artifact-storage quota, files up to 2 GiB) ----
assets=(); declare -A seen
if [ -n "${BUILD_ARTIFACTS:-}" ]; then
  shopt -s globstar nullglob
  while IFS= read -r pat; do
    pat="${pat%$'\r'}"; [ -z "${pat// }" ] && continue
    for f in $pat; do
      [ -f "$f" ] || continue
      b=$(basename "$f"); if [ -n "${seen[$b]:-}" ]; then echo "== skipped duplicate name: $f" | tee -a "$LOG"; continue; fi
      seen[$b]=1; assets+=("$f")
    done
  done <<< "$BUILD_ARTIFACTS"
fi
tag=""
if [ "${#assets[@]}" -gt 0 ]; then
  tag="build-$BUILD_ID"
  echo "== publishing ${#assets[@]} file(s) as release $tag (private hub)" | tee -a "$LOG"
  if gh release create "$tag" "${assets[@]}" -R "$HUB_REPO" --title "Build $BUILD_ID ($BUILD_PROJECT)" --notes "exit=$rc" > "$LOG.gh" 2>&1; then
    sed 's#https://github.com/[^ ]*#<release url hidden>#' "$LOG.gh" | tee -a "$LOG"
  else sed 's#https://github.com/[^ ]*#<url hidden>#' "$LOG.gh" | tee -a "$LOG"; echo "== release upload failed" | tee -a "$LOG"; tag=""; fi
elif [ -n "${BUILD_ARTIFACTS:-}" ]; then echo "== no files matched the artifact patterns" | tee -a "$LOG"; fi

# ---- flush the stream, then report ----
touch "$LOG.done"
if [ -n "${SHIP:-}" ]; then
  for _ in $(seq 1 30); do kill -0 "$SHIP" 2>/dev/null || break; sleep 2; done
  kill "$SHIP" 2>/dev/null
fi
if have_hook; then
  printf '{"exit":%d,"seconds":%d,"tag":"%s","files":%d}' "$rc" "$dur" "$tag" "${#assets[@]}" > "$LOG.json"
  tries=4; [ -e "$LOG.ok" ] || tries=1
  for _ in $(seq 1 "$tries"); do post done "$LOG.json" application/json && break; sleep 3; done
fi
exit "$rc"
