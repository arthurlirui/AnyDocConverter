// ===== Backend-aligned API Types =====

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
}

export interface LayoutParams {
  preservation: string; // exact | loose | adaptive
  detect_tables: boolean;
  detect_images: boolean;
  detect_headers_footers: boolean;
  reading_order: boolean;
}

export interface ImageParams {
  dpi: number;
  compression: string;
  quality: number;
  color_space: string;
}

export interface FontParams {
  mode: string; // exact | approximate | replace
  fallback_font: string;
  embed_fonts: boolean;
  subset_fonts: boolean;
}

export interface ConvertParams {
  ocr: OCRParams;
  layout: LayoutParams;
  image: ImageParams;
  font: FontParams;
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

export interface TaskStatus {
  id: string;
  file_id: string;
  target_format: string;
  status: "pending" | "queued" | "processing" | "completed" | "failed";
  progress: number;
  result?: Record<string, any> | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface StartTaskRequest {
  target_format: string;
  params: ConvertParams;
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

export interface ConversionProgress {
  phase: ConversionPhase;
  progress: number; // 0-100
  message: string;
}
