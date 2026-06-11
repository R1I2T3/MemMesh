import { expect, test } from 'vitest';
import { validateFile, normalizeUploadStatus } from './upload';

test('validates file size correctly', () => {
  // Mock File object
  const mockFile = new File(['a'.repeat(100)], 'document.pdf', { type: 'application/pdf' });
  
  // Valid case
  const resValid = validateFile(mockFile, 200);
  expect(resValid.valid).toBe(true);
  expect(resValid.error).toBeUndefined();

  // Too large case
  const resLarge = validateFile(mockFile, 50);
  expect(resLarge.valid).toBe(false);
  expect(resLarge.error).toBe('File size exceeds maximum allowed limit');
});

test('validates file format correctly', () => {
  const mockTxt = new File(['hello'], 'doc.txt');
  const mockZip = new File(['bytes'], 'archive.zip');
  const mockNoExt = new File(['bytes'], 'noext');

  expect(validateFile(mockTxt, 1000).valid).toBe(true);
  expect(validateFile(mockZip, 1000).valid).toBe(false);
  expect(validateFile(mockZip, 1000).error).toBe('Unsupported file format');
  expect(validateFile(mockNoExt, 1000).valid).toBe(false);
});

test('normalizes upload status correctly', () => {
  expect(normalizeUploadStatus('completed')).toBe('completed');
  expect(normalizeUploadStatus('SUCCESS')).toBe('completed');
  expect(normalizeUploadStatus('failed')).toBe('failed');
  expect(normalizeUploadStatus('FAILURE')).toBe('failed');
  expect(normalizeUploadStatus('error')).toBe('failed');
  expect(normalizeUploadStatus('processing')).toBe('processing');
  expect(normalizeUploadStatus('PENDING')).toBe('processing');
});
