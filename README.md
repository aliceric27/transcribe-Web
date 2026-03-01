# transcribe-Web

[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](docker-compose.yml)
[![CUDA](https://img.shields.io/badge/CUDA-GPU%20Accelerated-76B900?logo=nvidia&logoColor=white)](https://developer.nvidia.com/cuda-toolkit)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](LICENSE)

Whisper-based transcription with both **CLI** and **Web App** modes.

- Browser upload flow for audio/video files
- Docker-first startup with CUDA acceleration
- Optional Cloudflare Tunnel sidecar for public access

## Languages

- English (this file)
- 繁體中文: [README.zh-TW.md](README.zh-TW.md)

---

## Web App Overview

The web app is implemented with FastAPI and serves both frontend and API from one process.

Architecture:

```text
Browser <--HTTPS--> Cloudflare Tunnel <--> Docker (FastAPI:80) <--> transcribe() API
                                                       |
                                                    CUDA GPU
```

### API Endpoints

- `GET /` — Embedded frontend page
- `POST /api/transcribe` — Upload file + create transcription job
- `GET /api/jobs` — List jobs
- `GET /api/jobs/{job_id}` — Poll job status
- `GET /api/jobs/{job_id}/download/{filename}` — Download outputs

### Output files

A completed job may include:

- `out.srt`
- `out.vtt`
- `out.txt`
- `out.json`
- `speaker.json` (only when supported by backend/options)

---

## Quick Start

### Local Python (Web mode)

```bash
./install
source activate
transcribe-anything-web
```

Open: `http://localhost:80`

### Docker Compose (Recommended)

1) Create `.env` in project root:

```env
CLOUDFLARE_TUNNEL_TOKEN=your-tunnel-token-here
```

2) Build and run:

```bash
docker compose up --build -d
```

3) Open local web app:

- `http://localhost:8092`

4) Stop:

```bash
docker compose down
```

---

## Docker Build / Startup / Deployment Notes

### What the image does at build time

The Docker image prewarms backend environments to reduce first-request latency:

- `transcribe-anything-init-cuda`
- `transcribe-anything-init-insane`

The image defaults to web mode:

- `ENTRYPOINT ["/app/entrypoint.sh"]`
- `CMD ["--web"]`

### What `entrypoint.sh` does at runtime

- Configures CUDA runtime library paths
- Runs shared-library checks
- Starts web server for `--web`

### Current Compose services

`docker-compose.yml` defines:

- `transcribe`
  - Built from local `Dockerfile`
  - Port mapping: `8092:80`
  - Volume: `transcribe-data:/app/data`
  - Env:
    - `MAX_UPLOAD_SIZE_MB=100`
    - `NVIDIA_VISIBLE_DEVICES=all`
- `cloudflared`
  - Image: `cloudflare/cloudflared:latest`
  - Command: `tunnel run`
  - Env: `TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}`

### Cloudflare Tunnel setup

1. Create a Tunnel in Cloudflare Zero Trust.
2. Put token into `.env` as `CLOUDFLARE_TUNNEL_TOKEN`.
3. Configure public hostname service target to:
   - `http://transcribe:80`
4. Restart stack:

```bash
docker compose down
docker compose up -d
```

### Upload limits

- App-side upload limit is controlled by `MAX_UPLOAD_SIZE_MB` (default `100`).
- Cloudflare edge upload limits may still apply on public URLs.
- For very large uploads, use local endpoint `http://localhost:8092`.

---

## CLI / Python API (still supported)

CLI examples:

```bash
transcribe-anything video.mp4 --device cpu
transcribe-anything video.mp4 --device cuda
transcribe-anything video.mp4 --device insane --batch-size 8
transcribe-anything video.mp4 --device mlx
```

Python API:

```python
from transcribe_anything import transcribe

transcribe(
    url_or_file="video.mp4",
    output_dir="output_dir",
    task="transcribe",
    model="small",
    device="cuda",
)
```

---

## Development commands

- Setup: `./install && source activate`
- Tests: `./test`
- Lint: `./lint --no-ruff`
- Clean: `./clean`

## Acknowledgements

- Originally derived from [transcribe-anything](https://github.com/zackees/transcribe-anything)

## License

BSD-3-Clause
