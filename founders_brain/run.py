#!/usr/bin/env python3
"""
Founders Brain — run.py
Reads YTBSD transcript output → Claude extraction → Google Drive.

PIPELINE:
  Step 1 (YTBSD):  Download all transcripts from Founders Podcast
    git clone https://github.com/roundyyy/yt-bulk-subtitles-downloader
    cd yt-bulk-subtitles-downloader && pip install -r requirements.txt
    python ytbsd.py  →  select Channel → paste URL → choose Markdown format
    # Output: subtitles/subtitles.md  (all 229 transcripts in one file)

  Step 2 (this script):  Extract + upload to Google Drive
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 run.py --input subtitles/subtitles.md
    python3 run.py --input subtitles/subtitles.md --resume   # if interrupted

GOOGLE DRIVE SETUP (one time):
  1. console.cloud.google.com → New project → Enable Drive API
  2. Create OAuth 2.0 credentials (Desktop app) → download as credentials.json
  3. Place credentials.json in same folder as this script
"""

import os, re, json, time, sys, argparse
from pathlib import Path
from datetime import datetime

# ── Google Drive ──────────────────────────────────────────────────────────────
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaInMemoryUpload

SCOPES      = ["https://www.googleapis.com/auth/drive.file"]
FOLDER_NAME = "Founders Brain"
API_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL       = "claude-haiku-4-5-20251001"
HERE        = Path(__file__).parent
PROGRESS    = HERE / ".progress.json"

