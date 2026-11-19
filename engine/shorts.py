#!/usr/bin/env python3
"""Short-video engine for Wealth Extreme (theme "we") and Gaming Sane (theme "gs").
Usage: python3 shorts.py spec.json OUTDIR
spec = {"id","theme","speed"(opt),"beats":[{"say","bg":{"img"|"vid"|"grad"},"card":{...},"keys":[...]}],"outro_say"}
Card types: hero{big,sub}, logo{img}, photo{img}, versus{a:{label,value},b:{...}}, bars{items:[{label,value,num}]},
            list{items:[..]}, icon{emoji, big?}. Keep on-screen text minimal (numbers/names only).
Output: OUTDIR/<id>.mp4, OUTDIR/<id>_cover.jpg, OUTDIR/<id>_sheet.jpg (QA contact sheet)
"""
import urllib.error, json, os, sys, re, subprocess, math, hashlib, random, urllib.request, urllib.parse, base64, shutil
import numpy as np, soundfile as sf
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
UA = {"User-Agent": "WealthExtremeShorts/1.0 (https://www.instagram.com/wealth.extreme/) python-urllib"}
THEMES = {
  "we": dict(accent="#36F08F", accent2="#C9D3D6", tint=(4, 40, 22), glass="rgba(10,30,20,0.55)",
             font="Poppins", cap_font="Poppins", cap_hi="&H008FF036", voice="am_michael",
             plate="logo_we.png", brand=["Wealth", "Extreme"],
             bgm=[443, 587, 140, 127, 52], grad=((2, 22, 12), (0, 0, 0))),
  "gs": dict(accent="#FF2BD6", accent2="#22E6FF", tint=(40, 6, 48), glass="rgba(30,8,40,0.55)",
             font="Poppins", cap_font="Poppins", cap_hi="&H00D62BFF", voice="am_michael",
             plate="logo_gs.png", brand=["Gaming", "Sane"],
             bgm=[614, 584, 22, 2, 52], grad=((30, 4, 44), (4, 0, 12))),
}
SFX = {"whoosh": [1489, 1490, 2357], "pop": [2568, 2570], "hit": [1714, 2019], "riser": [3005, 2635]}

def sh(cmd, **kw):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)
    if r.returncode: raise RuntimeError(cmd[:300] + "\n" + r.stderr[-1500:])
    return r.stdout

def fetch(url, dst, tries=7):
    if os.path.exists(dst) and os.path.getsize(dst) > 1000: return dst
    import time
    err = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as f: f.write(r.read())
            if os.path.getsize(dst) > 1000: time.sleep(1.0); return dst
        except urllib.error.HTTPError as e:
            err = e; ra = e.headers.get("Retry-After") if e.headers else None
            time.sleep(min(60, int(ra) if ra and ra.isdigit() else 5 * (i + 1)))
        except Exception as e:
            err = e; time.sleep(4 * (i + 1))
    raise RuntimeError(f"fetch failed {url}: {err}")

def commons(name, dst, width=1400):
    """Wikimedia Commons file name (File:X.jpg or X.jpg) -> thumbnail download. Returns (path, credit)."""
    name = name.replace("File:", "")
    api = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo&iiprop=url|extmetadata"
           f"&iiurlwidth={width}&titles=File:{urllib.parse.quote(name)}")
    import time
    for i in range(6):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(api, headers=UA), timeout=60)); break
        except Exception as e:
            if i == 5: raise
            time.sleep(4 * (i + 1))
    p = next(iter(d["query"]["pages"].values()))
    ii = p["imageinfo"][0]; md = ii.get("extmetadata", {})
    art = re.sub("<[^>]+>", "", md.get("Artist", {}).get("value", "")).strip()
    art = re.split(r" - |\(|;|\n", art)[0].strip()[:40] or "Wikimedia Commons"
    lic = md.get("LicenseShortName", {}).get("value", "")
    fetch(ii.get("thumburl") or ii["url"], dst)
    return dst, (f"{art} ({lic})" if lic and "public domain" not in lic.lower() else "")

