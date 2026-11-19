# GAMING SANE — daily Shorts runbook (separate project; never mix with Wealth Extreme)

Channel: Gaming Sane (YouTube UCm-zuXXW7U16tu56ok_8Uew + IG @gamingsane_studios, account 29693848623588707). Niche: gaming news.
NEVER make money/business/finance videos and never reuse a topic Wealth Extreme covered (check log.md). Never use the Wealth Extreme engine (shorts.py) or its green studio look.
Lean: no subagents, ≤6 web searches, one QA look per video. Follows the gaming-shorts-pipeline skill's rules (hook < 1.5 s, cut every 1.5–3 s, 25–45 s, loop line, facts sourced, no spoilers/18+).

## Setup
```
git clone --depth 1 https://github.com/adityabakshi613-stack/shorts-media /home/claude/ws && cd /home/claude/ws
pip install --break-system-packages -q edge-tts
```

## Style = the channel's established footage look (see engine/ref_gs_style.jpg)
- Real gameplay/trailer footage: each beat shows a clip in a rounded card over a blurred copy of the same clip; big extruded red/white numbers above the card (`"num"`); single-word UPPERCASE captions, key words in a red box (`keys`); RGB-glitch on some cuts (`"glitch": true`); edge-tts Andrew voice +8%; whoosh SFX + music bed; Gaming Sane logo outro (engine/logo_gs.png, the slanted cyan/pink GS) on "Gaming Sane".
- Footage: for each story take the OFFICIAL trailer/gameplay video (publisher's channel). Import it with `vidiq_video_upload(url=<YouTube link>)` → poll `vidiq_job_poll` → download `videoUrl` with curl into src/<name>.mp4 (YouTube blocks yt-dlp here). Make a contact sheet of the source (`ffmpeg -vf fps=1/4,scale=192:-1,tile=6x5`) and pick timestamps that match each line. Twitch/Kick clips via yt-dlp also work. Still images only if no footage exists (`"clip":{"img":"commons:..."}`).
- Credit footage in the caption ("Footage: Rockstar Games").
- Spec: `{"id","sources":{"t1":"src/x.mp4"},"credit","beats":[{"say","clip":{"src":"t1","t":12.0},"num"?,"keys":[..],"glitch"?}],"outro_say":"Follow Gaming Sane for daily gaming news."}` — 9–12 beats, one short sentence each, numbers as digits.
- Render: `python3 engine/gs_shorts.py day/<id>.json out`. QA: read out/<id>_sheet.jpg once.

## Topics (3 per day)
The day's most-talked gaming stories (launches, reveals, confirmed leaks, records, prices, delays, big updates) from reliable outlets; rumors labelled as rumors.

## Publish + schedule (standing user approval)
`bash engine/publish.sh out/GS_*.mp4` → wait ~60 s → per video: `vidiq_video_upload(url=raw URL)` → `vidiq_social_post_draft_create` (YOUTUBE: title + " #Shorts", privacyStatus public, categoryId 20, 8–12 tags, publishAt; INSTAGRAM: publishAt) → if pacing, update to suggestedPublishAt and resend the YouTube publishAt in the same update → `vidiq_social_post_publish`. Slots IST 18:30, 21:30 today, 00:30 tomorrow. Check one with vidiq_social_post_status; if YouTube uploadLimitExceeded, keep IG and report.
Append rows to log.md (ch = GS) and push main. SendUserMessage with titles + times.
