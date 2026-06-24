import os
import re
import json
import uuid
import subprocess
import threading
from pathlib import Path
from flask import Flask, request, jsonify, send_file, make_response
from flask_cors import CORS

app = Flask(__name__)

# CORS — sab origins allow karo (file://, netlify, localhost sab)
CORS(app, origins="*", allow_headers=["Content-Type"], methods=["GET","POST","OPTIONS"])

# Har response mein manually bhi CORS header add karo (double safety)
@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

DOWNLOAD_DIR = Path("downloads")
CLIPS_DIR    = Path("clips")
DOWNLOAD_DIR.mkdir(exist_ok=True)
CLIPS_DIR.mkdir(exist_ok=True)

jobs: dict = {}

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


# ── OPTIONS preflight — sab routes ke liye ──
@app.route("/api/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return make_response("", 200)


# ── Route 1: Video info ──
@app.route("/api/info", methods=["POST", "OPTIONS"])
def video_info():
    if request.method == "OPTIONS":
        return make_response("", 200)
    data = request.json or {}
    url  = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL nahi mili"}), 400
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-playlist",
             "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
             url],
            capture_output=True, text=True, timeout=40
        )
        if result.returncode != 0:
            return jsonify({"error": result.stderr[:400]}), 400
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


# ── Route 2: Clip job start ──
@app.route("/api/clip", methods=["POST", "OPTIONS"])
def start_clip_job():
    if request.method == "OPTIONS":
        return make_response("", 200)
    data  = request.json or {}
    url   = data.get("url", "").strip()
    clips = data.get("clips", [])
    fmt   = data.get("format", "reels")
    if not url:
        return jsonify({"error": "URL chahiye"}), 400
    if not clips:
        return jsonify({"error": "Kam se kam ek clip chahiye"}), 400

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status": "queued", "progress": 0,
        "message": "Shuru ho raha hai...", "files": [], "error": None,
    }
    threading.Thread(target=_run_clip_job, args=(job_id, url, clips, fmt), daemon=True).start()
    return jsonify({"job_id": job_id})


def _run_clip_job(job_id, url, clips, fmt):
    try:
        update_job(job_id, status="downloading", progress=5, message="Video download ho rahi hai...")
        video_path = DOWNLOAD_DIR / f"{job_id}.mp4"

        result = subprocess.run([
            "yt-dlp",
            "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", str(video_path),
            "--no-playlist",
            "--sleep-interval", "2",
            "--max-sleep-interval", "5",
            "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "--add-header", "Accept-Language:en-US,en;q=0.9",
            "--extractor-retries", "5",
            url
        ], capture_output=True, text=True)

        if result.returncode != 0:
            update_job(job_id, status="error", error=result.stderr[:400])
            return

        update_job(job_id, progress=40, message="Video ready, clips kaat raha hoon...")

        vf_map = {
            "reels":     "crop=ih*9/16:ih,scale=1080:1920",
            "square":    "crop=min(iw\\,ih):min(iw\\,ih),scale=1080:1080",
            "landscape": "scale=1280:720",
        }
        vf = vf_map.get(fmt, "scale=1280:720")
        out_files = []

        for i, clip in enumerate(clips):
            start_sec = to_seconds(clip.get("start", "0"))
            end_sec   = to_seconds(clip.get("end", "30"))
            duration  = end_sec - start_sec
            label     = safe_name(clip.get("label", f"clip_{i+1}"))
            out_path  = CLIPS_DIR / f"{job_id}_{label}.mp4"

            subprocess.run([
                "ffmpeg", "-ss", str(start_sec), "-i", str(video_path),
                "-t", str(duration), "-vf", vf,
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                "-y", str(out_path)
            ], check=True, capture_output=True)

            out_files.append({
                "label":    clip.get("label", f"Clip {i+1}"),
                "file_id":  f"{job_id}_{label}",
                "filename": out_path.name,
                "start":    clip.get("start"),
                "end":      clip.get("end"),
            })
            prog = 40 + int(((i + 1) / len(clips)) * 55)
            update_job(job_id, progress=prog, message=f"Clip {i+1}/{len(clips)} ready...")

        try:
            video_path.unlink()
        except Exception:
            pass

        update_job(job_id, status="done", progress=100,
                   message="Sab clips taiyaar hain!", files=out_files)

    except Exception as e:
        update_job(job_id, status="error", error=str(e))


# ── Route 3: Status ──
@app.route("/api/status/<job_id>", methods=["GET"])
def job_status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job nahi mila"}), 404
    return jsonify(job)


# ── Route 4: Download ──
@app.route("/api/download/<file_id>", methods=["GET"])
def download_clip(file_id):
    safe_id = re.sub(r'[^\w\-]', '', file_id)
    path = CLIPS_DIR / f"{safe_id}.mp4"
    if not path.exists():
        return jsonify({"error": "File nahi mili"}), 404
    return send_file(str(path), as_attachment=True,
                     download_name=f"{safe_id}.mp4", mimetype="video/mp4")


# ── Route 5: Health ──
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "active_jobs": len(jobs)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Server chal raha hai → http://0.0.0.0:{port}")
    app.run(debug=False, host="0.0.0.0", port=port)
