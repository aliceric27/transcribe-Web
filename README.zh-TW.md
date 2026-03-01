# transcribe-Web（繁體中文）

Whisper 語音轉文字工具，支援 **CLI** 與 **Web 應用程式**。

- 可在瀏覽器上傳音訊/影片檔
- 以 Docker + CUDA 方式快速啟動
- 可搭配 Cloudflare Tunnel 對外提供服務

## 語言版本

- English: [README.md](README.md)
- 繁體中文（本文件）

---

## Web 應用程式概覽

目前 Web 版本使用 FastAPI，前端與 API 同一個服務進程提供。

架構：

```text
瀏覽器 <--HTTPS--> Cloudflare Tunnel <--> Docker (FastAPI:80) <--> transcribe() API
                                                        |
                                                     CUDA GPU
```

### API 端點

- `GET /`：前端頁面
- `POST /api/transcribe`：上傳檔案並建立任務
- `GET /api/jobs`：列出任務
- `GET /api/jobs/{job_id}`：查詢任務狀態
- `GET /api/jobs/{job_id}/download/{filename}`：下載輸出檔案

### 輸出檔案

任務完成後可能包含：

- `out.srt`
- `out.vtt`
- `out.txt`
- `out.json`
- `speaker.json`（僅特定 backend/選項會產生）

---

## 快速開始

### 本機 Python（Web 模式）

```bash
./install
source activate
transcribe-anything-web
```

開啟：`http://localhost:80`

### Docker Compose（建議）

1) 在專案根目錄建立 `.env`：

```env
CLOUDFLARE_TUNNEL_TOKEN=your-tunnel-token-here
```

2) 建置並啟動：

```bash
docker compose up --build -d
```

3) 開啟本機頁面：

- `http://localhost:8092`

4) 停止服務：

```bash
docker compose down
```

---

## Docker 建置 / 啟動 / 部署說明

### Image 在 build 階段會做什麼

為了降低首次請求等待時間，Docker image 會預熱兩個 backend 環境：

- `transcribe-anything-init-cuda`
- `transcribe-anything-init-insane`

Image 預設啟動為 Web 模式：

- `ENTRYPOINT ["/app/entrypoint.sh"]`
- `CMD ["--web"]`

### `entrypoint.sh` 在 runtime 會做什麼

- 設定 CUDA 相關 runtime 路徑
- 檢查共享函式庫
- 當參數是 `--web` 時啟動 Web 伺服器

### Compose 目前服務

`docker-compose.yml` 包含：

- `transcribe`
  - 由本地 `Dockerfile` 建置
  - 對外埠：`8092:80`
  - Volume：`transcribe-data:/app/data`
  - 環境變數：
    - `MAX_UPLOAD_SIZE_MB=100`
    - `NVIDIA_VISIBLE_DEVICES=all`
- `cloudflared`
  - 映像：`cloudflare/cloudflared:latest`
  - 指令：`tunnel run`
  - 環境變數：`TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}`

### Cloudflare Tunnel 設定流程

1. 在 Cloudflare Zero Trust 建立 Tunnel。
2. 把 token 放進 `.env` 的 `CLOUDFLARE_TUNNEL_TOKEN`。
3. 公開主機名稱路由到：
   - `http://transcribe:80`
4. 重啟服務：

```bash
docker compose down
docker compose up -d
```

### 上傳大小限制

- 應用端限制由 `MAX_UPLOAD_SIZE_MB` 控制（預設 `100`）。
- 公網網址仍可能受 Cloudflare edge 上傳限制。
- 超大檔案建議走本機入口：`http://localhost:8092`。

---

## CLI / Python API（仍可使用）

CLI 範例：

```bash
transcribe-anything video.mp4 --device cpu
transcribe-anything video.mp4 --device cuda
transcribe-anything video.mp4 --device insane --batch-size 8
transcribe-anything video.mp4 --device mlx
```

Python API 範例：

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

## 開發常用指令

- Setup：`./install && source activate`
- 測試：`./test`
- Lint：`./lint --no-ruff`
- 清理：`./clean`

## 致謝

- 包含 [transcribe-anything](https://github.com/zackees/transcribe-anything)

## License

BSD-3-Clause
