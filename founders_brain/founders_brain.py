#!/usr/bin/env python3
"""
Founders Brain - Build a queryable knowledge base from Founders Podcast
Scrapes transcripts, extracts structured insights, saves to disk.
Run: python3 founders_brain.py
Resume after interruption: python3 founders_brain.py --resume
"""

import os
import json
import time
import re
import subprocess
import sys
import argparse
from pathlib import Path
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
CHANNEL_URL = "https://www.youtube.com/@founderspodcast1"
BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "raw"
STRUCTURED_DIR = BASE_DIR / "structured"
MARKDOWN_DIR = BASE_DIR / "markdown"
INDEX_FILE = BASE_DIR / "INDEX.json"
PROGRESS_FILE = BASE_DIR / ".progress.json"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
BATCH_SIZE = 5          # Process N transcripts before saving progress
SLEEP_BETWEEN = 2       # Seconds between YouTube requests
MODEL = "claude-haiku-4-5-20251001"   # Fast + cheap for bulk extraction

EXTRACTION_PROMPT = """You are extracting structured insights from a Founders Podcast episode transcript.

Extract ONLY what is explicitly stated or clearly implied in the transcript. No hallucination.

Return valid JSON matching this exact schema:
{
  "figure": "Full name of the entrepreneur/founder",
  "key_decisions": [
    "3-5 pivotal choices with context of why and when they made them"
  ],
  "mental_models": [
    "2-4 core frameworks or thinking tools they used"
  ],
  "operating_principles": [
    "3-5 daily rules, habits, or working principles they followed"
  ],
  "turning_points": [
    "2-3 moments that completely changed their trajectory"
  ],
  "pressure_response": [
    "2-3 specific crises or high-stakes moments and exactly how they responded"
  ],
  "no_playbook_build": [
    "2-3 ways they built something with no precedent or existing map to follow"
  ],
  "top_insight": "Single most memorable/useful insight from this founder in one sentence"
}

Transcript:
"""

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text())
    return {"done": [], "failed": []}


def save_progress(progress: dict):
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))


def slug(name: str) -> str:
    """Convert founder name to safe filename."""
    return re.sub(r"[^\w]", "_", name).strip("_")


# ── Step 1: Get video list ─────────────────────────────────────────────────────

def get_video_list() -> list[dict]:
    """Use yt-dlp to fetch all video IDs and titles from the channel."""
    log("Fetching video list from channel (this takes ~60s)...")
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--print", "%(id)s\t%(title)s",
        "--no-warnings",
        f"{CHANNEL_URL}/videos",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        log(f"yt-dlp error: {result.stderr[:300]}")
        return []

    videos = []
    for line in result.stdout.strip().splitlines():
        if "\t" not in line:
            continue
        vid_id, title = line.split("\t", 1)
        videos.append({"id": vid_id, "title": title, "url": f"https://www.youtube.com/watch?v={vid_id}"})

    log(f"Found {len(videos)} videos")
    return videos


def extract_founder_name(title: str) -> str:
    """Pull founder name from title like '#154 Charlie Munger (Poor Charlie's Almanack)'."""
    # Remove episode number prefix like #154, 154., etc.
    name = re.sub(r"^#?\d+[\s\.\-:]+", "", title).strip()
    # Remove parenthetical suffixes
    name = re.sub(r"\s*\(.*\)$", "", name).strip()
    # Remove book name suffixes after common separators
    name = re.sub(r"\s*[-–|:]+.*$", "", name).strip()
    return name or title


# ── Step 2: Fetch transcripts ─────────────────────────────────────────────────

