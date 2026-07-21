import { create } from "zustand";
import type {
  Format,
  ConvertParams,
  TaskStatus,
  ConversionPhase,
} from "@/types";
import {
  uploadFile,
  fetchFormats,
  fetchFormatParams,
  startTask,
  fetchTaskStatus,
} from "@/lib/api";

// ── Helpers ─────────────────────────────────────────────────────────

function phaseFromStatus(
  status: string,
  progress: number
): ConversionPhase {
  switch (status) {
    case "pending":
    case "queued":
      return "preparing";
    case "processing":
      if (progress < 0.5) return "processing";
      return "finalizing";
    case "completed":
      return "completed";
    case "failed":
      return "failed";
    default:
      return "idle";
  }
}

function phaseMessage(phase: ConversionPhase, progress: number): string {
  switch (phase) {
    case "uploading":
      return "Uploading file...";
    case "preparing":
      return "Preparing conversion...";
    case "processing":
      return `Processing... ${Math.round(progress * 100)}%`;
    case "finalizing":
      return "Finalizing output...";
    case "completed":
      return "Conversion complete!";
    case "failed":
      return "Conversion failed.";
    default:
      return "";
  }
}

function defaultParams(): ConvertParams {
  return {
    ocr: {
      enabled: false,
      engine: "paddle",
      language: "ch",
      min_confidence: 0.45,
      enhance_image: false,
      enhance_mode: "standard",
      upscale_factor: 1.0,
      contrast: 1.15,
      sharpness: 1.05,
      binarize: false,
    },
    layout: {
      detect_tables: true,
      detect_images: true,
      detect_headers_footers: true,
      reading_order: true,
    },
    image: {
      dpi: 150,
      quality: 85,
      max_width: null,
      max_height: null,
    },
    font: {
      fallback_font: "Noto Sans CJK SC",
      embed_fonts: true,
      preserve_size: true,
    },
    output_format: "docx",
    start_page: 0,
    end_page: null,
  };
}

// ── Store Interface ────────────────────────────────────────────────

interface TaskStore {
  // Formats
  formats: Format[];
  formatsLoading: boolean;
  formatsError: string | null;
  loadFormats: () => Promise<void>;

  // Upload
  file: File | null;
  uploadedFileName: string | null;
  fileId: string | null;
  isUploading: boolean;
  uploadProgress: number;
  uploadError: string | null;
  setFile: (file: File | null) => void;
  performUpload: (file: File) => Promise<string | null>;

  // Format / params
  targetFormat: string | null;
  params: ConvertParams;
  selectFormat: (formatId: string) => void;
  updateParams: (partial: Partial<ConvertParams>) => void;
  loadFormatParams: (formatId: string) => Promise<void>;

  // Task
  taskId: string | null;
  taskStatus: TaskStatus | null;
  phase: ConversionPhase;
  progress: number;
  phaseMessage: string;
  pollInterval: ReturnType<typeof setInterval> | null;
  createAndStartTask: () => Promise<string | null>;
  pollTask: (taskId: string) => Promise<void>;
  startPolling: (taskId: string) => void;
  stopPolling: () => void;

  // Reset
  reset: () => void;
}

// ── Store ───────────────────────────────────────────────────────────

