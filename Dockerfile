FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# STEP 1: pip + setuptools pehle upgrade karo (pkg_resources fix)
RUN pip install --upgrade pip setuptools wheel

# STEP 2: openai-whisper alag install karo (legacy setup.py fix)
RUN pip install --no-cache-dir openai-whisper==20231117

# STEP 3: Baaki dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Whisper base model pre-download (cold start fast hoga)
RUN python -c "import whisper; whisper.load_model('base')"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
