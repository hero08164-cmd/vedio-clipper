FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --upgrade pip
RUN pip install "setuptools>=68" wheel

# Whisper GitHub se
RUN pip install --no-cache-dir "openai-whisper @ git+https://github.com/openai/whisper.git"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# tiny model - sirf ~150MB RAM (free plan ke liye)
RUN python -c "import whisper; whisper.load_model('tiny')"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
