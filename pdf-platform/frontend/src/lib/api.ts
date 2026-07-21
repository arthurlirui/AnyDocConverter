// In Docker behind nginx, NEXT_PUBLIC_API_URL is empty → relative URLs proxied by nginx
// In dev mode (localhost:3000), fallback to direct backend URL
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

function apiUrl(path: string): string {
  return API_BASE ? `${API_BASE}${path}` : path;
}

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(body.detail || res.statusText, res.status);
  }
  return res.json();
}

// ── Types ─────────────────────────────────────────────────────────────
import type {
  UploadResponse,
  FormatsResponse,
  ParamsResponse,
  TaskStatus,
  ConvertParams,
} from "@/types";

/**
 * POST /api/v1/upload — Upload a PDF file.
 * Uses XMLHttpRequest for upload progress tracking.
 */
export async function uploadFile(
  file: File,
  onProgress?: (pct: number) => void
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", apiUrl("/api/v1/upload"));

    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        try {
          const body = JSON.parse(xhr.responseText);
          reject(new ApiError(body.detail || xhr.statusText, xhr.status));
        } catch {
          reject(new ApiError(xhr.statusText, xhr.status));
        }
      }
    });

    xhr.addEventListener("error", () => reject(new Error("Network error")));
    xhr.send(form);
  });
}

/**
 * GET /api/v1/formats — List all supported conversion formats.
 */
export async function fetchFormats(): Promise<FormatsResponse> {
  const res = await fetch(apiUrl("/api/v1/formats"));
  return handleResponse<FormatsResponse>(res);
}

/**
 * GET /api/v1/params/{format} — Get default conversion params for a format.
 */
export async function fetchFormatParams(
  formatId: string
): Promise<ParamsResponse> {
  const res = await fetch(apiUrl(`/api/v1/params/${formatId}`));
  return handleResponse<ParamsResponse>(res);
}

/**
 * POST /api/v1/convert — Create and start a conversion task in one step.
 *
 * This is the main frontend-facing endpoint. Returns the freshly-created
 * task with `status: "queued"` (or `"failed"` if the broker was unreachable).
 * The response is a `TaskResponse`; note that `file_name` / `file_size` on
 * the frontend `TaskStatus` type are NOT populated by the backend — the
 * store fills them from the locally known upload (see taskStore).
 */
export async function startTask(
  fileId: string,
  targetFormat: string,
  params: ConvertParams
): Promise<TaskStatus> {
  const res = await fetch(apiUrl("/api/v1/convert"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      file_id: fileId,
      target_format: targetFormat,
      params,
    }),
  });
  return handleResponse<TaskStatus>(res);
}

/**
 * GET /api/v1/tasks/{id} — Poll task status.
 */
export async function fetchTaskStatus(id: string): Promise<TaskStatus> {
  const res = await fetch(apiUrl(`/api/v1/tasks/${id}`));
  return handleResponse<TaskStatus>(res);
}

/**
 * Build the download URL for a conversion result.
 *
 * The backend `GET /api/v1/download/{file_id}` endpoint serves the file
 * directly (binary FileResponse), accepting either a File id or a Task id.
 * The frontend passes the Task id (see result/page.tsx). This function only
 * constructs the URL string — the actual download happens when the browser
 * navigates to it via an `<a href download>` click.
 */
export function getDownloadUrl(fileId: string): string {
  return apiUrl(`/api/v1/download/${fileId}`);
}
