FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# pip upgrade
RUN pip install --upgrade pip

# setuptools PEHLE - isolated environment me bhi available rahe
RUN pip install "setuptools>=68" wheel

# Whisper latest GitHub se (modern pyproject.toml hai, setup.py nahi)
RUN pip install --no-cache-dir "openai-whisper @ git+https://github.com/openai/whisper.git"

# Baaki dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Model pre-download
RUN python -c "import whisper; whisper.load_model('base')"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
