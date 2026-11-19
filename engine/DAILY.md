# Daily Shorts runbook — Wealth Extreme (WE) + Gaming Sane (GS)

Goal: 2–3 viral-style Shorts/Reels per channel per day, YouTube + Instagram, near-zero cost.
Keep it lean: no subagents, ≤6 web searches per channel, one QA look per video (contact sheet).

## 0. Setup (≈3 min, every run starts fresh)
```
git clone <repo> /home/claude/ws && cd /home/claude/ws
pip install --break-system-packages -q kokoro-onnx soundfile faster-whisper
mkdir -p /home/claude/models && cd /home/claude/models && \
 curl -sL -o kokoro.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx && \
 curl -sL -o voices.bin  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```
Playwright Chromium is preinstalled (/opt/pw-browsers). Fonts: Poppins is installed.

## 1. Research (pick 3 topics)
- WE (US money/business, high RPM): today's biggest money/business story (earnings, deals, Fed, prices, taxes, big launches' money angle), + 1 evergreen high-search money explainer. Verify every number on ≥1 primary/major source. Never repeat a topic in `log.md`.
- GS (gaming news): the day's most-talked game story (launches, reveals, leaks confirmed by a reliable outlet, records, prices, delays). Only confirmed facts; label rumors as rumors.
- Algorithm rules: hook = surprising number or conflict in the first 2 s; 35–50 s; a new visual every ~2–3 s; one question CTA at the end (comments); loopable last line.

## 2. Script → spec JSON (`day/<id>.json`)
- 9–12 beats, each one short sentence (≈2–3 s). Write numbers as digits (`$115.8 billion`, `93%`).
- Each beat: `bg` = `{"img":"commons:<File name>"}` (find with `python3 engine/find.py "query"`), optional `"blur":6`, or `{}` for brand gradient.
- `card` types: hero{big,sub}, logo{img}, photo{img}, versus{a,b}, bars{items}, list{items}, icon{emoji,big?}.
  Emoji/icon cards only on `{}` or blurred backgrounds (never over a face/logo). Minimal on-screen text: numbers/names only.
- `keys`: 1–2 words of that beat to box-highlight in captions.
- `outro_say`: WE → "Follow Wealth Extreme for the money behind the headlines." GS → "Follow Gaming Sane for daily gaming news."
  The original channel logo plate (engine/logo_we.png / logo_gs.png) appears on the brand word.

## 3. Render + QA
`python3 engine/shorts.py day/<id>.json out` (≈3–4 min each; run detached with setsid nohup, sequentially).
Read `out/<id>_sheet.jpg` once: no text cut off, card matches line, no emoji on faces, logo outro present. Fix spec and re-render only if needed.

## 4. Publish links
`engine/publish.sh out/<id>.mp4` → public GitHub release asset URL (repo release tag = date). Same for `_cover.jpg`.

## 5. Schedule
- WE → Metricool brand 7870926 (IG @wealth.extreme + YouTube), tz Asia/Calcutta. Existing queue holds 05:30 and 22:30 IST; new slots: 19:30, 02:30 (+1d), 08:00 (+1d) IST. Check getScheduledPosts for the day first; never double-book a slot.
  info: providers instagram+youtube; instagramData {type REEL, showReelOnFeed true, isAiGenerated true}; youtubeData {title ≤70 chars, type short, privacy public, tags 10–15, category EDUCATION, madeForKids false, isAiGeneratedContent true}; text = hook line + 1–2 fact lines + question + "Follow @wealth.extreme for daily money stories." + "Not financial advice." + 5–8 hashtags + 📷 credits from `out/<id>_meta.json`; videoCoverMilliseconds 1200.
- GS → vidIQ: `vidiq_video_upload` (url) → `vidiq_social_post_draft_create` with YOUTUBE UCm-zuXXW7U16tu56ok_8Uew (title + " #Shorts", privacyStatus public, categoryId 20, tags) and INSTAGRAM 29693848623588707, each with publishAt; then `vidiq_social_post_publish` (standing approval from the user for this daily job). Slots IST: 18:30, 21:30, 00:30 (+1d). If YouTube says uploadLimitExceeded, post IG only and note it.

## 6. Log
Append one line per video to `log.md` (date, channel, id, title, slot, links) and push. Then send the user a short summary (titles + times).