def get_media(src, wd, credits):
    """src: http URL | 'commons:File.jpg' | local path. Returns local path."""
    if not src: return None
    if os.path.exists(src): return src
    h = hashlib.md5(src.encode()).hexdigest()[:10]
    ext = os.path.splitext(urllib.parse.urlparse(src.split("commons:")[-1]).path)[1].lower() or ".jpg"
    if ext == ".svg": ext = ".png"
    dst = os.path.join(wd, "m_" + h + ext)
    if src.startswith("commons:"):
        nm = src[8:]
        p, c = commons(nm, dst, 1280 if not nm.lower().endswith(".svg") else 960)
        if c: credits.add(c)
        return p
    return fetch(src, dst)

# ---------------- voice ----------------
def tts(text, out, voice, speed):
    from kokoro_onnx import Kokoro
    k = Kokoro(os.path.join(MODELS, "kokoro.onnx"), os.path.join(MODELS, "voices.bin"))
    a, sr = k.create(text, voice=voice, speed=speed, lang="en-us")
    sf.write(out, a, sr); return out

def align(wav):
    from faster_whisper import WhisperModel
    m = WhisperModel("base.en", device="cpu", compute_type="int8")
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", wav, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
    audio = np.frombuffer(raw, np.float32)
    segs, _ = m.transcribe(audio, word_timestamps=True, beam_size=1, vad_filter=False)
    return [dict(w=w.word.strip(), s=w.start, e=w.end) for s in segs for w in s.words]

def norm(t): return re.sub(r"[^a-z0-9]", "", t.lower())

def map_beats(beats, words):
    """Assign word index ranges to beats by sequential fuzzy matching of token counts."""
    out, wi = [], 0
    for b in beats:
        toks = [norm(t) for t in re.findall(r"[\w$%.,'-]+", b["say"]) if norm(t)]
        start = wi
        # advance roughly len(toks) words, re-sync on the last token if found nearby
        target = wi + max(1, len(toks))
        best = min(target, len(words))
        last = toks[-1] if toks else ""
        for j in range(max(wi, target - 4), min(len(words), target + 5)):
            if norm(words[j]["w"]) and (norm(words[j]["w"]) == last or last.startswith(norm(words[j]["w"])) or norm(words[j]["w"]).startswith(last)):
                best = j + 1
                if j + 1 >= target: break
        wi = max(start + 1, best) if start < len(words) else start
        out.append((start, min(wi, len(words))))
    out[-1] = (out[-1][0], len(words))
    return out

# ---------------- cards (HTML glass -> PNG) ----------------
CSS = """
*{margin:0;padding:0;box-sizing:border-box} body{width:1080px;height:1920px;background:transparent;font-family:'%(font)s',sans-serif;}
.wrap{position:absolute;left:0;right:0;top:%(top)dpx;display:flex;justify-content:center}
.g{background:linear-gradient(145deg,rgba(255,255,255,.20),rgba(255,255,255,.04) 45%%,rgba(255,255,255,.10));
   border:2px solid rgba(255,255,255,.35);border-radius:44px;box-shadow:0 30px 80px rgba(0,0,0,.55),inset 0 2px 0 rgba(255,255,255,.45),0 0 60px %(acc)s44;
   backdrop-filter:blur(8px);padding:44px 56px;color:#fff;text-align:center;position:relative;overflow:hidden}
.g:before{content:'';position:absolute;left:-40%%;top:-60%%;width:80%%;height:120%%;background:linear-gradient(100deg,transparent,rgba(255,255,255,.22),transparent);transform:rotate(18deg)}
.big{font-size:%(bigsz)dpx;font-weight:900;line-height:1;letter-spacing:-3px;background:linear-gradient(180deg,#fff 0%%,%(acc2)s 55%%,%(acc)s 100%%);-webkit-background-clip:text;color:transparent;filter:drop-shadow(0 6px 18px rgba(0,0,0,.6))}
.sub{font-size:54px;font-weight:700;margin-top:18px;color:#E9F2EE;letter-spacing:.5px}
.lab{font-size:46px;font-weight:700;color:#E8EEF0}
.val{font-size:96px;font-weight:900;color:%(acc)s;text-shadow:0 0 30px %(acc)s66}
.vs{display:flex;gap:30px;align-items:stretch}
.vs .g{width:440px;padding:40px 24px}
.vsx{position:absolute;left:50%%;top:50%%;transform:translate(-50%%,-50%%);width:120px;height:120px;border-radius:60px;background:%(acc)s;color:#06120c;font-weight:900;font-size:48px;display:flex;align-items:center;justify-content:center;box-shadow:0 0 50px %(acc)saa;z-index:3}
.bar{display:flex;align-items:center;gap:22px;margin:16px 0;text-align:left}
.bar .t{width:250px;font-size:42px;font-weight:700}
.bar .b{height:64px;border-radius:32px;background:linear-gradient(90deg,%(acc)s,%(acc2)s);box-shadow:0 0 30px %(acc)s66}
.bar .n{font-size:44px;font-weight:900;margin-left:6px}
.li{font-size:56px;font-weight:800;margin:14px 0;text-align:left}
.li b{color:%(acc)s;margin-right:18px}
.logo{background:rgba(255,255,255,.94);border-radius:48px;padding:50px 64px;box-shadow:0 30px 90px rgba(0,0,0,.6),0 0 70px %(acc)s55}
.logo img{max-width:640px;max-height:360px;display:block}
.photo{border-radius:44px;overflow:hidden;border:4px solid rgba(255,255,255,.55);box-shadow:0 30px 90px rgba(0,0,0,.65),0 0 60px %(acc)s55}
.photo img{width:860px;height:640px;object-fit:cover;display:block}
.emo{font-size:300px;line-height:1;filter:drop-shadow(0 20px 40px rgba(0,0,0,.6))}
"""

