// ===== Backend-aligned API Types =====
//
// These mirror backend/app/schemas/task.py. Keep them in sync when the
// backend schemas change.

export interface Format {
  id: string;
  name: string;
  description: string;
  icon: string;
  /** Target file extension, e.g. '.docx' */
  target_ext: string;
  /** Target MIME type */
  mime_type: string;
}

export interface OCRParams {
  enabled: boolean;
  engine: string;
  language: string;
  min_confidence: number;
  enhance_image?: boolean;
  enhance_mode?: "standard" | "hard";
  upscale_factor?: number;
  contrast?: number;
  sharpness?: number;
  binarize?: boolean;
}

export interface LayoutParams {
  detect_tables: boolean;
  detect_images: boolean;
  detect_headers_footers: boolean;
  reading_order: boolean;
}

export interface ImageParams {
  quality: number;
  max_width?: number | null;
  max_height?: number | null;
  dpi: number;
}

export interface FontParams {
  fallback_font: string;
  embed_fonts: boolean;
  preserve_size: boolean;
}

export interface ConvertParams {
  ocr: OCRParams;
  layout: LayoutParams;
  image: ImageParams;
  font: FontParams;
  output_format?: string;
  start_page?: number;
  end_page?: number | null;
}

export interface FormatsResponse {
  formats: Format[];
}

export interface ParamsResponse {
  format: string;
  default_params: ConvertParams;
  description?: string;
}

export interface UploadResponse {
  file_id: string;
  filename: string;
  size: number;
}

/**
 * Task response from the backend.
 *
 * `result` shape (consistent across `/convert`, `/convert/sync`,
 * `/tasks/{id}`, `/tasks/{id}/start`):
 *   - `null` when the task is not yet completed or has no result file.
 *   - `{ file_id: string; filename: string; path: string }` when completed.
 *     `file_id` is the *task* id (the handle `/download/{id}` accepts), not
 *     the source File id.
 *
 * `file_name` and `file_size` are NOT returned by the backend. They are
 * frontend-only display fields, populated by the store from the locally
 * known upload (see taskStore.createAndStartTask). After a page refresh
 * they are null and the result page falls back to its own placeholder.
 */
export interface TaskStatus {
  id: string;
  file_id: string;
  target_format: string;
  status: "pending" | "queued" | "processing" | "completed" | "failed";
  progress: number;
  result?: {
    file_id: string;
    filename: string;
    path: string;
  } | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  /** Frontend-only display field; not populated by the backend. */
  file_name?: string;
  /** Frontend-only display field; not populated by the backend. */
  file_size?: number;
}

// ===== Application State Types =====

export type ConversionPhase =
  | "idle"
  | "uploading"
  | "preparing"
  | "processing"
  | "finalizing"
  | "completed"
  | "failed";
