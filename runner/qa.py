#!/usr/bin/env python3
"""QA for a rendered video. Usage: qa.py VIDEO [--html index.html] [--out qa.json] [--grid grid.jpg] [--max 48]
Checks: duration/size/fps vs the composition's data-* attributes, black / blank / frozen frames, big flat areas stuck on the background colour while the
scene is stable (clipped or half-revealed scenes), content touching the frame edge, abrupt jumps. Heuristics: they flag candidates; look at the grid."""
import argparse, json, os, re, subprocess, sys, tempfile
import numpy as np

def run(a): return subprocess.run(a, capture_output=True, text=True)

def probe(v):
    j = json.loads(run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", v]).stdout or "{}")
    vs = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), None)
    if not vs: raise SystemExit("no video stream")
    n, d = (vs.get("r_frame_rate") or "30/1").split("/"); fps = float(n) / float(d or 1)
    return dict(w=int(vs["width"]), h=int(vs["height"]), fps=round(fps, 3), duration=float(j["format"].get("duration") or vs.get("duration") or 0),
                audio=any(s.get("codec_type") == "audio" for s in j["streams"]), codec=vs.get("codec_name"), size=int(j["format"].get("size", 0)))

def expected(html):
    if not html or not os.path.exists(html): return {}
    t = open(html, encoding="utf8", errors="ignore").read()
    m = re.search(r"<[^>]*data-composition-id=[^>]*>", t)
    if not m: return {}
    g = lambda k: (re.search(k + r'="([\d.]+)"', m.group(0)) or [None, None])[1]
    return {k: float(v) for k, v in dict(duration=g("data-duration"), w=g("data-width"), h=g("data-height"), fps=g("data-fps")).items() if v}

def css_ground(html):
    if not html or not os.path.exists(html): return None
    t = open(html, encoding="utf8", errors="ignore").read()
    m = re.search(r"--ground\s*:\s*#([0-9a-fA-F]{3,8})", t) or re.search(r"(?:html|body)[^{{]*\{{[^}}]*background(?:-color)?\s*:\s*#([0-9a-fA-F]{{3,8}})".format(), t)
    if not m: return None
    h = m.group(1)
    if len(h) in (3, 4): h = "".join(c * 2 for c in h[:3])
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)])

def ranges(times, step):
    out, i = [], 0
    while i < len(times):
        j = i
        while j + 1 < len(times) and times[j + 1] - times[j] <= step * 1.01: j += 1
        out.append(f"{times[i]:g}s" if i == j else f"{times[i]:g}-{times[j]:g}s"); i = j + 1
    return ", ".join(out)

