"""
Video Clipper — Flask Backend
==============================
Website ke saath chalane ke liye full REST API

INSTALL:
    pip install flask flask-cors yt-dlp ffmpeg-python

RUN:
    python app.py
    → http://localhost:5000

DEPLOY (free):
    Railway.app ya Render.com pe push karo
"""

import os
import re
import json
import uuid
import subprocess
import threading
from pathlib import Path
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)   # Frontend se requests allow karo

# ── Folders ──
DOWNLOAD_DIR = Path("downloads")
CLIPS_DIR    = Path("clips")
DOWNLOAD_DIR.mkdir(exist_ok=True)
CLIPS_DIR.mkdir(exist_ok=True)

# ── Job status track karo (in-memory; production mein Redis use karo) ──
jobs: dict = {}


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def to_seconds(t: str) -> float:
    t = t.strip()
    if ":" in t:
        parts = t.split(":")
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    return float(t)


def safe_name(s: str) -> str:
    return re.sub(r'[^\w\-]', '_', s)[:40]


def update_job(job_id, **kwargs):
    jobs[job_id].update(kwargs)


# ─────────────────────────────────────────
# ROUTE 1: Video info fetch
# POST /api/info   body: { "url": "..." }
# ─────────────────────────────────────────
@app.route("/api/info", methods=["POST"])
def video_info():
    data = request.json or {}
    url  = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL nahi mili"}), 400

    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-playlist", url],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return jsonify({"error": result.stderr[:300]}), 400

        info = json.loads(result.stdout)
        return jsonify({
            "title":     info.get("title"),
            "duration":  info.get("duration"),
            "thumbnail": info.get("thumbnail"),
            "views":     info.get("view_count"),
            "uploader":  info.get("uploader"),
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Timeout — URL check karo"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────
# ROUTE 2: Clip job start karo (async)
# POST /api/clip
# body: {
#   "url": "...",
#   "clips": [{"start":"0:12","end":"0:42","label":"moment1"}],
#   "format": "reels"
# }
# ─────────────────────────────────────────
@app.route("/api/clip", methods=["POST"])
def start_clip_job():
    data   = request.json or {}
    url    = data.get("url", "").strip()
    clips  = data.get("clips", [])
    fmt    = data.get("format", "reels")

    if not url:
        return jsonify({"error": "URL chahiye"}), 400
    if not clips:
        return jsonify({"error": "Kam se kam ek clip chahiye"}), 400

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status":   "queued",
        "progress": 0,
        "message":  "Shuru ho raha hai...",
        "files":    [],
        "error":    None,
    }

    # Background thread mein chalao
    t = threading.Thread(
        target=_run_clip_job,
        args=(job_id, url, clips, fmt),
        daemon=True
    )
    t.start()

    return jsonify({"job_id": job_id})


def _run_clip_job(job_id, url, clips, fmt):
    try:
        update_job(job_id, status="downloading", progress=5,
                   message="Video download ho rahi hai...")

        # ── Download full video ──
        video_path = DOWNLOAD_DIR / f"{job_id}.mp4"
        result = subprocess.run([
            "yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", str(video_path),
            "--no-playlist",
            url
        ], capture_output=True, text=True)

        if result.returncode != 0:
            update_job(job_id, status="error", error=result.stderr[:300])
            return

        update_job(job_id, progress=40, message="Video ready, clips kaat raha hoon...")

        # Format filters
        vf_map = {
            "reels":     "crop=ih*9/16:ih,scale=1080:1920",
            "square":    "crop=min(iw\\,ih):min(iw\\,ih),scale=1080:1080",
            "landscape": "scale=1280:720",
        }
        vf = vf_map.get(fmt, "scale=1280:720")

        out_files = []
        total = len(clips)

        for i, clip in enumerate(clips):
            start_sec = to_seconds(clip.get("start", "0"))
            end_sec   = to_seconds(clip.get("end",   "30"))
            duration  = end_sec - start_sec
            label     = safe_name(clip.get("label", f"clip_{i+1}"))
            out_path  = CLIPS_DIR / f"{job_id}_{label}.mp4"

            subprocess.run([
                "ffmpeg",
                "-ss",  str(start_sec),
                "-i",   str(video_path),
                "-t",   str(duration),
                "-vf",  vf,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "128k",
                "-movflags", "+faststart",
                "-y",
                str(out_path)
            ], check=True, capture_output=True)

            out_files.append({
                "label":    clip.get("label", f"Clip {i+1}"),
                "file_id":  f"{job_id}_{label}",
                "filename": out_path.name,
                "start":    clip.get("start"),
                "end":      clip.get("end"),
            })

            prog = 40 + int(((i + 1) / total) * 55)
            update_job(job_id, progress=prog,
                       message=f"Clip {i+1}/{total} ready...")

        # ── Cleanup full video ──
        try:
            video_path.unlink()
        except Exception:
            pass

        update_job(job_id, status="done", progress=100,
                   message="Sab clips taiyaar hain!", files=out_files)

    except Exception as e:
        update_job(job_id, status="error", error=str(e))


# ─────────────────────────────────────────
# ROUTE 3: Job status check karo
# GET /api/status/<job_id>
# ─────────────────────────────────────────
@app.route("/api/status/<job_id>", methods=["GET"])
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job nahi mila"}), 404
    return jsonify(job)


# ─────────────────────────────────────────
# ROUTE 4: Clip download karo
# GET /api/download/<file_id>
# ─────────────────────────────────────────
@app.route("/api/download/<file_id>", methods=["GET"])
def download_clip(file_id):
    safe_id = re.sub(r'[^\w\-]', '', file_id)
    path = CLIPS_DIR / f"{safe_id}.mp4"
    if not path.exists():
        return jsonify({"error": "File nahi mili"}), 404
    return send_file(str(path), as_attachment=True,
                     download_name=f"{safe_id}.mp4",
                     mimetype="video/mp4")


# ─────────────────────────────────────────
# ROUTE 5: Health check
# GET /api/health
# ─────────────────────────────────────────
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "active_jobs": len(jobs)})


if __name__ == "__main__":
    print("🚀 Video Clipper Backend chal raha hai → http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