export const useTaskStore = create<TaskStore>((set, get) => ({
  // ── Formats ──────────────────────────────
  formats: [],
  formatsLoading: false,
  formatsError: null,
  loadFormats: async () => {
    set({ formatsLoading: true, formatsError: null });
    try {
      const res = await fetchFormats();
      set({ formats: res.formats, formatsLoading: false });
    } catch (e: any) {
      set({
        formatsError: e.message || "Failed to load formats",
        formatsLoading: false,
      });
    }
  },

  // ── Upload ───────────────────────────────
  file: null,
  uploadedFileName: null,
  fileId: null,
  isUploading: false,
  uploadProgress: 0,
  uploadError: null,
  setFile: (file) => set({ file, uploadError: null }),
  performUpload: async (file) => {
    set({
      isUploading: true,
      uploadProgress: 0,
      uploadError: null,
      file,
      phase: "uploading",
    });
    try {
      const result = await uploadFile(file, (pct) => {
        set({ uploadProgress: pct });
      });
      set({
        fileId: result.file_id,
        uploadedFileName: result.filename,
        isUploading: false,
        uploadProgress: 100,
      });
      return result.file_id;
    } catch (e: any) {
      set({
        uploadError: e.message || "Upload failed",
        isUploading: false,
      });
      return null;
    }
  },

  // ── Format / params ──────────────────────
  targetFormat: null,
  params: defaultParams(),
  selectFormat: (formatId) => set({ targetFormat: formatId }),
  updateParams: (partial) =>
    set((s) => ({ params: { ...s.params, ...partial } })),
  loadFormatParams: async (formatId) => {
    try {
      const res = await fetchFormatParams(formatId);
      if (res.default_params) {
        set({ params: res.default_params as ConvertParams });
      }
    } catch {
      // keep defaults
    }
  },

  // ── Task ─────────────────────────────────
  taskId: null,
  taskStatus: null,
  phase: "idle",
  progress: 0,
  phaseMessage: "",
  pollInterval: null,
  createAndStartTask: async () => {
    const { fileId, targetFormat, params } = get();
    if (!fileId || !targetFormat) return null;

    try {
      const result = await startTask(fileId, targetFormat, params);
      const taskId = result.id;
      // file_name / file_size are frontend-only display fields (the backend
      // does not return them on TaskResponse). Populate from the locally
      // known upload so the result page can render the original file info
      // even after a refresh — when uploadedFileName/file are null, the
      // result page falls back to its own placeholder.
      const { uploadedFileName, file } = get();
      set({
        taskId,
        taskStatus: {
          ...result,
          file_name: uploadedFileName || file?.name,
          file_size: file?.size,
        },
        phase: "preparing",
        progress: 0,
        phaseMessage: "Preparing conversion...",
      });
      // Start polling. startPolling clears any existing interval first so
      // we never end up with two intervals running concurrently.
      get().startPolling(taskId);
      // Immediate first poll (the interval fires after the first delay).
      await get().pollTask(taskId);
      return taskId;
    } catch (e: any) {
      set({
        phase: "failed",
        phaseMessage: e.message || "Failed to start task",
      });
      return null;
    }
  },
  pollTask: async (taskId) => {
    try {
      const status = await fetchTaskStatus(taskId);
      const phase = phaseFromStatus(status.status, status.progress);
      const msg = phaseMessage(phase, status.progress);
      // Backend reports progress as 0.0–1.0; UI bars/labels expect 0–100.
      const progressPct = Math.round((status.progress ?? 0) * 100);
      // Preserve the frontend-only display fields across polls — the backend
      // does not return file_name/file_size, so without this the result page
      // would lose the original-file info after the first poll overwrites
      // taskStatus.
      const prev = get().taskStatus;
      set({
        taskStatus: {
          ...status,
          file_name: prev?.file_name,
          file_size: prev?.file_size,
        },
        phase,
        progress: progressPct,
        phaseMessage: msg,
      });

      if (
        status.status === "completed" ||
        status.status === "failed"
      ) {
        get().stopPolling();
      }
    } catch {
      // continue polling
    }
  },
  startPolling: (taskId) => {
    // Clear any existing interval first so we never run two at once.
    get().stopPolling();
    const interval = setInterval(() => {
      void get().pollTask(taskId);
    }, 1500);
    set({ pollInterval: interval });
  },
  stopPolling: () => {
    const { pollInterval } = get();
    if (pollInterval) {
      clearInterval(pollInterval);
      set({ pollInterval: null });
    }
  },

  // ── Reset ────────────────────────────────
  reset: () => {
    get().stopPolling();
    set({
      file: null,
      uploadedFileName: null,
      fileId: null,
      isUploading: false,
      uploadProgress: 0,
      uploadError: null,
      targetFormat: null,
      params: defaultParams(),
      taskId: null,
      taskStatus: null,
      phase: "idle",
      progress: 0,
      phaseMessage: "",
    });
  },
}));
