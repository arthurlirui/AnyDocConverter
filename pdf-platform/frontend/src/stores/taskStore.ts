import { create } from "zustand";
import type {
  Format,
  ConvertParams,
  TaskStatus,
  ConversionPhase,
  OCRParams,
  LayoutParams,
  ImageParams,
  FontParams,
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
      language: "chi_sim",
      min_confidence: 0.5,
    },
    layout: {
      preservation: "exact",
      detect_tables: true,
      detect_images: true,
      detect_headers_footers: true,
      reading_order: true,
    },
    image: {
      dpi: 300,
      compression: "jpeg",
      quality: 95,
      color_space: "rgb",
    },
    font: {
      mode: "approximate",
      fallback_font: "NotoSansCJK",
      embed_fonts: true,
      subset_fonts: true,
    },
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
      set({
        taskId,
        taskStatus: result,
        phase: "preparing",
        progress: 0,
        phaseMessage: "Preparing conversion...",
      });
      // Start polling
      get().stopPolling();
      const interval = setInterval(async () => {
        await get().pollTask(taskId);
      }, 1500);
      set({ pollInterval: interval });
      // Immediate first poll
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
      set({
        taskStatus: status,
        phase,
        progress: status.progress,
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
