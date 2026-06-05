'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, File, X, AlertCircle, CheckCircle2 } from 'lucide-react';
import { useTaskStore } from '@/stores/taskStore';
import clsx from 'clsx';

interface FileUploaderProps {
  onUploadComplete?: (fileId: string) => void;
}

export default function FileUploader({ onUploadComplete }: FileUploaderProps) {
  const {
    file,
    isUploading,
    uploadProgress,
    uploadError,
    setFile,
    performUpload,
  } = useTaskStore();
  const [uploaded, setUploaded] = useState(false);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const f = acceptedFiles[0];
      if (!f) return;
      setFile(f);
      setUploaded(false);
      const fileId = await performUpload(f);
      if (fileId && onUploadComplete) {
        setUploaded(true);
        onUploadComplete(fileId);
      }
    },
    [setFile, performUpload, onUploadComplete]
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject } =
    useDropzone({
      onDrop,
      accept: {
        'application/pdf': ['.pdf'],
        'image/*': ['.png', '.jpg', '.jpeg', '.tiff', '.tif', '.bmp'],
      },
      maxFiles: 1,
      maxSize: 100 * 1024 * 1024, // 100MB
      disabled: isUploading,
    });

  const removeFile = () => {
    setFile(null);
    setUploaded(false);
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      {/* Dropzone */}
      <div
        {...getRootProps()}
        className={clsx(
          'relative border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer transition-all duration-200',
          isDragActive && !isDragReject && 'border-primary-500 bg-primary-50',
          isDragReject && 'border-red-400 bg-red-50',
          !isDragActive &&
            !file &&
            'border-gray-300 hover:border-primary-400 hover:bg-gray-50',
          file && 'border-green-300 bg-green-50',
          isUploading && 'pointer-events-none opacity-60'
        )}
      >
        <input {...getInputProps()} />

        {!file && !isUploading && (
          <div className="space-y-4">
            <div className="flex justify-center">
              <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center">
                <Upload className="w-8 h-8 text-primary-600" />
              </div>
            </div>
            <div>
              <p className="text-lg font-semibold text-gray-700">
                {isDragActive
                  ? 'Drop your file here'
                  : 'Drag & drop your PDF here'}
              </p>
              <p className="text-sm text-gray-500 mt-1">
                or <span className="text-primary-600 font-medium">browse</span>{' '}
                to select a file
              </p>
            </div>
            <p className="text-xs text-gray-400">
              Supports PDF, PNG, JPG, TIFF — up to 100MB
            </p>
          </div>
        )}

        {isDragReject && (
          <div className="flex items-center justify-center gap-2 text-red-600">
            <AlertCircle className="w-5 h-5" />
            <span>Unsupported file type or too large</span>
          </div>
        )}

        {/* Upload progress */}
        {isUploading && (
          <div className="space-y-4">
            <div className="flex items-center justify-center gap-3">
              <File className="w-6 h-6 text-primary-600" />
              <span className="font-medium text-gray-700 truncate max-w-[250px]">
                {file?.name}
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2.5 max-w-sm mx-auto">
              <div
                className="bg-primary-600 h-2.5 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <p className="text-sm text-gray-500">{uploadProgress}% uploaded</p>
          </div>
        )}

        {/* File selected */}
        {file && !isUploading && !uploadError && (
          <div className="space-y-3">
            <div className="flex items-center justify-center gap-3">
              {uploaded ? (
                <CheckCircle2 className="w-6 h-6 text-green-500" />
              ) : (
                <File className="w-6 h-6 text-primary-600" />
              )}
              <span className="font-medium text-gray-700 truncate max-w-[300px]">
                {file.name}
              </span>
              <span className="text-sm text-gray-400">
                {formatFileSize(file.size)}
              </span>
            </div>
            {uploaded && (
              <p className="text-sm text-green-600 font-medium">
                ✓ Upload complete
              </p>
            )}
            {!uploaded && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  removeFile();
                }}
                className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-red-500 transition-colors"
              >
                <X className="w-4 h-4" />
                Remove
              </button>
            )}
          </div>
        )}

        {/* Error */}
        {uploadError && (
          <div className="flex items-center justify-center gap-2 text-red-600 mt-2">
            <AlertCircle className="w-5 h-5" />
            <span>{uploadError}</span>
          </div>
        )}
      </div>
    </div>
  );
}
