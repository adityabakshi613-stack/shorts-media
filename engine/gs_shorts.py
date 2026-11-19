#!/usr/bin/env python3
"""Gaming Sane short engine (footage style, separate from Wealth Extreme).
Usage: python3 gs_shorts.py spec.json OUTDIR
spec = {"id", "sources": {"name": "<url or path to mp4/jpg>"},
        "beats": [{"say", "clip": {"src": "name", "t": 12.0} | {"img": "<url|commons:File>"}, "num": "2017"(opt), "keys": [..], "glitch": true(opt)}],
        "outro_say": "Follow Gaming Sane for daily gaming news.", "credit": "Footage: Rockstar Games"(opt)}
Look: real gameplay/trailer clip in a framed card over a blurred copy of itself, big red/white numbers,
single-word UPPERCASE captions (key words in a red box), RGB-glitch cuts, edge-tts voice, GS logo outro.
"""
import os, sys, json, re, asyncio, hashlib, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import shorts as S

W, H, FPS = 1080, 1920, 30
RED = "#E3262F"; FONT = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
CARD_W, CARD_H, CARD_Y = 1000, 562, 500
GS = dict(S.THEMES["gs"]); GS.update(plate="logo_gs.png", brand=["Gaming", "Sane"], bgm=[614, 584, 22, 2])

def tts_words(text, out, voice="en-US-AndrewMultilingualNeural", rate="+8%"):
    import certifi
    if os.path.exists("/root/.ccr/ca-bundle.crt"): certifi.where = lambda: "/root/.ccr/ca-bundle.crt"
    import edge_tts
    async def go():
        c = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
        ws = []
        with open(out, "wb") as f:
            async for ch in c.stream():
                if ch["type"] == "audio": f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    s = ch["offset"] / 1e7; ws.append(dict(w=ch["text"], s=s, e=s + ch["duration"] / 1e7))
        return ws
    import time
    for k in range(5):
        try:
            ws = asyncio.run(go())
            if os.path.getsize(out) > 1000: return ws
        except Exception as e:
            err = e
        time.sleep(3 * (k + 1))
    raise RuntimeError(f"edge-tts failed: {err}")

def dur(p): return float(S.sh(f"ffprobe -v error -show_entries format=duration -of csv=p=0 '{p}'"))

def round_mask(path, w, h, r=36):
    m = Image.new("L", (w * 2, h * 2), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w * 2 - 1, h * 2 - 1], r * 2, fill=255)
    m.resize((w, h), Image.LANCZOS).save(path); return path

