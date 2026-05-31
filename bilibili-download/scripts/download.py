#!/usr/bin/env python3
"""Download audio/video from Bilibili via public DASH APIs. No cookies needed."""

import argparse
import os
import re
import subprocess
import sys
import time

import requests


def get_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com/",
        }
    )
    return s


def extract_bvid(url: str) -> str:
    """Normalize any B站 URL to a bare BV ID."""
    # Already a bare BV ID
    if re.match(r"^BV[a-zA-Z0-9]{10}$", url):
        return url
    # b23.tv short link — follow redirect
    if "b23.tv" in url:
        sess = get_session()
        r = sess.head(url, allow_redirects=True, timeout=15)
        url = r.url
    # Full URL
    m = re.search(r"/video/(BV[a-zA-Z0-9]{10})", url)
    if m:
        return m.group(1)
    raise ValueError(f"Cannot extract BV ID from: {url}")


def get_video_info(session: requests.Session, bvid: str) -> dict:
    resp = session.get(
        "https://api.bilibili.com/x/web-interface/view",
        params={"bvid": bvid},
        timeout=15,
    )
    data = resp.json()
    if data["code"] != 0:
        raise RuntimeError(f"View API error: {data}")
    return data["data"]


def get_dash_streams(session: requests.Session, bvid: str, cid: int) -> dict:
    resp = session.get(
        "https://api.bilibili.com/x/player/playurl",
        params={"bvid": bvid, "cid": cid, "fnval": 4048, "fourk": 1},
        timeout=15,
    )
    data = resp.json()
    if data["code"] != 0:
        raise RuntimeError(f"PlayURL API error: {data}")
    return data["data"]["dash"]


def download_file(session: requests.Session, url: str, path: str) -> int:
    resp = session.get(url, stream=True, timeout=300)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    t0 = time.time()
    with open(path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
            downloaded += len(chunk)
    elapsed = time.time() - t0
    mb = downloaded / (1024 * 1024)
    speed = mb / elapsed if elapsed > 0 else 0
    print(f"  Downloaded: {mb:.1f} MB in {elapsed:.1f}s ({speed:.1f} MB/s)")
    return downloaded


def sanitize_filename(title: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", title).strip()


def run_ffmpeg(args: list[str], desc: str) -> None:
    print(f"  Converting ({desc})...")
    result = subprocess.run(
        ["ffmpeg", "-y", *args],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        tail = result.stderr.split("\n")[-10:]
        raise RuntimeError(f"FFmpeg failed ({desc}):\n" + "\n".join(tail))


def main():
    parser = argparse.ArgumentParser(description="Download Bilibili video/audio")
    parser.add_argument("url", help="Bilibili URL or BV ID")
    parser.add_argument(
        "--mode",
        choices=["audio-only", "video-only", "full"],
        default="full",
        help="Download mode (default: full)",
    )
    parser.add_argument(
        "--outdir",
        default=os.getcwd(),
        help="Output directory (default: current dir)",
    )
    args = parser.parse_args()

    session = get_session()

    # Step 1: Extract BV ID
    bvid = extract_bvid(args.url)
    print(f"BV ID: {bvid}")

    # Step 2: Get video info
    info = get_video_info(session, bvid)
    title = sanitize_filename(info["title"])
    cid = info["cid"]
    print(f"Title: {title}")
    print(f"CID: {cid}")

    # Step 3: Get DASH streams
    dash = get_dash_streams(session, bvid, cid)

    os.makedirs(args.outdir, exist_ok=True)

    if args.mode == "audio-only":
        audios = dash.get("audio", [])
        if not audios:
            print("ERROR: No audio streams found", file=sys.stderr)
            sys.exit(1)
        best = max(audios, key=lambda a: a.get("bandwidth", 0))
        print(
            f"Audio: ID={best['id']}, {best.get('bandwidth', '?')}bps, "
            f"codec={best.get('codecs', '?')}"
        )
        m4s = os.path.join(args.outdir, f"{title}.audio.m4s")
        download_file(session, best["baseUrl"], m4s)
        out = os.path.join(args.outdir, f"{title}.mp3")
        run_ffmpeg(
            ["-i", m4s, "-vn", "-acodec", "libmp3lame", "-q:a", "2", out],
            "audio m4s → mp3",
        )
        os.remove(m4s)
        print(f"Done → {out}")

    elif args.mode == "video-only":
        videos = dash.get("video", [])
        if not videos:
            print("ERROR: No video streams found", file=sys.stderr)
            sys.exit(1)
        best = max(videos, key=lambda v: v.get("bandwidth", 0))
        print(
            f"Video: ID={best['id']}, {best.get('bandwidth', '?')}bps, "
            f"codec={best.get('codecs', '?')}, "
            f"{best.get('width', '?')}x{best.get('height', '?')}"
        )
        m4s = os.path.join(args.outdir, f"{title}.video.m4s")
        download_file(session, best["baseUrl"], m4s)
        out = os.path.join(args.outdir, f"{title}.mp4")
        run_ffmpeg(["-i", m4s, "-c", "copy", out], "video m4s → mp4 (copy)")
        os.remove(m4s)
        print(f"Done → {out}")

    else:  # full
        audios = dash.get("audio", [])
        videos = dash.get("video", [])
        if not audios or not videos:
            print("ERROR: Missing streams for full download", file=sys.stderr)
            sys.exit(1)

        best_audio = max(audios, key=lambda a: a.get("bandwidth", 0))
        best_video = max(videos, key=lambda v: v.get("bandwidth", 0))
        print(
            f"Video: ID={best_video['id']}, {best_video.get('bandwidth', '?')}bps, "
            f"{best_video.get('width', '?')}x{best_video.get('height', '?')}"
        )
        print(
            f"Audio: ID={best_audio['id']}, {best_audio.get('bandwidth', '?')}bps"
        )

        video_m4s = os.path.join(args.outdir, f"{title}.video.m4s")
        audio_m4s = os.path.join(args.outdir, f"{title}.audio.m4s")

        print("  → Video stream:")
        download_file(session, best_video["baseUrl"], video_m4s)
        print("  → Audio stream:")
        download_file(session, best_audio["baseUrl"], audio_m4s)

        out = os.path.join(args.outdir, f"{title}.mp4")
        run_ffmpeg(
            ["-i", video_m4s, "-i", audio_m4s, "-c", "copy", out],
            "merge video + audio → mp4",
        )
        os.remove(video_m4s)
        os.remove(audio_m4s)
        print(f"Done → {out}")


if __name__ == "__main__":
    main()
