FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# Install Python 3.10 and pip
RUN apt-get update && \
    apt-get install -y python3.10 python3.10-venv python3.10-dev python3-pip && \
    ln -sf python3.10 /usr/bin/python && \
    ln -sf pip3 /usr/bin/pip && \
    python3.10 -m pip install --upgrade pip

COPY requirements.txt .
RUN python3.10 -m pip install --no-cache-dir -r requirements.txt

# Install PyTorch 2.3.0 with CUDA 12.1 support
RUN python3.10 -m pip install torch==2.3.0 torchvision==0.18.0 torchaudio==2.3.0 \
    --extra-index-url https://download.pytorch.org/whl/cu121

# Install Python app dependencies


# Copy app code and expose port
COPY . .
EXPOSE 8081

CMD ["python3.10", "app.py"]