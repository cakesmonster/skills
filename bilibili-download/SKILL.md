---
name: bilibili-download
description: "Use when user wants to download audio or video from Bilibili (bilibili.com). Extracts DASH audio/video streams via public APIs — no cookies needed. Supports audio-only (mp3), video-only (mp4, no audio track), and merged full video."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [bilibili, download, video, audio, media]
    related_skills: [youtube-content]
---

# Bilibili Audio/Video Downloader

## Overview

Downloads audio and video from Bilibili (bilibili.com) by calling public B站 APIs directly — no cookies, no login, no yt-dlp workarounds. B站 serves content as DASH streams where audio and video are separate `.m4s` files. This skill fetches the stream URLs via API, downloads the `.m4s`, and uses ffmpeg to convert to standard formats.

## When to Use

- User shares a B站 link (bilibili.com/video/BVxxxxxx, b23.tv, etc.) and asks to download
- User wants audio-only extraction from B站 (podcast, music, lectures)
- User wants a local copy of a B站 video

## Prerequisites

- `ffmpeg` (tested with 7.0+)
- Python 3 with `requests` (stdlib on most distros)

No other dependencies. No cookies, no browser, no login.

## Workflow

### Step 1: Extract BV ID

Normalize any B站 URL to the bare BV ID. The script handles:
- `https://www.bilibili.com/video/BV13T411J7qQ`
- `https://b23.tv/xxxxx`
- `BV13T411J7qQ`

### Step 2: Fetch video info + DASH streams

```bash
python3 SKILL_DIR/scripts/download.py "BV13T411J7qQ" --audio-only
```

**Modes:**

| Flag | Output | Behavior |
|------|--------|----------|
| `--audio-only` | `.mp3` | Downloads best audio stream (highest bandwidth), converts m4s → mp3 |
| `--video-only` | `.mp4` (no audio) | Downloads best video stream, remuxes m4s → mp4 |
| `--full` (default) | `.mp4` (with audio) | Downloads best video + best audio, merges with ffmpeg |

### Step 3: The script does

1. `GET https://api.bilibili.com/x/web-interface/view?bvid=<bvid>` → gets `title` and `cid`
2. `GET https://api.bilibili.com/x/player/playurl?bvid=<bvid>&cid=<cid>&fnval=4048&fourk=1` → gets DASH stream URLs
3. Downloads the selected `.m4s` stream(s) with proper `User-Agent` and `Referer` headers
4. Converts via ffmpeg:
   - Audio: `ffmpeg -i input.m4s -vn -acodec libmp3lame -q:a 2 output.mp3`
   - Video (no audio): `ffmpeg -i input.m4s -c copy output.mp4`
   - Full (merge): `ffmpeg -i video.m4s -i audio.m4s -c copy output.mp4`
5. Cleans up intermediate `.m4s` files

### Output

Files saved to current working directory (or `--outdir /path/to/dir`). Filename is the sanitized video title.

## One-Shot Recipes

### Download audio only (for podcasts, lectures, music)

```bash
python3 SKILL_DIR/scripts/download.py "https://www.bilibili.com/video/BV13T411J7qQ" --audio-only
```

### Download full video with audio

```bash
python3 SKILL_DIR/scripts/download.py "BV13T411J7qQ" --full
```

### Download to specific directory

```bash
python3 SKILL_DIR/scripts/download.py "BV13T411J7qQ" --audio-only --outdir /root/music/
```

## Common Pitfalls

1. **yt-dlp 412 error**: B站's CDN returns HTTP 412 to block yt-dlp's default UA. This skill bypasses it by using a browser-like User-Agent and the official public APIs. Don't bother with yt-dlp for B站.

2. **Missing ffmpeg**: The downloaded `.m4s` is in fragmented MP4 container. Without ffmpeg you can't convert it. Install via `apt install ffmpeg` or download a static build.

3. **DASH + hvc1 codec**: Some 4K videos use `hvc1` (HEVC) codec. ffmpeg's `-c copy` remux for video-only mode may fail if the player doesn't support HEVC in MP4. For problematic codecs, re-encode with `-c:v libx264` instead of `-c copy`.

4. **b23.tv short links**: The script resolves redirects automatically. If it fails, curl `-L` the short link to get the final URL first.

5. **Audio quality**: The script picks the highest-bandwidth audio stream automatically. B站 typically offers 3 tiers (~67kbps, ~125kbps, ~302kbps for premium). The script takes the best available without login.

## Verification Checklist

- [ ] `ffmpeg -version` returns 7.0+
- [ ] BV ID extracted correctly from user's URL
- [ ] API responses return `code: 0` (not blocked or geo-restricted)
- [ ] Downloaded file has non-zero size
- [ ] Audio playback works, no corruption
