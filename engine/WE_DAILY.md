# WEALTH EXTREME — daily Shorts runbook (separate project; never mix with Gaming Sane)

Channel: Wealth Extreme (YouTube + IG @wealth.extreme). Niche: US money, business, investing, taxes, economy, billionaires, companies.
NEVER cover gaming topics (launches, consoles, game sales) — those belong to Gaming Sane. Never reuse a topic Gaming Sane covered (check log.md).
Lean: no subagents, ≤6 web searches, one QA look per video.

## Setup (every run is fresh)
```
git clone --depth 1 https://github.com/adityabakshi613-stack/shorts-media /home/claude/ws && cd /home/claude/ws
pip install --break-system-packages -q kokoro-onnx soundfile faster-whisper
mkdir -p /home/claude/models && (cd /home/claude/models && curl -sL -o kokoro.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx && curl -sL -o voices.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin)
```

## Style = the channel's established "green studio" look (see engine/ref_we_style.jpg)
- Background: the dark-green studio with grid floor (`"bg": {}`) for most beats. A blurred real photo (`{"img":"commons:...","blur":12}`) only when a brand/person/place must be recognisable (≤3 beats).
- Visuals: `card.type = "studio"` with several elements per beat (2–4): glossy Fluent 3D icons (`{"k":"icon","n":"Money bag","x","y","s","r"}` — names from github.com/microsoft/fluentui-emoji/tree/main/assets, e.g. Money bag, Coin, Dollar banknote, Money with wings, Trophy, Crown, Chart increasing, Chart decreasing, Bank, Office building, House, Automobile, Shopping cart, Package, Stopwatch, Calendar, Locked, Gem stone, Rocket, Fire, Warning, Light bulb, Brain, Robot, Globe showing americas, Busts in silhouette),
  glossy numbers (`{"k":"num","t":"$115.8B","y","s","gold":true?}`), green pills (`{"k":"pill","t":"$79.99","x","y"}`), year chips (`{"k":"chip","t":"2013"}`), 3D bars (`{"k":"bars","items":[{"label","value","num"}]}`), logo tiles (`{"k":"logo","img":"commons:X.svg","x","y","s"}`), icon grids (`{"k":"grid","icon":"Busts in silhouette","n":30,"cols":6,"y":500}`).
  Keep elements between y=380 and y=1250 (captions sit at ~1440). A new visual every ~2–3 s. Every visual must match its line.
- Voice: Kokoro am_michael (engine default). Captions: word-by-word, key words in a green box (`keys`). SFX + soft BGM automatic. Outro: original WE logo plate on "Wealth Extreme".
- Render: `python3 engine/shorts.py day/<id>.json out` (theme "we").

## Topics (3 per day)
2 trend-riding money stories from the last 24–48 h + 1 evergreen high-search money explainer; 70–80% US. Verify every number on a primary/major source. Hook = surprising number/conflict in 2 s; 35–50 s; end with a comment question. Not on log.md already.

## Publish + schedule
`bash engine/publish.sh out/WE_*.mp4` → wait ~60 s, `curl -sI` one URL = 200. Metricool brand 7870926 (Asia/Calcutta), IG REEL + YouTube short, AI labels on, slots 19:30 today, 02:30 and 08:00 tomorrow IST (check getScheduledPosts; shift 30 min if taken). Caption: hook + facts + question + "Follow @wealth.extreme for daily money stories." + "Not financial advice." + hashtags + 📷 credits from out/<id>_meta.json. YouTube title ≤70 chars, 10–15 tags, EDUCATION, videoCoverMilliseconds 1200.
Append rows to log.md (column ch = WE) and push main. SendUserMessage with titles + times.