def sample(v, dur, maxn, tw=320):
    step = max(0.25, dur / maxn); fps = 1.0 / step
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", v, "-vf", f"fps={fps:.5f},scale={tw}:-2", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    return p.stdout, step

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("video"); ap.add_argument("--html"); ap.add_argument("--out", default="qa.json"); ap.add_argument("--grid"); ap.add_argument("--max", type=int, default=48); ap.add_argument("--ground", help="background colour hex (default: read from the composition CSS, else guessed from the corners)")
    a = ap.parse_args(); info = probe(a.video); exp = expected(a.html); err, warn = [], []
    for k, tol in (("w", 0), ("h", 0), ("fps", 0.6), ("duration", 0.35)):
        if k in exp and abs(exp[k] - info[k]) > tol: err.append(f"{k}: composition says {exp[k]:g}, video has {info[k]:g}")
    raw, step = sample(a.video, info["duration"], a.max); tw = 320; th = int(round(info["h"] * tw / info["w"] / 2) * 2); fs = tw * th * 3
    n = len(raw) // fs
    if n < 2: err.append("could not sample frames"); out = dict(ok=False, errors=err, warnings=warn, info=info); json.dump(out, open(a.out, "w"), indent=1); print(json.dumps(out)); sys.exit(1)
    F = np.frombuffer(raw[: n * fs], np.uint8).reshape(n, th, tw, 3).astype(np.int16)
    luma = F.mean(axis=3); mean = luma.mean(axis=(1, 2)); std = luma.std(axis=(1, 2))
    ts = [round(i * step, 2) for i in range(n)]
    # ground colour = most common colour in the 4 corner patches over all frames
    c = 8; corners = np.concatenate([F[:, :c, :c].reshape(n, -1, 3), F[:, :c, -c:].reshape(n, -1, 3), F[:, -c:, :c].reshape(n, -1, 3), F[:, -c:, -c:].reshape(n, -1, 3)], axis=1).reshape(-1, 3)
    q = (corners // 8).astype(np.int32); keys = q[:, 0] * 1024 + q[:, 1] * 32 + q[:, 2]; mode = np.bincount(keys).argmax(); guess = np.array([mode // 1024, (mode // 32) % 32, mode % 32]) * 8 + 4
    ground = guess; src = "corners-guess"
    if a.ground: h = a.ground.lstrip("#"); ground = np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)]); src = "--ground"
    elif css_ground(a.html) is not None: ground = css_ground(a.html); src = "composition css"
    near = (np.abs(F - ground).max(axis=3) < 22)  # n,h,w bool : pixel ~ ground colour
    cover = 1 - near.mean(axis=(1, 2))
    diff = np.r_[0, np.abs(luma[1:] - luma[:-1]).mean(axis=(1, 2))]
    flagged = []; kinds = {}
    def hit(kind, i): kinds.setdefault(kind, []).append(i); flagged.append(i)
    for i in range(n):
        if mean[i] < 6 and std[i] < 4: hit("black frame", i)
        elif mean[i] > 250 and std[i] < 3: hit("pure white frame", i)
    if diff[1:].max() < 0.15 and n > 4: warn.append("video is almost completely static (no frame changes)")
    stable = [i for i in range(1, n - 1) if diff[i] < 1.2 and diff[i + 1] < 1.2]
    if len(stable) >= 4:
        med = float(np.median(cover[stable]))
        for i in stable:
            if med > 0.25 and cover[i] < 0.62 * med:
                blk = max(near[i, : th // 2, : tw // 2].mean(), near[i, : th // 2, tw // 2 :].mean(), near[i, th // 2 :, : tw // 2].mean(), near[i, th // 2 :, tw // 2 :].mean())
                if blk > 0.5: hit("scene NOT covering the frame (a whole quadrant stays background colour; content %d%% vs ~%d%% typical): clipped or half-revealed scene?" % (cover[i] * 100, med * 100), i)
    ring = 3
    for i in stable:
        e = np.concatenate([~near[i, :ring, :].ravel(), ~near[i, -ring:, :].ravel(), ~near[i, :, :ring].ravel(), ~near[i, :, -ring:].ravel()]).mean()
        if e > 0.5 and e > cover[i] * 1.3 and cover[i] < 0.5: hit("content cut by the frame edge (%d%% of the border is non-background)" % (e * 100), i)
    for kind, idx in kinds.items(): warn.append(f"{ranges([ts[i] for i in idx], step)}: {kind}")
    cuts = [ts[i] for i in range(1, n) if diff[i] > 18]
    seen = set(); w2 = []
    for w in warn:
        if w not in seen: seen.add(w); w2.append(w)
    warn = w2[:40]
    out = dict(ok=not err, errors=err, warnings=warn, info={**info, "sampled": n, "step_s": round(step, 2), "ground_rgb": ground.tolist(), "median_content": round(float(np.median(cover)), 3), "ground_source": src, "hard_cuts_or_fast_transitions_at": cuts[:12]}, flagged_times=sorted({ts[i] for i in flagged}))
    json.dump(out, open(a.out, "w"), indent=1)
    if a.grid:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet
        pick = sorted(set(flagged[:8]) | set(np.linspace(0, n - 1, min(n, 12)).astype(int).tolist())); d = tempfile.mkdtemp(); items = []
        from PIL import Image
        for i in pick:
            pth = os.path.join(d, f"{i}.jpg"); Image.fromarray(F[i].astype(np.uint8)).save(pth, quality=85); items.append(f"{pth}|{ts[i]}s" + (" !" if i in flagged else ""))
        sheet.make(a.grid, 4, 320, items)
    print(json.dumps(out, indent=1)); sys.exit(0 if out["ok"] else 1)

if __name__ == "__main__": main()