EXTRACT_PROMPT = """\
Extract structured insights from this Founders Podcast transcript.
Return ONLY valid JSON — no markdown fences, no commentary.

{
  "figure": "Full name of the founder/entrepreneur",
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

# ── Google Drive ──────────────────────────────────────────────────────────────

def drive_service():
    creds, token_path, creds_path = None, HERE / "token.json", HERE / "credentials.json"
    if not creds_path.exists():
        print("ERROR: credentials.json missing.\n"
              "  console.cloud.google.com → Enable Drive API → OAuth 2.0 (Desktop) → download → rename to credentials.json")
        sys.exit(1)
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            creds = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES).run_local_server(port=0)
        token_path.write_text(creds.to_json())
    return build("drive", "v3", credentials=creds)


def get_or_create_folder(svc, name: str) -> str:
    q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    files = svc.files().list(q=q, fields="files(id)").execute().get("files", [])
    if files:
        return files[0]["id"]
    return svc.files().create(
        body={"name": name, "mimeType": "application/vnd.google-apps.folder"}, fields="id"
    ).execute()["id"]


def upload(svc, folder_id: str, name: str, content: str) -> str:
    q = f"name='{name}' and '{folder_id}' in parents and trashed=false"
    existing = svc.files().list(q=q, fields="files(id)").execute().get("files", [])
    media = MediaInMemoryUpload(content.encode("utf-8"), mimetype="text/plain")
    if existing:
        file_id = existing[0]["id"]
        svc.files().update(fileId=file_id, media_body=media).execute()
    else:
        file_id = svc.files().create(
            body={"name": name, "parents": [folder_id]}, media_body=media, fields="id"
        ).execute()["id"]
    return f"https://drive.google.com/file/d/{file_id}/view"


# ── Parse YTBSD markdown output ───────────────────────────────────────────────

def parse_ytbsd_markdown(md_path: Path) -> list[dict]:
    """
    YTBSD markdown format:
      # Table of Contents
      - [Video Title](#anchor)
      ...
      # Video Title
      transcript text...
      # Another Video Title
      ...
    Returns list of {title, transcript}.
    """
    text = md_path.read_text(encoding="utf-8", errors="replace")

    # Split on H1 headings
    sections = re.split(r"\n# ", text)

    entries = []
    for sec in sections[1:]:  # skip everything before first #
        lines = sec.strip().splitlines()
        if not lines:
            continue
        title = lines[0].strip()
        # Skip table of contents section
        if title.lower() in ("table of contents", "contents"):
            continue
        transcript = " ".join(lines[1:]).strip()
        if len(transcript) < 100:  # skip empty/stub entries
            continue
        entries.append({"title": title, "transcript": transcript})

    return entries


def parse_ytbsd_srt_folder(srt_dir: Path) -> list[dict]:
    """Fallback: read individual .srt or .md files from a folder."""
    entries = []
    for f in sorted(srt_dir.glob("*.md")) or sorted(srt_dir.glob("*.srt")):
        text = f.read_text(encoding="utf-8", errors="replace")
        # Strip SRT timestamps
        text = re.sub(r"\d+\n\d{2}:\d{2}:\d{2},\d+ --> \d{2}:\d{2}:\d{2},\d+\n", "", text)
        entries.append({"title": f.stem, "transcript": text.strip()})
    return entries


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


# ── Format for AI querying ────────────────────────────────────────────────────

def to_doc(d: dict, source_title: str) -> str:
    lines = [
        f"FOUNDER: {d['figure']}",
        f"EPISODE: {source_title}",
        f"EXTRACTED: {datetime.now().strftime('%Y-%m-%d')}",
        "",
    ]
    if d.get("top_insight"):
        lines += [f"TOP INSIGHT: {d['top_insight']}", ""]
    for heading, key in [
        ("KEY DECISIONS",       "key_decisions"),
        ("MENTAL MODELS",       "mental_models"),
        ("OPERATING PRINCIPLES","operating_principles"),
        ("TURNING POINTS",      "turning_points"),
        ("PRESSURE RESPONSE",   "pressure_response"),
        ("NO-PLAYBOOK BUILD",   "no_playbook_build"),
    ]:
        items = d.get(key, [])
        if items:
            lines += [f"── {heading} ──"] + [f"• {x}" for x in items] + [""]
    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True,
                    help="Path to YTBSD output: subtitles.md file OR folder of .srt/.md files")
    ap.add_argument("--resume", action="store_true", help="Skip already-uploaded founders")
    ap.add_argument("--limit",  type=int, default=0, help="Process only N entries (for testing)")
    args = ap.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: {input_path} not found.")
        sys.exit(1)

    # Parse YTBSD output
    if input_path.is_file():
        print(f"Parsing markdown: {input_path}")
        entries = parse_ytbsd_markdown(input_path)
    else:
        print(f"Parsing folder: {input_path}")
        entries = parse_ytbsd_srt_folder(input_path)

    print(f"  {len(entries)} transcripts found")

    if args.limit:
        entries = entries[:args.limit]

    # Drive setup
    print("Connecting to Google Drive...")
    svc = drive_service()
    folder_id = get_or_create_folder(svc, FOLDER_NAME)
    print(f"  Ready: '{FOLDER_NAME}' folder")

    progress = json.loads(PROGRESS.read_text()) if PROGRESS.exists() else {"done": {}, "failed": []}
    done_titles = set(progress["done"].keys()) if args.resume else set()
    index_rows = list(progress["done"].values()) if args.resume else []

    to_process = [e for e in entries if e["title"] not in done_titles]
    print(f"  Processing: {len(to_process)} | Skipping: {len(done_titles)}\n")

    for i, entry in enumerate(to_process, 1):
        title = entry["title"]
        name  = extract_name(title)
        print(f"[{i}/{len(to_process)}] {name}")

        data = extract(name, entry["transcript"])
        doc  = to_doc(data, title)
        safe = re.sub(r"[^\w\s\-]", "", name).strip()[:80]

        drive_url = upload(svc, folder_id, safe, doc)
        row = {"name": data["figure"], "top_insight": data.get("top_insight", ""),
               "mental_models": data.get("mental_models", [])[:2], "url": drive_url}

        index_rows.append(row)
        progress["done"][title] = row
        PROGRESS.write_text(json.dumps(progress, indent=2))
        print(f"  → {drive_url}")
        time.sleep(1)

    # Index doc
    idx = ["FOUNDERS BRAIN — INDEX",
           f"Total: {len(index_rows)} founders",
           f"Updated: {datetime.now().strftime('%Y-%m-%d')}", "", "── FOUNDERS ──", ""]
    for r in sorted(index_rows, key=lambda x: x["name"]):
        idx.append(r["name"])
        if r.get("top_insight"):  idx.append(f"  → {r['top_insight']}")
        if r.get("mental_models"): idx.append(f"  Models: {', '.join(r['mental_models'][:2])}")
        idx.append(f"  {r['url']}")
        idx.append("")

    upload(svc, folder_id, "_INDEX", "\n".join(idx))

    print(f"\n{'='*50}")
    print(f"DONE: {len(index_rows)} founders → Google Drive '{FOLDER_NAME}'")
    if progress["failed"]:
        print(f"Failed: {len(progress['failed'])}")
    print("="*50)


if __name__ == "__main__":
    main()