def esc(s): return str(s).replace("&", "&amp;").replace("<", "&lt;")

def data_uri(path):
    ext = os.path.splitext(path)[1].lower().strip(".") or "png"
    ext = {"jpg": "jpeg", "svg": "svg+xml"}.get(ext, ext)
    return f"data:image/{ext};base64," + base64.b64encode(open(path, "rb").read()).decode()

def card_html(c, th, wd, credits):
    t = c.get("type", "hero"); top = c.get("top", 470)
    big = esc(c.get("big", "")); bigsz = 210 if len(big) <= 6 else (170 if len(big) <= 9 else 130)
    if t == "hero":
        inner = f'<div class="g"><div class="big">{big}</div>' + (f'<div class="sub">{esc(c["sub"])}</div>' if c.get("sub") else "") + "</div>"
    elif t == "logo":
        inner = f'<div class="logo"><img src="{data_uri(get_media(c["img"], wd, credits))}"></div>'
    elif t == "photo":
        inner = f'<div class="photo"><img src="{data_uri(get_media(c["img"], wd, credits))}"></div>'
    elif t == "versus":
        a, b = c["a"], c["b"]
        inner = (f'<div class="vs" style="position:relative"><div class="g"><div class="lab">{esc(a["label"])}</div><div class="val">{esc(a["value"])}</div></div>'
                 f'<div class="vsx">VS</div><div class="g"><div class="lab">{esc(b["label"])}</div><div class="val">{esc(b["value"])}</div></div></div>')
    elif t == "bars":
        mx = max(i["num"] for i in c["items"]) or 1
        rows = "".join(f'<div class="bar"><div class="t">{esc(i["label"])}</div><div class="b" style="width:{int(80+420*i["num"]/mx)}px"></div><div class="n">{esc(i["value"])}</div></div>' for i in c["items"])
        inner = f'<div class="g" style="padding:40px 46px">{rows}</div>'
    elif t == "list":
        rows = "".join(f'<div class="li"><b>{k+1}</b>{esc(x)}</div>' for k, x in enumerate(c["items"]))
        inner = f'<div class="g">{rows}</div>'
    elif t == "icon":
        inner = f'<div style="text-align:center"><div class="emo">{c["emoji"]}</div>' + (f'<div class="g" style="margin-top:30px;padding:26px 46px"><div class="big" style="font-size:150px">{big}</div></div>' if big else "") + "</div>"
    else:
        raise ValueError(t)
    css = CSS % dict(font=th["font"], acc=th["accent"], acc2=th["accent2"], top=top, bigsz=bigsz)
    return f"<html><head><style>{css}</style></head><body><div class='wrap'>{inner}</div></body></html>"

def render_cards(beats, th, wd, credits):
    from playwright.sync_api import sync_playwright
    paths = []
    with sync_playwright() as p:
        br = p.chromium.launch(); pg = br.new_page(viewport={"width": W, "height": H})
        for i, b in enumerate(beats):
            c = b.get("card")
            if not c: paths.append(None); continue
            pg.set_content(card_html(c, th, wd, credits)); pg.wait_for_timeout(120)
            out = os.path.join(wd, f"card_{i:02d}.png")
            pg.screenshot(path=out, omit_background=True); paths.append(out)
        br.close()
    return paths

