#!/usr/bin/env python3
"""
Founders Brain — run.py
Scrapes every Founders Podcast episode → structures with Claude → uploads to Google Drive.

SETUP (one time):
  pip install yt-dlp youtube-transcript-api anthropic google-api-python-client google-auth-oauthlib
  export ANTHROPIC_API_KEY=sk-ant-...
  Place credentials.json (Google Cloud OAuth) in this folder.

RUN:
  python3 run.py            # full run
  python3 run.py --resume   # skip already-uploaded founders
  python3 run.py --limit 3  # test with 3 episodes
"""

import os, re, json, time, sys, argparse, subprocess
from pathlib import Path
from datetime import datetime

# ── Google Drive ──────────────────────────────────────────────────────────────
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_NAME = "Founders Brain"

# ── Config ────────────────────────────────────────────────────────────────────
CHANNEL_URL  = "https://www.youtube.com/@founderspodcast1/videos"
API_KEY      = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL        = "claude-haiku-4-5-20251001"
SLEEP        = 2
HERE         = Path(__file__).parent
PROGRESS     = HERE / ".progress.json"

EXTRACT_PROMPT = """\
Extract structured insights from this Founders Podcast transcript.
Return ONLY valid JSON — no markdown, no commentary.

{
  "figure": "Full name",
  "key_decisions": ["3-5 pivotal choices with context of why and when"],
  "mental_models": ["2-4 core frameworks they used to think"],
  "operating_principles": ["3-5 daily rules or habits"],
  "turning_points": ["2-3 moments that changed everything"],
  "pressure_response": ["2-3 specific crises and exactly how they responded"],
  "no_playbook_build": ["2-3 ways they built with zero precedent"],
  "top_insight": "Single most useful insight in one sentence"
}

Transcript:
"""

# ── Google Drive auth ─────────────────────────────────────────────────────────

def get_drive_service():
    creds = None
    token_path = HERE / "token.json"
    creds_path = HERE / "credentials.json"

    if not creds_path.exists():
        print("ERROR: credentials.json not found.")
        print("  1. Go to console.cloud.google.com")
        print("  2. Create project → Enable Drive API → Create OAuth 2.0 credentials (Desktop app)")
        print("  3. Download as credentials.json → place in this folder")
        sys.exit(1)

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return build("drive", "v3", credentials=creds)


def get_or_create_folder(service, name: str) -> str:
    """Return folder ID, creating it if needed."""
    q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=q, fields="files(id)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    folder = service.files().create(body=meta, fields="id").execute()
    return folder["id"]


def upload_doc(service, folder_id: str, name: str, content: str) -> str:
    """Upload or update a Google Doc. Returns the file URL."""
    q = f"name='{name}' and '{folder_id}' in parents and trashed=false"
    existing = service.files().list(q=q, fields="files(id)").execute().get("files", [])

    media = MediaInMemoryUpload(content.encode("utf-8"), mimetype="text/plain", resumable=False)

    if existing:
        file_id = existing[0]["id"]
        service.files().update(fileId=file_id, media_body=media).execute()
    else:
        meta = {"name": name, "parents": [folder_id]}
        file_id = service.files().create(body=meta, media_body=media, fields="id").execute()["id"]

    return f"https://drive.google.com/file/d/{file_id}/view"


# ── YouTube ───────────────────────────────────────────────────────────────────

def get_videos() -> list[dict]:
    print("Fetching video list...")
    cmd = ["yt-dlp", "--flat-playlist", "--print", "%(id)s\t%(title)s", "--no-warnings", CHANNEL_URL]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        print(f"yt-dlp failed: {r.stderr[:200]}")
        sys.exit(1)
    videos = []
    for line in r.stdout.strip().splitlines():
        if "\t" not in line:
            continue
        vid_id, title = line.split("\t", 1)
        videos.append({"id": vid_id, "title": title})
    print(f"  {len(videos)} episodes found")
    return videos


def get_transcript(vid_id: str) -> str | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        entries = YouTubeTranscriptApi.get_transcript(vid_id)
        return " ".join(e["text"] for e in entries)
    except Exception as e:
        print(f"  No transcript: {e}")
        return None


def extract_name(title: str) -> str:
    name = re.sub(r"^#?\d+[\s.\-:]+", "", title).strip()
    name = re.sub(r"\s*\(.*\)$", "", name).strip()
    name = re.sub(r"\s*[-–|:].*$", "", name).strip()
    return name or title


# ── Claude extraction ─────────────────────────────────────────────────────────

