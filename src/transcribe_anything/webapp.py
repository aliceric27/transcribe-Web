"""FastAPI web application for transcribe-anything."""

# pylint: disable=too-many-lines,broad-except

from __future__ import annotations

import os
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from transcribe_anything.api import transcribe

APP_DIR = Path("/app")
DEFAULT_DATA_ROOT = APP_DIR / "data" if APP_DIR.exists() else Path.cwd() / "data"
DATA_ROOT = Path(os.environ.get("TRANSCRIBE_ANYTHING_WEB_DATA_DIR", str(DEFAULT_DATA_ROOT)))
UPLOADS_ROOT = DATA_ROOT / "uploads"
RESULTS_ROOT = DATA_ROOT / "results"
MAX_UPLOAD_SIZE_MB = int(os.environ.get("MAX_UPLOAD_SIZE_MB", "100"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {
    ".mp4",
    ".mp3",
    ".wav",
    ".m4a",
    ".webm",
    ".ogg",
    ".flac",
    ".mkv",
    ".avi",
}
DEFAULT_OUTPUT_FILES = ["out.srt", "out.vtt", "out.txt", "out.json", "speaker.json"]
DEFAULT_HOST = os.environ.get("TRANSCRIBE_ANYTHING_WEB_HOST", "0.0.0.0")
DEFAULT_PORT = int(os.environ.get("PORT", os.environ.get("TRANSCRIBE_ANYTHING_WEB_PORT", "80")))

for directory in (UPLOADS_ROOT, RESULTS_ROOT):
    directory.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="transcribe-anything Web App")
executor = ThreadPoolExecutor(max_workers=1)
jobs_lock = threading.Lock()
jobs: dict[str, dict[str, Any]] = {}

FRONTEND_HTML = """
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>transcribe-anything Web</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0f172a;
      --card: #111827;
      --border: #334155;
      --text: #e5e7eb;
      --muted: #94a3b8;
      --accent: #38bdf8;
      --success: #22c55e;
      --error: #ef4444;
      --warning: #f59e0b;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #020617 0%, var(--bg) 100%);
      color: var(--text);
    }

    .container {
      width: min(1100px, calc(100% - 32px));
      margin: 0 auto;
      padding: 32px 0 48px;
    }

    h1, h2, h3, p { margin-top: 0; }

    .card {
      background: rgba(17, 24, 39, 0.95);
      border: 1px solid rgba(51, 65, 85, 0.9);
      border-radius: 16px;
      padding: 20px;
      box-shadow: 0 12px 30px rgba(0, 0, 0, 0.25);
      margin-bottom: 20px;
    }

    .hero {
      display: grid;
      gap: 20px;
      grid-template-columns: 1.35fr 1fr;
      align-items: start;
    }

    .muted {
      color: var(--muted);
      line-height: 1.6;
    }

    .dropzone {
      border: 2px dashed var(--border);
      border-radius: 14px;
      padding: 28px;
      text-align: center;
      cursor: pointer;
      transition: border-color 0.2s ease, transform 0.2s ease;
      background: rgba(15, 23, 42, 0.55);
    }

    .dropzone.dragover {
      border-color: var(--accent);
      transform: translateY(-2px);
    }

    .dropzone strong {
      display: block;
      margin-bottom: 8px;
      font-size: 18px;
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }

    label {
      display: block;
      font-size: 14px;
      color: var(--muted);
      margin-bottom: 6px;
    }

    select,
    input[type="text"],
    button {
      width: 100%;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: rgba(15, 23, 42, 0.8);
      color: var(--text);
      padding: 11px 12px;
      font-size: 15px;
    }

    input[type="file"] {
      display: none;
    }

    button {
      border: none;
      background: linear-gradient(90deg, #0284c7, #06b6d4);
      font-weight: 700;
      cursor: pointer;
      margin-top: 18px;
    }

    button:disabled {
      opacity: 0.65;
      cursor: wait;
    }

    .status-pill {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 13px;
      font-weight: 700;
    }

    .queued { background: rgba(245, 158, 11, 0.14); color: #fbbf24; }
    .processing { background: rgba(56, 189, 248, 0.14); color: #67e8f9; }
    .completed { background: rgba(34, 197, 94, 0.14); color: #86efac; }
    .failed { background: rgba(239, 68, 68, 0.14); color: #fca5a5; }

    .downloads a {
      display: inline-block;
      margin: 4px 8px 0 0;
      color: var(--accent);
      text-decoration: none;
    }

    .history-item {
      border: 1px solid rgba(51, 65, 85, 0.8);
      border-radius: 12px;
      padding: 14px;
      margin-bottom: 10px;
      background: rgba(15, 23, 42, 0.5);
    }

    .history-meta {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      font-size: 13px;
      color: var(--muted);
      margin-top: 8px;
    }

    .empty {
      color: var(--muted);
      font-style: italic;
    }

    .error-text {
      color: #fca5a5;
      white-space: pre-wrap;
    }

    .success-text {
      color: #86efac;
    }

    @media (max-width: 900px) {
      .hero,
      .grid {
        grid-template-columns: 1fr;
      }
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="card">
      <h1>transcribe-anything Web 應用程式</h1>
      <p class="muted">
        直接從瀏覽器上傳音訊或影片檔，交給 transcribe-anything 進行語音轉文字。
        GPU 任務會依序排隊執行，避免同時佔滿顯示卡記憶體。
      </p>
      <p class="muted">支援格式：mp4、mp3、wav、m4a、webm、ogg、flac、mkv、avi。單檔上限：__MAX_UPLOAD_SIZE_MB__ MB。</p>
    </div>

    <div class="hero">
      <div class="card">
        <h2>上傳檔案</h2>
        <div id="dropzone" class="dropzone">
          <strong>拖放檔案到這裡</strong>
          <span class="muted">或點擊選擇檔案</span>
          <input id="fileInput" type="file" accept=".mp4,.mp3,.wav,.m4a,.webm,.ogg,.flac,.mkv,.avi">
        </div>
        <p id="selectedFile" class="muted" style="margin-top: 14px;">尚未選擇檔案</p>
      </div>

      <div class="card">
        <h2>轉錄選項</h2>
        <div class="grid">
          <div>
            <label for="model">模型</label>
            <select id="model">
              <option value="tiny">tiny</option>
              <option value="base">base</option>
              <option value="small" selected>small</option>
              <option value="medium">medium</option>
              <option value="large-v3">large-v3</option>
            </select>
          </div>
          <div>
            <label for="device">裝置</label>
            <select id="device">
              <option value="cpu">cpu</option>
              <option value="cuda" selected>cuda</option>
              <option value="insane">insane</option>
            </select>
          </div>
          <div>
            <label for="task">任務類型</label>
            <select id="task">
              <option value="transcribe" selected>轉錄</option>
              <option value="translate">翻譯成英文</option>
            </select>
          </div>
          <div>
            <label for="language">語言（留空 = 自動偵測）</label>
            <input id="language" type="text" list="languageOptions" placeholder="例如：zh、en、ja">
            <datalist id="languageOptions">
              <option value="zh"></option>
              <option value="en"></option>
              <option value="ja"></option>
              <option value="ko"></option>
              <option value="fr"></option>
              <option value="de"></option>
              <option value="es"></option>
            </datalist>
          </div>
        </div>
        <button id="submitButton" type="button">開始轉錄</button>
      </div>
    </div>

    <div class="card">
      <h2>目前任務</h2>
      <div id="currentJob" class="empty">尚未建立任務</div>
    </div>

    <div class="card">
      <h2>任務歷史</h2>
      <div id="history" class="empty">尚無任務紀錄</div>
    </div>
  </div>

  <script>
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const selectedFile = document.getElementById('selectedFile');
    const submitButton = document.getElementById('submitButton');
    const currentJob = document.getElementById('currentJob');
    const history = document.getElementById('history');

    let activeFile = null;
    let currentJobId = null;
    let pollTimer = null;

    function escapeHtml(value) {
      return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
    }

    function setActiveFile(file) {
      activeFile = file;
      if (!file) {
        selectedFile.textContent = '尚未選擇檔案';
        return;
      }
      const sizeMb = (file.size / (1024 * 1024)).toFixed(2);
      selectedFile.textContent = `已選擇：${file.name}（${sizeMb} MB）`;
    }

    function statusLabel(status) {
      if (status === 'queued') return '排隊中';
      if (status === 'processing') return '處理中';
      if (status === 'completed') return '已完成';
      if (status === 'failed') return '失敗';
      return status;
    }

    function renderDownloads(job) {
      if (!job.downloads || !job.downloads.length) {
        return '<div class="muted">尚未產生可下載檔案。</div>';
      }
      const links = job.downloads
        .map((item) => `<a href="${item.url}" target="_blank" rel="noopener">下載 ${escapeHtml(item.filename)}</a>`)
        .join('');
      return `<div class="downloads">${links}</div>`;
    }

    function renderCurrentJob(job) {
      if (!job) {
        currentJob.innerHTML = '<div class="empty">尚未建立任務</div>';
        return;
      }
      const errorBlock = job.error
        ? `<div class="error-text" style="margin-top: 12px;">${escapeHtml(job.error)}</div>`
        : '';
      const extra = job.status === 'completed'
        ? `<div style="margin-top: 12px;" class="success-text">轉錄完成，可下載結果檔案。</div>${renderDownloads(job)}`
        : '';
      currentJob.innerHTML = `
        <div class="history-item">
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;">
            <strong>${escapeHtml(job.original_filename)}</strong>
            <span class="status-pill ${job.status}">${statusLabel(job.status)}</span>
          </div>
          <div class="history-meta">
            <span>Job ID: ${escapeHtml(job.id)}</span>
            <span>模型: ${escapeHtml(job.model)}</span>
            <span>裝置: ${escapeHtml(job.device)}</span>
            <span>任務: ${escapeHtml(job.task)}</span>
            <span>語言: ${escapeHtml(job.language || '自動偵測')}</span>
          </div>
          ${extra}
          ${errorBlock}
        </div>
      `;
    }

    function renderHistory(items) {
      if (!items.length) {
        history.innerHTML = '<div class="empty">尚無任務紀錄</div>';
        return;
      }
      history.innerHTML = items.map((job) => {
        const downloads = job.status === 'completed' ? renderDownloads(job) : '';
        const error = job.error ? `<div class="error-text" style="margin-top: 10px;">${escapeHtml(job.error)}</div>` : '';
        return `
          <div class="history-item">
            <div style="display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;">
              <strong>${escapeHtml(job.original_filename)}</strong>
              <span class="status-pill ${job.status}">${statusLabel(job.status)}</span>
            </div>
            <div class="history-meta">
              <span>${new Date(job.created_at).toLocaleString('zh-TW')}</span>
              <span>模型: ${escapeHtml(job.model)}</span>
              <span>裝置: ${escapeHtml(job.device)}</span>
              <span>任務: ${escapeHtml(job.task)}</span>
              <span>語言: ${escapeHtml(job.language || '自動偵測')}</span>
            </div>
            ${downloads}
            ${error}
          </div>
        `;
      }).join('');
    }

    async function loadHistory() {
      try {
        const response = await fetch('/api/jobs');
        const data = await response.json();
        renderHistory(data.jobs || []);
      } catch (error) {
        history.innerHTML = `<div class="error-text">讀取任務歷史失敗：${escapeHtml(error.message)}</div>`;
      }
    }

    async function pollJob(jobId) {
      try {
        const response = await fetch(`/api/jobs/${jobId}`);
        if (!response.ok) {
          throw new Error('查詢任務狀態失敗');
        }
        const job = await response.json();
        renderCurrentJob(job);
        await loadHistory();
        if (job.status === 'completed' || job.status === 'failed') {
          clearInterval(pollTimer);
          pollTimer = null;
          submitButton.disabled = false;
        }
      } catch (error) {
        clearInterval(pollTimer);
        pollTimer = null;
        submitButton.disabled = false;
        currentJob.innerHTML = `<div class="error-text">${escapeHtml(error.message)}</div>`;
      }
    }

    function startPolling(jobId) {
      if (pollTimer) {
        clearInterval(pollTimer);
      }
      pollJob(jobId);
      pollTimer = setInterval(() => pollJob(jobId), 2000);
    }

    async function submitJob() {
      if (!activeFile) {
        currentJob.innerHTML = '<div class="error-text">請先選擇要上傳的檔案。</div>';
        return;
      }

      submitButton.disabled = true;
      currentJob.innerHTML = '<div class="muted">正在建立任務…</div>';

      const formData = new FormData();
      formData.append('file', activeFile);
      formData.append('model', document.getElementById('model').value);
      formData.append('device', document.getElementById('device').value);
      formData.append('task', document.getElementById('task').value);
      formData.append('language', document.getElementById('language').value.trim());

      try {
        const response = await fetch('/api/transcribe', {
          method: 'POST',
          body: formData,
        });
        const raw = await response.text();
        let data = {};
        if (raw) {
          try {
            data = JSON.parse(raw);
          } catch (parseError) {
            data = { detail: raw };
          }
        }
        if (!response.ok) {
          throw new Error(data.detail || '建立任務失敗');
        }
        currentJobId = data.job.id;
        renderCurrentJob(data.job);
        await loadHistory();
        startPolling(currentJobId);
      } catch (error) {
        submitButton.disabled = false;
        currentJob.innerHTML = `<div class="error-text">${escapeHtml(error.message)}</div>`;
      }
    }

    dropzone.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (event) => {
      const [file] = event.target.files;
      setActiveFile(file || null);
    });

    ['dragenter', 'dragover'].forEach((eventName) => {
      dropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropzone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach((eventName) => {
      dropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropzone.classList.remove('dragover');
      });
    });

    dropzone.addEventListener('drop', (event) => {
      const [file] = event.dataTransfer.files;
      setActiveFile(file || null);
    });

    submitButton.addEventListener('click', submitJob);
    loadHistory();
  </script>
</body>
</html>
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_filename(filename: Optional[str]) -> str:
    if not filename:
        return "upload.bin"
    safe_name = Path(filename).name
    return safe_name or "upload.bin"


def _get_job(job_id: str) -> dict[str, Any]:
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="找不到指定的任務")
        return dict(job)


def _serialize_job(job: dict[str, Any]) -> dict[str, Any]:
    serialized = {
        "id": job["id"],
        "status": job["status"],
        "original_filename": job["original_filename"],
        "stored_filename": job["stored_filename"],
        "model": job["model"],
        "device": job["device"],
        "task": job["task"],
        "language": job["language"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "error": job.get("error"),
        "output_files": list(job.get("output_files", [])),
    }
    serialized["downloads"] = [
        {
            "filename": filename,
            "url": f"/api/jobs/{job['id']}/download/{filename}",
        }
        for filename in serialized["output_files"]
    ]
    return serialized


def _update_job(job_id: str, **changes: Any) -> None:
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return
        job.update(changes)
        job["updated_at"] = _utc_now()


def _process_job(job_id: str, upload_path: Path, result_dir: Path, model: str, device: str, task: str, language: Optional[str]) -> None:
    _update_job(job_id, status="processing")
    try:
        transcribe(
            url_or_file=str(upload_path),
            output_dir=str(result_dir),
            model=model,
            task=task,
            language=language,
            device=device,
        )
        output_files = [name for name in DEFAULT_OUTPUT_FILES if (result_dir / name).is_file()]
        _update_job(job_id, status="completed", output_files=output_files, error=None)
    except Exception as exc:
        _update_job(job_id, status="failed", error=str(exc), output_files=[])


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse(FRONTEND_HTML.replace("__MAX_UPLOAD_SIZE_MB__", str(MAX_UPLOAD_SIZE_MB)))


@app.post("/api/transcribe")
async def create_transcription_job(
    file: UploadFile = File(...),
    model: str = Form("small"),
    device: str = Form("cuda"),
    task: str = Form("transcribe"),
    language: str = Form(""),
) -> dict[str, Any]:
    safe_name = _safe_filename(file.filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="不支援的檔案格式")

    job_id = uuid4().hex
    upload_dir = UPLOADS_ROOT / job_id
    result_dir = RESULTS_ROOT / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    result_dir.mkdir(parents=True, exist_ok=True)
    upload_path = upload_dir / safe_name

    bytes_written = 0
    try:
        with upload_path.open("wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > MAX_UPLOAD_SIZE_BYTES:
                    raise HTTPException(status_code=413, detail=f"檔案超過 {MAX_UPLOAD_SIZE_MB} MB 上限")
                handle.write(chunk)
    except HTTPException:
        shutil.rmtree(upload_dir, ignore_errors=True)
        shutil.rmtree(result_dir, ignore_errors=True)
        raise
    finally:
        await file.close()

    normalized_language = language.strip() or None
    job = {
        "id": job_id,
        "status": "queued",
        "original_filename": safe_name,
        "stored_filename": str(upload_path),
        "result_dir": str(result_dir),
        "model": model,
        "device": device,
        "task": task,
        "language": normalized_language,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "error": None,
        "output_files": [],
    }

    with jobs_lock:
        jobs[job_id] = job

    executor.submit(_process_job, job_id, upload_path, result_dir, model, device, task, normalized_language)
    return {"job": _serialize_job(job)}


@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str) -> dict[str, Any]:
    return _serialize_job(_get_job(job_id))


@app.get("/api/jobs")
def list_jobs() -> dict[str, Any]:
    with jobs_lock:
        ordered_jobs = sorted(jobs.values(), key=lambda item: item["created_at"], reverse=True)
        serialized_jobs = [_serialize_job(dict(job)) for job in ordered_jobs]
    return {"jobs": serialized_jobs}


@app.get("/api/jobs/{job_id}/download/{filename}")
def download_job_file(job_id: str, filename: str) -> FileResponse:
    job = _get_job(job_id)
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="無效的檔案名稱")
    if safe_name not in job.get("output_files", []):
        raise HTTPException(status_code=404, detail="找不到指定的結果檔案")

    file_path = Path(job["result_dir"]) / safe_name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="找不到指定的結果檔案")
    return FileResponse(path=file_path, filename=safe_name)


@app.on_event("shutdown")
def shutdown_executor() -> None:
    executor.shutdown(wait=False)


def main() -> None:
    uvicorn.run(app, host=DEFAULT_HOST, port=DEFAULT_PORT)


if __name__ == "__main__":
    main()
