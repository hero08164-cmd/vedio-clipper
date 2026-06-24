# ✂️ Video Clip Maker — Setup Guide

---

## 📁 File Structure

```
video-clipper/
├── clip_downloader.py      ← Standalone Python script (local use)
├── backend/
│   ├── app.py              ← Flask backend server
│   └── requirements.txt    ← Python dependencies
└── frontend/
    └── index.html          ← Website (browser mein open karo)
```

---

## 🛠 Prerequisites (pehle install karo)

### 1. Python 3.8+
Download: https://python.org

### 2. FFmpeg (ZARURI hai!)
- **Windows**: https://ffmpeg.org/download.html
  - Download karo → unzip karo → `bin` folder ko PATH mein add karo
- **Mac**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

Check karo: `ffmpeg -version`

---

## 🐍 Option A — Standalone Script (Local PC)

### Install
```bash
pip install yt-dlp ffmpeg-python
```

### Use karo
`clip_downloader.py` file mein ye fields edit karo:
```python
YOUTUBE_URL = "https://www.youtube.com/watch?v=YOUR_ID"
CLIPS = [
    {"start": "0:12", "end": "0:42", "label": "sabse_acha_moment"},
    {"start": "1:05", "end": "1:35", "label": "funny_scene"},
]
FORMAT = "reels"   # reels | square | landscape
```

### Run karo
```bash
python clip_downloader.py
```

Clips `my_clips/` folder mein save hongi ✅

---

## 🌐 Option B — Flask Backend + Website

### Install
```bash
cd backend
pip install -r requirements.txt
```

### Backend start karo
```bash
python app.py
```
→ Server chal raha hai: http://localhost:5000

### Website open karo
`frontend/index.html` ko browser mein open karo
(ya VS Code Live Server use karo)

### Use karo
1. YouTube URL paste karo → Check dabao
2. Clips ki start/end time bharo
3. Format choose karo (Reels/Square/Landscape)
4. "Clips banao" dabao
5. Progress dekho → Download button aayega ✅

---

## ☁️ Free Deployment (Online chalane ke liye)

### Railway.app (Recommended — Free)
```bash
# Railway CLI install karo
npm install -g @railway/cli

# Login
railway login

# Deploy
cd backend
railway init
railway up
```

Phir `frontend/index.html` mein API URL change karo:
```javascript
const API = "https://YOUR-APP.railway.app/api";
```

### Render.com (Alternative)
- New Web Service banao
- GitHub repo connect karo
- Start command: `python app.py`
- Port: `5000`

---

## ⚙️ Supported Formats

| Format    | Resolution  | Best for              |
|-----------|-------------|------------------------|
| reels     | 1080×1920   | Instagram Reels, YouTube Shorts, TikTok |
| square    | 1080×1080   | Instagram Feed         |
| landscape | 1280×720    | YouTube, Twitter       |

---

## ❓ Common Issues

**"yt-dlp not found"**
→ `pip install yt-dlp` aur phir try karo

**"ffmpeg not found"**
→ FFmpeg install karo aur PATH mein add karo

**"Backend se connect nahi hua"**
→ `python app.py` chala rahe ho? Terminal check karo

**Age-restricted ya private video**
→ yt-dlp cookies option use karo: `--cookies-from-browser chrome`
"# vedio-clipper" 