# ---------------- backgrounds ----------------
def grade_still(src, out, th, blur=0):
    im = Image.open(src).convert("RGB")
    sw, shh = int(W * 1.18), int(H * 1.18)
    r = max(sw / im.width, shh / im.height)
    im = im.resize((max(sw, int(im.width * r)), max(shh, int(im.height * r))), Image.LANCZOS)
    l, t = (im.width - sw) // 2, (im.height - shh) // 2
    im = im.crop((l, t, l + sw, t + shh))
    if blur: im = im.filter(ImageFilter.GaussianBlur(blur))
    im = ImageEnhance.Contrast(im).enhance(1.12); im = ImageEnhance.Color(im).enhance(1.1)
    tint = Image.new("RGB", im.size, th["tint"]); im = Image.blend(im, tint, 0.22)
    # vignette + bottom shade for captions
    vg = Image.new("L", im.size, 0); d = ImageDraw.Draw(vg)
    for k in range(60):
        a = int(255 * (k / 60) ** 2 * 0.75)
        d.rectangle([k * 9, k * 16, im.width - k * 9, im.height - k * 16], outline=None)
    arr = np.asarray(im).astype(np.float32)
    yy, xx = np.mgrid[0:im.height, 0:im.width]
    rr = np.sqrt(((xx - im.width / 2) / (im.width / 2)) ** 2 + ((yy - im.height / 2) / (im.height / 2)) ** 2)
    v = np.clip(1.05 - 0.45 * rr ** 2, 0.35, 1)[..., None]
    arr = arr * v * 0.82
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(out, quality=94)
    return out

def grad_bg(out, th, seed=0):
    random.seed(seed)
    a, b = np.array(th["grad"][0], np.float32), np.array(th["grad"][1], np.float32)
    sw, shh = int(W * 1.18), int(H * 1.18)
    yy, xx = np.mgrid[0:shh, 0:sw]
    rr = np.sqrt(((xx - sw / 2) / sw) ** 2 + ((yy - shh * 0.35) / shh) ** 2)
    t = np.clip(rr * 1.6, 0, 1)[..., None]
    arr = a * (1 - t) + b * t
    im = Image.fromarray(arr.astype(np.uint8)); d = ImageDraw.Draw(im, "RGBA")
    acc = tuple(int(th["accent"][i:i + 2], 16) for i in (1, 3, 5))
    for _ in range(26):
        x, y, r = random.randint(0, sw), random.randint(0, shh), random.randint(3, 12)
        d.ellipse([x - r, y - r, x + r, y + r], fill=acc + (random.randint(40, 120),))
    for k in range(0, sw, 90):  # perspective floor grid
        d.line([(sw / 2 + (k - sw / 2) * 0.25, shh * 0.62), (k * 1.0 - sw * 0.5 + k, shh)], fill=acc + (35,), width=2)
    for k in range(12):
        y = shh * 0.62 + (shh * 0.38) * (k / 12) ** 1.8
        d.line([(0, y), (sw, y)], fill=acc + (30,), width=2)
    im.filter(ImageFilter.GaussianBlur(1)).save(out, quality=94); return out

