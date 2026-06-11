export function validateFile(file: File | null, maxBytes: number): { valid: boolean; error?: string } {
  if (!file) {
    return { valid: false, error: 'No file selected' };
  }
  if (file.size > maxBytes) {
    return { valid: false, error: 'File size exceeds maximum allowed limit' };
  }
  const allowedExtensions = ['.pdf', '.docx', '.txt', '.md', '.xlsx', '.pptx'];
  const dotIndex = file.name.lastIndexOf('.');
  if (dotIndex === -1) {
    return { valid: false, error: 'Unsupported file format' };
  }
  const ext = file.name.substring(dotIndex).toLowerCase();
  if (!allowedExtensions.includes(ext)) {
    return { valid: false, error: 'Unsupported file format' };
  }
  return { valid: true };
}

export function normalizeUploadStatus(status: string): 'processing' | 'completed' | 'failed' {
  const s = status.toLowerCase();
  if (s === 'completed' || s === 'success') return 'completed';
  if (s === 'failed' || s === 'failure' || s === 'error') return 'failed';
  return 'processing';
}