def extract(name: str, transcript: str) -> dict:
    if not API_KEY:
        return _empty(name)
    import anthropic
    client = anthropic.Anthropic(api_key=API_KEY)
    try:
        r = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": EXTRACT_PROMPT + transcript[:80_000]}]
        )
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", r.content[0].text.strip())
        data = json.loads(raw)
        data["figure"] = data.get("figure") or name
        return data
    except Exception as e:
        print(f"  Extraction error: {e}")
        return _empty(name)


def _empty(name: str) -> dict:
    return {"figure": name, "top_insight": "", "key_decisions": [], "mental_models": [],
            "operating_principles": [], "turning_points": [], "pressure_response": [], "no_playbook_build": []}


# ── Format for Drive/AI ───────────────────────────────────────────────────────

def to_doc(d: dict, url: str) -> str:
    """Plain text doc optimised for pasting into any AI session."""
    lines = [
        f"FOUNDER: {d['figure']}",
        f"SOURCE: {url}",
        f"EXTRACTED: {datetime.now().strftime('%Y-%m-%d')}",
        "",
    ]
    if d.get("top_insight"):
        lines += [f"TOP INSIGHT: {d['top_insight']}", ""]

    sections = [
        ("KEY DECISIONS", "key_decisions"),
        ("MENTAL MODELS", "mental_models"),
        ("OPERATING PRINCIPLES", "operating_principles"),
        ("TURNING POINTS", "turning_points"),
        ("PRESSURE RESPONSE", "pressure_response"),
        ("NO-PLAYBOOK BUILD", "no_playbook_build"),
    ]
    for heading, key in sections:
        items = d.get(key, [])
        if items:
            lines.append(f"── {heading} ──")
            for item in items:
                lines.append(f"• {item}")
            lines.append("")

    return "\n".join(lines)


def to_index_row(d: dict, url: str) -> dict:
    return {
        "name": d["figure"],
        "top_insight": d.get("top_insight", ""),
        "mental_models": d.get("mental_models", [])[:2],
        "url": url,
    }


# ── Progress ──────────────────────────────────────────────────────────────────

def load_progress() -> dict:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text())
    return {"done": {}, "failed": []}


def save_progress(p: dict):
    PROGRESS.write_text(json.dumps(p, indent=2))


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if not API_KEY:
        print("WARNING: ANTHROPIC_API_KEY not set. Transcripts will be saved without extraction.")

    print("Connecting to Google Drive...")
    service = get_drive_service()
    folder_id = get_or_create_folder(service, FOLDER_NAME)
    print(f"  Folder ready: {FOLDER_NAME}")

    videos = get_videos()
    if args.limit:
        videos = videos[:args.limit]

    progress = load_progress()
    done_ids = set(progress["done"].keys()) if args.resume else set()
    to_process = [v for v in videos if v["id"] not in done_ids]
    print(f"  Processing: {len(to_process)} | Skipping: {len(done_ids)}\n")

    index_rows = list(progress["done"].values()) if args.resume else []

    for i, video in enumerate(to_process, 1):
        vid_id = video["id"]
        name = extract_name(video["title"])
        yt_url = f"https://www.youtube.com/watch?v={vid_id}"
        print(f"[{i}/{len(to_process)}] {name}")

        transcript = get_transcript(vid_id)
        if not transcript:
            progress["failed"].append(vid_id)
            save_progress(progress)
            time.sleep(SLEEP)
            continue

        data = extract(name, transcript)
        doc_content = to_doc(data, yt_url)

        # Sanitize filename for Drive
        safe_name = re.sub(r"[^\w\s\-]", "", name).strip()[:80]
        drive_url = upload_doc(service, folder_id, safe_name, doc_content)

        row = to_index_row(data, drive_url)
        index_rows.append(row)
        progress["done"][vid_id] = row
        save_progress(progress)

        print(f"  → {drive_url}")
        time.sleep(SLEEP)

    # Build index doc
    index_lines = [
        "FOUNDERS BRAIN — INDEX",
        f"Total: {len(index_rows)} founders",
        f"Updated: {datetime.now().strftime('%Y-%m-%d')}",
        "",
        "── FOUNDERS ──",
        "",
    ]
    for r in sorted(index_rows, key=lambda x: x["name"]):
        index_lines.append(f"{r['name']}")
        if r.get("top_insight"):
            index_lines.append(f"  → {r['top_insight']}")
        if r.get("mental_models"):
            index_lines.append(f"  Models: {', '.join(r['mental_models'][:2])}")
        index_lines.append(f"  {r['url']}")
        index_lines.append("")

    upload_doc(service, folder_id, "_INDEX", "\n".join(index_lines))

    print("\n" + "="*50)
    print(f"DONE: {len(index_rows)} founders in Google Drive → '{FOLDER_NAME}'")
    if progress["failed"]:
        print(f"Failed (no transcript): {len(progress['failed'])} episodes")
    print("="*50)


if __name__ == "__main__":
    main()