def segment(i, b, dur, card, wd, th, credits, seed):
    """Render one beat to seg_i.mp4 (video only)."""
    out = os.path.join(wd, f"seg_{i:02d}.mp4")
    bg = b.get("bg", {}) or {}
    n = max(1, int(round(dur * FPS)))
    dirn = seed % 4
    if bg.get("vid"):
        src = get_media(bg["vid"], wd, credits)
        base = (f"-stream_loop -1 -i '{src}'", f"[0:v]scale={int(W*1.08)}:{int(H*1.08)}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"eq=contrast=1.08:saturation=1.08:brightness=-0.06,colorbalance=gs=0.04,vignette=PI/4,fps={FPS}[bg]")
    else:
        still = os.path.join(wd, f"bg_{i:02d}.jpg")
        if bg.get("img"): grade_still(get_media(bg["img"], wd, credits), still, th, blur=bg.get("blur", 0))
        else: grad_bg(still, th, seed)
        sx, sy = int(W * 0.18), int(H * 0.18)
        px = [f"{sx}*t/{dur:.3f}", f"{sx}*(1-t/{dur:.3f})", f"{sx}/2", f"{sx}/2"][dirn]
        py = [f"{sy}/2", f"{sy}/2", f"{sy}*t/{dur:.3f}", f"{sy}*(1-t/{dur:.3f})"][dirn]
        base = (f"-loop 1 -framerate {FPS} -i '{still}'", f"[0:v]crop={W}:{H}:x='{px}':y='{py}',fps={FPS}[bg]")
    inp, fg = base
    if card:
        inp += f" -loop 1 -framerate {FPS} -i '{card}'"
        ease = "(1-pow(max(0,1-t/0.35),3))"
        fg += (f";[1:v]format=rgba,fade=t=in:st=0.05:d=0.3:alpha=1[c];"
               f"[bg][c]overlay=x=0:y='110*(1-{ease})+8*sin(t*2.2)':shortest=1[v]")
    else:
        fg += ";[bg]null[v]"
    sh(f"ffmpeg -v error -y {inp} -filter_complex \"{fg}\" -map [v] -frames:v {n} -c:v libx264 -preset veryfast -crf 19 -pix_fmt yuv420p '{out}'")
    return out

def outro_seg(wd, th, dur, t_logo):
    out = os.path.join(wd, "seg_outro.mp4"); plate = os.path.join(HERE, th["plate"])
    pre = os.path.join(wd, "outro_pre.jpg"); grad_bg(pre, th, 99)
    n = int(round(dur * FPS)); tl = max(0.0, t_logo)
    fg = (f"[0:v]crop={W}:{H}:x='{int(W*0.09)}':y='{int(H*0.09)}',fps={FPS}[a];"
          f"[1:v]scale={W}:{H},format=rgba,fade=t=in:st={tl:.2f}:d=0.35:alpha=1,"
          f"zoompan=z='if(lt(on,{int(tl*FPS)}),1.25,max(1.0,1.25-0.25*(on-{int(tl*FPS)})/{int(0.5*FPS)}))':d=1:s={W}x{H}:fps={FPS}[p];"
          f"[a][p]overlay=0:0,eq=brightness='0.25*exp(-pow((t-{tl+0.15:.2f})*7,2))'[v]")
    sh(f"ffmpeg -v error -y -loop 1 -framerate {FPS} -i '{pre}' -loop 1 -framerate {FPS} -i '{plate}' -filter_complex \"{fg}\" -map [v] -frames:v {n} -c:v libx264 -preset veryfast -crf 19 -pix_fmt yuv420p '{out}'")
    return out

# ---------------- captions (ASS, word-by-word) ----------------
def ass_time(t):
    t = max(0, t); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def captions(words, keys, th, out):
    keyset = {norm(k) for k in keys}
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: C,{th['cap_font']},92,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,5,3,5,70,70,0

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # chunk into lines of <=3 words / <=18 chars, break on punctuation
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        if len(cur) >= 3 or sum(len(x["w"]) for x in cur) > 14 or re.search(r"[.,!?;:]$", w["w"]):
            chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    ev = []
    for ci, ch in enumerate(chunks):
        end_chunk = chunks[ci + 1][0]["s"] if ci + 1 < len(chunks) else ch[-1]["e"] + 0.4
        for k, w in enumerate(ch):
            st = w["s"]; en = ch[k + 1]["s"] if k + 1 < len(ch) else end_chunk
            parts = []
            for j, x in enumerate(ch[:k + 1]):
                txt = re.sub(r"[{}\\]", "", x["w"]).upper()
                if j < k: parts.append(r"{\1c&H00B4B4B4&\bord5\3c&H00000000&\4a&H96&}" + txt)
                elif norm(x["w"]) in keyset:
                    parts.append(r"{\1c&H00FFFFFF&\3c" + th["cap_hi"] + r"&\bord12\4a&HFF&\fscx108\fscy108}" + txt)
                else: parts.append(r"{\1c&H00FFFFFF&\bord5\3c&H00000000&\fscx106\fscy106}" + txt)
            pop = r"{\pos(540,1330)\t(0,80,\fscx104\fscy104)}"
            ev.append(f"Dialogue: 0,{ass_time(st)},{ass_time(en)},C,,0,0,0,,{pop}" + " ".join(parts))
    open(out, "w").write(hdr + "\n".join(ev) + "\n")
    return out

# ---------------- audio ----------------
def mixkit_sfx(kind, wd, seed):
    ids = SFX[kind]; i = ids[seed % len(ids)]
    try: return fetch(f"https://assets.mixkit.co/active_storage/sfx/{i}/{i}-preview.mp3", os.path.join(wd, f"sfx_{i}.mp3"))
    except Exception: return None

def mix(vo, total, cuts, t_logo, th, wd, seed, out):
    music_id = th["bgm"][seed % len(th["bgm"])]
    try: bgm = fetch(f"https://assets.mixkit.co/music/{music_id}/{music_id}.mp3", os.path.join(wd, f"bgm_{music_id}.mp3"))
    except Exception: bgm = None
    ins, flt, labs = [f"-i '{vo}'"], [], []
    flt.append("[0:a]aformat=sample_rates=48000:channel_layouts=stereo,apad[vo]")
    k = 1
    if bgm:
        ins.append(f"-stream_loop -1 -i '{bgm}'")
        flt.append(f"[{k}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.13,afade=t=out:st={total-1.2:.2f}:d=1.2[bg]"); labs.append("[bg]"); k += 1
    events = [("whoosh", c, 0.22) for c in cuts[1:]] + [("riser", max(0, t_logo - 1.0), 0.30), ("hit", t_logo, 0.40)]
    for j, (kind, t, vol) in enumerate(events):
        f = mixkit_sfx(kind, wd, seed + j)
        if not f: continue
        ins.append(f"-i '{f}'")
        flt.append(f"[{k}:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:1.6,afade=t=out:st=1.2:d=0.4,volume={vol},adelay={int(max(0,t-0.08)*1000)}|{int(max(0,t-0.08)*1000)}[s{j}]")
        labs.append(f"[s{j}]"); k += 1
    if bgm:  # duck music under voice
        flt.append("[vo]asplit=2[vo1][vo2]")
        flt.append("[bg][vo2]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[bgd]")
        labs = ["[bgd]"] + [l for l in labs if l != "[bg]"]; vlab = "[vo1]"
    else: vlab = "[vo]"
    flt.append(f"{vlab}{''.join(labs)}amix=inputs={1+len(labs)}:normalize=0:duration=first,atrim=0:{total:.2f},loudnorm=I=-14:TP=-1.5:LRA=11[a]")
    sh(f"ffmpeg -v error -y {' '.join(ins)} -filter_complex \"{';'.join(flt)}\" -map [a] -ar 48000 -c:a pcm_s16le '{out}'")
    return out

# ---------------- main ----------------
def build(spec_path, outdir):
    spec = json.load(open(spec_path)); th = THEMES[spec.get("theme", "we")]
    vid = spec["id"]; wd = os.path.join(outdir, "work_" + vid); os.makedirs(wd, exist_ok=True)
    credits = set(); seed = int(hashlib.md5(vid.encode()).hexdigest(), 16) % 1000
    beats = spec["beats"]
    outro = spec.get("outro_say") or f"Follow {' '.join(th['brand'])} for more."
    allb = beats + [{"say": outro}]
    from kokoro_onnx import Kokoro
    from faster_whisper import WhisperModel
    kk = Kokoro(os.path.join(MODELS, "kokoro.onnx"), os.path.join(MODELS, "voices.bin"))
    wm = WhisperModel("base.en", device="cpu", compute_type="int8")
    voice = spec.get("voice", th["voice"]); speed = spec.get("speed", 1.1)
    pieces, words, starts, ranges, t, sr = [], [], [], [], 0.0, 24000
    for i, b in enumerate(allb):
        a, sr = kk.create(b["say"].strip(), voice=voice, speed=speed, lang="en-us")
        nz = np.where(np.abs(a) > 0.01)[0]  # trim edge silence
        if len(nz): a = a[max(0, nz[0] - int(0.03 * sr)): nz[-1] + int(0.06 * sr)]
        gap = np.zeros(int((0.10 if i < len(allb) - 1 else 0.0) * sr), np.float32)
        p = os.path.join(wd, f"vo_{i:02d}.wav"); sf.write(p, a, sr)
        audio16 = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout, np.float32)
        segs, _ = wm.transcribe(audio16, word_timestamps=True, beam_size=1, initial_prompt=b["say"])
        dur_a = len(a) / sr; ws = []
        for sg in segs:
            for w in sg.words:
                tok = w.word.strip()
                if not tok or w.start >= dur_a - 0.02: continue
                if ws and (re.match(r"^[.,%]", tok) or ws[-1]["w"] in ("$",) or (re.match(r"^\d", tok) and ws[-1]["w"].endswith((".", ",")) and re.search(r"\d[.,]$", ws[-1]["w"]))):
                    ws[-1]["w"] += tok; ws[-1]["e"] = t + w.end; continue
                ws.append(dict(w=tok, s=t + w.start, e=t + w.end))
        ntok = len(b["say"].split())
        ws = ws[:ntok + 2]
        starts.append(t); ranges.append((len(words), len(words) + len(ws))); words += ws
        pieces += [a.astype(np.float32), gap]; t += (len(a) + len(gap)) / sr
    vo = os.path.join(wd, "vo.wav"); sf.write(vo, np.concatenate(pieces), sr)
    vo_len = t
    total = vo_len + 1.3
    ends = starts[1:] + [total]
    o0, o1 = ranges[-1]
    t_logo = next((w["s"] for w in words[o0:o1] if norm(w["w"]) == norm(th["brand"][0])), starts[-1] + 0.4)
    cards = render_cards(beats, th, wd, credits); X = 0.18
    segs = []
    for i, b in enumerate(beats):
        segs.append(segment(i, b, ends[i] - starts[i] + X, cards[i], wd, th, credits, seed + i))
    segs.append(outro_seg(wd, th, ends[-1] - starts[-1], t_logo - starts[-1]))
    # concat with short crossfades (keeps cut times)
    durs = [e - s for s, e in zip(starts, ends)]
    inp = " ".join(f"-i '{s}'" for s in segs); fl = []; prev = "[0:v]"
    for j in range(1, len(segs)):  # each seg rendered X longer, so offsets == original start times (no drift)
        fl.append(f"{prev}[{j}:v]xfade=transition={'fade' if j%3 else 'smoothup'}:duration={X}:offset={starts[j]:.3f}[x{j}]")
        prev = f"[x{j}]"
    cap = captions(words[:ranges[-1][0]], sum((b.get("keys", []) for b in beats), []), th, os.path.join(wd, "cap.ass"))
    fl.append(f"{prev}ass='{cap}':fontsdir=/usr/share/fonts[v]")
    silent = os.path.join(wd, "video.mp4")
    sh(f"ffmpeg -v error -y {inp} -filter_complex \"{';'.join(fl)}\" -map [v] -c:v libx264 -preset veryfast -crf 18 -pix_fmt yuv420p -r {FPS} '{silent}'")
    vdur = float(sh(f"ffprobe -v error -show_entries format=duration -of csv=p=0 '{silent}'"))
    # xfade shortens timeline by X per join: shift audio cues to match
    audio = mix(vo, vdur, starts, t_logo, th, wd, seed, os.path.join(wd, "mix.wav"))
    final = os.path.join(outdir, vid + ".mp4")
    sh(f"ffmpeg -v error -y -i '{silent}' -i '{audio}' -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest -movflags +faststart '{final}'")
    # cover (frame inside first beat with card) + QA sheet
    cover = os.path.join(outdir, vid + "_cover.jpg")
    sh(f"ffmpeg -v error -y -ss {min(1.2, durs[0]*0.7):.2f} -i '{final}' -frames:v 1 -q:v 2 '{cover}'")
    sheet = os.path.join(outdir, vid + "_sheet.jpg")
    step = max(1.0, vdur / 12)
    sh(f"ffmpeg -v error -y -i '{final}' -vf \"fps=1/{step:.2f},scale=216:384,tile=6x2\" -frames:v 1 '{sheet}'")
    json.dump({"duration": vdur, "credits": sorted(credits), "words": len(words)}, open(os.path.join(outdir, vid + "_meta.json"), "w"), indent=1)
    print(json.dumps({"mp4": final, "dur": round(vdur, 1), "credits": sorted(credits)}))

MODELS = os.environ.get("MODELS", "/home/claude/models")
if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