def num_png(text, path):
    """Big extruded red/white number like the channel's '2017' / '9' callouts."""
    f = ImageFont.truetype(FONT, 230 if len(text) <= 4 else 170)
    im = Image.new("RGBA", (W, 330), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    tw = d.textlength(text, font=f); x = (W - tw) / 2; y = 20
    for k in range(14, 0, -1): d.text((x + k * 0.6, y + k), text, font=f, fill=(90, 8, 14, 255))
    d.text((x, y), text, font=f, fill=(255, 255, 255, 255), stroke_width=10, stroke_fill=(214, 34, 44, 255))
    g = Image.new("RGBA", im.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(g)
    gd.text((x, y), text, font=f, fill=(255, 40, 60, 140)); im = Image.alpha_composite(g.filter(ImageFilter.GaussianBlur(18)), im)
    im.save(path); return path

def segment(i, b, d, sources, wd, credits, mask):
    out = os.path.join(wd, f"seg_{i:02d}.mp4"); n = max(1, int(round(d * FPS))); c = b.get("clip", {})
    if c.get("img"):
        src = S.get_media(c["img"], wd, credits); inp = f"-loop 1 -framerate {FPS} -i '{src}'"
    else:
        src = sources[c["src"]]; inp = f"-ss {c.get('t', 0):.2f} -i '{src}'"
    zoom = f"1+0.05*t/{d:.2f}"
    fg = (f"[0:v]fps={FPS},split[a][b];"
          f"[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=28:2,eq=brightness=-0.22:saturation=1.1[bg];"
          f"[b]scale={CARD_W}:{CARD_H}:force_original_aspect_ratio=increase,crop={CARD_W}:{CARD_H},"
          f"scale=w='trunc({CARD_W}*({zoom})/2)*2':h='trunc({CARD_H}*({zoom})/2)*2':eval=frame,crop={CARD_W}:{CARD_H},format=rgba[c0];"
          f"[1:v]format=gray[m];[c0][m]alphamerge[card];"
          f"[bg]drawbox=x={(W-CARD_W)//2-6}:y={CARD_Y-6}:w={CARD_W+12}:h={CARD_H+12}:color=0x3a0a0e@0.55:t=fill[bg2];"
          f"[bg2][card]overlay={(W-CARD_W)//2}:{CARD_Y}[v0]")
    inp += f" -loop 1 -i '{mask}'"; k = 2
    if b.get("num"):
        inp += f" -loop 1 -i '{num_png(b['num'], os.path.join(wd, f'num_{i:02d}.png'))}'"
        fg += f";[{k}:v]format=rgba,fade=t=in:st=0:d=0.2:alpha=1[nn];[v0][nn]overlay=0:'{CARD_Y-300}-40*max(0,1-t/0.25)'[v1]"; k += 1
    else:
        fg += ";[v0]null[v1]"
    if b.get("glitch"):
        fg += ";[v1]rgbashift=rh=-16:bh=16:enable='lt(t,0.22)',noise=alls=22:allf=t:enable='lt(t,0.22)'[v]"
    else:
        fg += ";[v1]null[v]"
    S.sh(f"ffmpeg -v error -y {inp} -filter_complex \"{fg}\" -map [v] -frames:v {n} -an -c:v libx264 -preset veryfast -crf 19 -pix_fmt yuv420p '{out}'")
    return out

def captions(words, keys, out):
    keyset = {S.norm(k) for k in keys}
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: C,Poppins,96,&H00FFFFFF,&H00FFFFFF,&H00000000,&H99000000,-1,0,0,0,100,100,0,0,1,6,4,5,60,60,0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    for j, w in enumerate(words):
        st = w["s"]; en = words[j + 1]["s"] if j + 1 < len(words) else w["e"] + 0.3
        txt = re.sub(r"[{}\\]", "", w["w"]).upper()
        if any(k and (k in S.norm(w["w"])) for k in keyset):
            body = r"{\bord14\3c&H002F26E3&\shad0}" + txt  # red box (ASS colours are BGR)
        else:
            body = txt
        ev.append(f"Dialogue: 0,{S.ass_time(st)},{S.ass_time(en)},C,,0,0,0,,{{\\pos(540,1440)\\fscx115\\fscy115\\t(0,90,\\fscx100\\fscy100)}}{body}")
    open(out, "w").write(hdr + "\n".join(ev) + "\n"); return out

def build(spec_path, outdir):
    outdir = os.path.abspath(outdir); spec = json.load(open(spec_path)); vid = spec["id"]; wd = os.path.join(outdir, "work_" + vid); os.makedirs(wd, exist_ok=True)
    credits = set(); seed = int(hashlib.md5(vid.encode()).hexdigest(), 16) % 1000
    sources = {k: (v if os.path.exists(v) else S.fetch(v, os.path.join(wd, f"src_{k}.mp4"))) for k, v in spec.get("sources", {}).items()}
    beats = spec["beats"]; outro = spec.get("outro_say", "Follow Gaming Sane for daily gaming news.")
    allb = beats + [{"say": outro}]
    pieces, words, starts, ranges, t = [], [], [], [], 0.0
    for i, b in enumerate(allb):
        mp3 = os.path.join(wd, f"vo_{i:02d}.mp3"); ws = tts_words(b["say"].strip(), mp3)
        wav = os.path.join(wd, f"vo_{i:02d}.wav"); S.sh(f"ffmpeg -v error -y -i '{mp3}' -ar 48000 -ac 1 '{wav}'")
        dd = dur(wav); gap = 0.06 if i < len(allb) - 1 else 0.0
        starts.append(t); ranges.append((len(words), len(words) + len(ws)))
        words += [dict(w=w["w"], s=t + w["s"], e=t + w["e"]) for w in ws]
        pieces.append((wav, gap)); t += dd + gap
    lst = os.path.join(wd, "vo_list.txt"); sil = os.path.join(wd, "sil.wav")
    S.sh(f"ffmpeg -v error -y -f lavfi -i anullsrc=r=48000:cl=mono -t 0.06 '{sil}'")
    open(lst, "w").write("".join(f"file '{p}'\n" + (f"file '{sil}'\n" if g else "") for p, g in pieces))
    vo = os.path.join(wd, "vo.wav"); S.sh(f"ffmpeg -v error -y -f concat -safe 0 -i '{lst}' -c copy '{vo}'")
    total = t + 1.2; ends = starts[1:] + [total]; X = 0.12
    o0, o1 = ranges[-1]
    t_logo = next((w["s"] for w in words[o0:o1] if S.norm(w["w"]) == "gaming"), starts[-1] + 0.4)
    mask = round_mask(os.path.join(wd, "mask.png"), CARD_W, CARD_H)
    segs = [segment(i, b, ends[i] - starts[i] + X, sources, wd, credits, mask) for i, b in enumerate(beats)]
    segs.append(S.outro_seg(wd, GS, ends[-1] - starts[-1], t_logo - starts[-1]))
    inp = " ".join(f"-i '{s}'" for s in segs); fl = []; prev = "[0:v]"
    for j in range(1, len(segs)):
        fl.append(f"{prev}[{j}:v]xfade=transition={'fadewhite' if j % 4 == 0 else 'fade'}:duration={X}:offset={starts[j]:.3f}[x{j}]"); prev = f"[x{j}]"
    cap = captions(words[:o0], sum((b.get("keys", []) for b in beats), []), os.path.join(wd, "cap.ass"))
    fl.append(f"{prev}ass='{cap}':fontsdir=/usr/share/fonts[v]")
    silent = os.path.join(wd, "video.mp4")
    S.sh(f"ffmpeg -v error -y {inp} -filter_complex \"{';'.join(fl)}\" -map [v] -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p -r {FPS} '{silent}'")
    vdur = dur(silent)
    audio = S.mix(vo, vdur, starts, t_logo, GS, wd, seed, os.path.join(wd, "mix.wav"))
    final = os.path.join(outdir, vid + ".mp4")
    S.sh(f"ffmpeg -v error -y -i '{silent}' -i '{audio}' -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart '{final}'")
    S.sh(f"ffmpeg -v error -y -ss 0.8 -i '{final}' -frames:v 1 -q:v 2 '{os.path.join(outdir, vid + '_cover.jpg')}'")
    step = max(1.0, vdur / 12)
    S.sh(f"ffmpeg -v error -y -i '{final}' -vf \"fps=1/{step:.2f},scale=216:384,tile=6x2\" -frames:v 1 '{os.path.join(outdir, vid + '_sheet.jpg')}'")
    json.dump({"duration": vdur, "credits": sorted(credits), "footage": spec.get("credit", "")}, open(os.path.join(outdir, vid + "_meta.json"), "w"), indent=1)
    print(json.dumps({"mp4": final, "dur": round(vdur, 1)}))

if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
