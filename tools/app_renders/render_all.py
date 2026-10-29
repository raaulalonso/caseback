#!/usr/bin/env python3
"""Makes the phone renders of the website's "The app" section from the screenshots that capture.sh takes.

    python3 tools/app_renders/render_all.py --shots <dir with en/ and es/> [--only today,trends] [--width 1760]
                                            [--samples 128] [--out-dir web/public/app] [--blender <path>]

For each language and group of phones (render_phones.py, SCENES) it
  1. copies the screenshots it needs, with the pill cut-out drawn in (the simulator does not draw it),
  2. renders the group with Blender and writes <out-dir>/<lang>/<scene>.webp (a transparent background: the site is black),
  3. writes web/content/app-renders.ts with where each phone lands in the picture, which the captions line up with.
Needs Pillow and Blender 4.2 or later. The photographs are the app on invented data: nothing here comes from a disc.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
LANGS = ("en", "es")

# the screenshots each group uses (keep in step with SCENES in render_phones.py)
GROUPS = {
    "today": ["today_night", "today_sheet", "today_now"],
    "trends": ["trends_readiness", "trends_scrub"],
    "device": ["device_health", "device", "device_data"],
    "widgets": ["widgets_home_fresh", "widgets_home_day", "widgets_home_days"],
}


def with_pill(im: Image.Image) -> Image.Image:
    """The Dynamic Island look-alike: 124 x 36.7 pt, 11 pt from the top, on a 402 pt wide screen (3 px per pt)."""
    im = im.convert("RGB")
    w, _ = im.size
    k, strip = 4, 200
    pw, ph, top = 372, 110, 33
    mask = Image.new("L", (w * k, strip * k), 0)
    ImageDraw.Draw(mask).rounded_rectangle([((w - pw) // 2) * k, top * k, ((w + pw) // 2) * k, (top + ph) * k], radius=(ph // 2) * k, fill=255)
    mask = mask.resize((w, strip), Image.LANCZOS)
    band = im.crop((0, 0, w, strip))
    band.paste(Image.new("RGB", (w, strip), (0, 0, 0)), (0, 0), mask)
    im.paste(band, (0, 0))
    return im


def prepare(shots: Path, lang: str, names: list[str], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for n in names:
        with_pill(Image.open(shots / lang / f"{n}.png")).save(dest / f"{n}.png")


def crop_to_phones(png: Path, info: dict, pad: float = 0.025) -> tuple[Image.Image, dict]:
    """Trim the transparent margin (keeping `pad` of the width all round) and move the positions to the trimmed picture."""
    im = Image.open(png).convert("RGBA")
    w, h = im.size
    box = im.getchannel("A").point(lambda a: 255 if a > 6 else 0).getbbox()
    m = int(pad * w)
    l, t, r, b = max(box[0] - m, 0), max(box[1] - m, 0), min(box[2] + m, w), min(box[3] + m, h)
    cw, ch = r - l, b - t
    out = {"width": cw, "height": ch, "phones": []}
    for p in info["phones"]:
        out["phones"].append({"shot": p["shot"], "centre": [(p["centre"][0] * w - l) / cw, (p["centre"][1] * h - t) / ch],
                              "top": [(p["top"][0] * w - l) / cw, (p["top"][1] * h - t) / ch],
                              "bottom": [(p["bottom"][0] * w - l) / cw, (p["bottom"][1] * h - t) / ch]})
    return im.crop((l, t, r, b)), out


def to_webp(im: Image.Image, webp: Path) -> None:
    webp.parent.mkdir(parents=True, exist_ok=True)
    im.save(webp, "WEBP", quality=88, method=6, alpha_quality=95)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", required=True, type=Path)
    ap.add_argument("--only", default=",".join(GROUPS))
    ap.add_argument("--width", default="2200")
    ap.add_argument("--samples", default="128")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "web" / "public" / "app")
    ap.add_argument("--ts", type=Path, default=ROOT / "web" / "content" / "app-renders.ts")
    ap.add_argument("--blender", default=BLENDER)
    a = ap.parse_args()

    positions: dict[str, dict] = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for lang in LANGS:
            for scene in a.only.split(","):
                tex = tmp / lang / scene
                prepare(a.shots, lang, GROUPS[scene], tex)
                png = tmp / f"{lang}_{scene}.png"
                cmd = [a.blender, "--background", "--python", str(Path(__file__).with_name("render_phones.py")), "--",
                       "--scene", scene, "--tex", str(tex), "--out", str(png), "--width", a.width, "--samples", a.samples]
                r = subprocess.run(cmd, capture_output=True, text=True)
                if not png.exists():
                    sys.exit(f"render failed for {lang}/{scene}:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
                im, info = crop_to_phones(png, json.loads(Path(str(png) + ".json").read_text()))
                to_webp(im, a.out_dir / lang / f"{scene}.webp")
                if lang == "en":  # the same in both languages: only the screens change
                    positions[scene] = info
                print(f"{lang}/{scene}: {(a.out_dir / lang / f'{scene}.webp').stat().st_size // 1024} KB")

    if a.ts:
        # keep the rows of the groups that were not rendered this time
        rows = {}
        if a.ts.exists():
            for line in a.ts.read_text().splitlines():
                m = re.match(r"^  (\w+): \{.*\},$", line)
                if m:
                    rows[m.group(1)] = line
        for scene, info in positions.items():
            shots = ", ".join(
                f'{{ shot: "{p["shot"]}", x: {p["centre"][0]:.4f}, top: {p["top"][1]:.4f}, bottom: {p["bottom"][1]:.4f} }}' for p in info["phones"])
            rows[scene] = f'  {scene}: {{ width: {info["width"]}, height: {info["height"]}, phones: [{shots}] }},'
        ordered = [rows[k] for k in GROUPS if k in rows]
        a.ts.write_text(
            "// Where each phone lands in the render, 0 to 1 from the top left. Written by tools/app_renders/render_all.py; do not edit.\n"
            "export const appRenders = {\n" + "\n".join(ordered) + "\n} as const;\n")
        print("wrote", a.ts)

if __name__ == "__main__":
    main()