def get_transcript(video_id: str) -> str | None:
    """Fetch transcript using youtube-transcript-api."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        entries = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join(e["text"] for e in entries)
    except Exception as e:
        log(f"  Transcript error for {video_id}: {e}")
        return None


# ── Step 3: Extract insights with Claude ──────────────────────────────────────

def extract_insights(founder_name: str, transcript: str) -> dict | None:
    """Send transcript to Claude and get structured JSON back."""
    if not ANTHROPIC_API_KEY:
        log("  No ANTHROPIC_API_KEY set — skipping LLM extraction. Raw transcript saved.")
        return None

    import anthropic
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Truncate transcript to ~80k chars to stay within context limits
    truncated = transcript[:80_000]

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            messages=[{
                "role": "user",
                "content": EXTRACTION_PROMPT + truncated
            }]
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        data["figure"] = data.get("figure") or founder_name
        return data
    except json.JSONDecodeError as e:
        log(f"  JSON parse error: {e}")
        return None
    except Exception as e:
        log(f"  Claude API error: {e}")
        return None


# ── Step 4: Write outputs ─────────────────────────────────────────────────────

def save_raw(founder_name: str, url: str, transcript: str):
    path = RAW_DIR / f"{slug(founder_name)}.txt"
    path.write_text(f"FOUNDER: {founder_name}\nURL: {url}\n\n{transcript}")


def save_structured(data: dict):
    path = STRUCTURED_DIR / f"{slug(data['figure'])}.json"
    path.write_text(json.dumps(data, indent=2))


def save_markdown(data: dict):
    name = data["figure"]
    lines = [f"# {name}\n"]
    sections = [
        ("Key Decisions", "key_decisions"),
        ("Mental Models", "mental_models"),
        ("Operating Principles", "operating_principles"),
        ("Turning Points", "turning_points"),
        ("Pressure Response", "pressure_response"),
        ("No-Playbook Build", "no_playbook_build"),
    ]
    for heading, key in sections:
        items = data.get(key, [])
        if items:
            lines.append(f"## {heading}")
            for item in items:
                lines.append(f"- {item}")
            lines.append("")

    if data.get("top_insight"):
        lines.append(f"## Top Insight\n> {data['top_insight']}\n")

    path = MARKDOWN_DIR / f"{slug(name)}.md"
    path.write_text("\n".join(lines))


def build_index(all_data: list[dict]):
    index = {
        "total_founders": len(all_data),
        "created": datetime.now().strftime("%Y-%m-%d"),
        "founders": [
            {
                "name": d["figure"],
                "top_insight": d.get("top_insight", ""),
                "mental_models": d.get("mental_models", [])[:2],
                "file": f"markdown/{slug(d['figure'])}.md",
            }
            for d in all_data
        ]
    }
    INDEX_FILE.write_text(json.dumps(index, indent=2))
    log(f"Index written: {len(all_data)} founders")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", action="store_true", help="Skip already-processed videos")
    parser.add_argument("--limit", type=int, default=0, help="Only process N videos (for testing)")
    parser.add_argument("--no-llm", action="store_true", help="Save raw transcripts only, skip Claude")
    args = parser.parse_args()

    if args.no_llm:
        global ANTHROPIC_API_KEY
        ANTHROPIC_API_KEY = ""

    progress = load_progress()
    done_ids = set(progress["done"])

    # Step 1: get video list
    videos = get_video_list()
    if not videos:
        log("No videos found. Check your internet connection.")
        sys.exit(1)

    if args.limit:
        videos = videos[:args.limit]

    to_process = [v for v in videos if v["id"] not in done_ids] if args.resume else videos
    log(f"Videos to process: {len(to_process)} (skipping {len(done_ids)} already done)")

    all_data = []
    batch_count = 0

    for i, video in enumerate(to_process, 1):
        vid_id = video["id"]
        title = video["title"]
        founder = extract_founder_name(title)
        log(f"[{i}/{len(to_process)}] {founder} — {title}")

        # Skip if raw file already exists (partial resume)
        raw_path = RAW_DIR / f"{slug(founder)}.txt"
        if raw_path.exists() and args.resume:
            log("  Raw exists, reloading...")
            transcript = raw_path.read_text().split("\n\n", 2)[-1]
        else:
            transcript = get_transcript(vid_id)
            if not transcript:
                progress["failed"].append(vid_id)
                save_progress(progress)
                time.sleep(SLEEP_BETWEEN)
                continue
            save_raw(founder, video["url"], transcript)

        # Extract insights
        data = extract_insights(founder, transcript)

        if data:
            save_structured(data)
            save_markdown(data)
            all_data.append(data)
            log(f"  Extracted: {len(data.get('key_decisions', []))} decisions, {len(data.get('mental_models', []))} models")
        else:
            # Save a minimal entry so the index still includes this founder
            minimal = {"figure": founder, "top_insight": "", "key_decisions": [],
                       "mental_models": [], "operating_principles": [],
                       "turning_points": [], "pressure_response": [], "no_playbook_build": []}
            save_structured(minimal)
            save_markdown(minimal)
            all_data.append(minimal)

        progress["done"].append(vid_id)
        batch_count += 1

        if batch_count >= BATCH_SIZE:
            save_progress(progress)
            build_index(all_data)
            log(f"  --- Progress saved ({len(progress['done'])} total done) ---")
            batch_count = 0

        time.sleep(SLEEP_BETWEEN)

    # Final index + report
    save_progress(progress)
    build_index(all_data)

    print("\n" + "="*50)
    print("BRAIN BUILT")
    print("="*50)
    print(f"Founders processed : {len(progress['done'])}")
    print(f"Failed             : {len(progress['failed'])}")
    print(f"JSON files         : {len(list(STRUCTURED_DIR.glob('*.json')))}")
    print(f"Markdown files     : {len(list(MARKDOWN_DIR.glob('*.md')))}")
    print(f"Location           : {BASE_DIR}")
    if progress["failed"]:
        print(f"\nFailed video IDs (no transcript available):")
        for fid in progress["failed"]:
            print(f"  https://www.youtube.com/watch?v={fid}")
    print("\nNext: open QUERY.md to learn how to use your brain")


if __name__ == "__main__":
    main()
