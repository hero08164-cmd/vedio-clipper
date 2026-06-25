import os
import tempfile
import whisper
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Whisper Transcription Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print("⏳ Whisper tiny model load ho raha hai...")
model = whisper.load_model("tiny")  # tiny = ~150MB RAM only
print("✅ Whisper ready!")


@app.get("/")
def root():
    return {"status": "✅ Whisper Service chal raha hai", "model": "tiny"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename)[-1] or ".mp4"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()

        if len(content) > 100 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File bahut badi hai! Max 100MB.")

        tmp.write(content)
        tmp_path = tmp.name

    try:
        print(f"🎙️ Transcribing: {file.filename}")

        result = model.transcribe(
            tmp_path,
            verbose=False,
            word_timestamps=True,
            language=None,
            fp16=False,  # CPU pe fp16 nahi chalta
        )

        segments = []
        for seg in result["segments"]:
            segments.append({
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip()
            })

        return {
            "success": True,
            "language": result.get("language", "unknown"),
            "full_text": result["text"].strip(),
            "segments": segments,
            "total_segments": len(segments)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
