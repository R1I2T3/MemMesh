import { useRef } from 'react';
import { UploadIcon, Loader2Icon, FileUpIcon } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { AlertBanner } from '@/components/shared/AlertBanner';

interface UploadZoneProps {
  onUpload: (file: File) => void;
  uploading: boolean;
  error: string;
  success: string;
  disabled?: boolean;
}

export function UploadZone({ onUpload, uploading, error, success, disabled }: UploadZoneProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const files = fileInputRef.current?.files;
    if (!files || files.length === 0) return;
    onUpload(files[0]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <Card className="lg:col-span-1 border-border/80 shadow-sm bg-card">
      <form onSubmit={handleSubmit}>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm flex items-center gap-2">
            <div className="flex items-center justify-center rounded-lg bg-primary/10 p-1.5 text-primary">
              <FileUpIcon className="size-4" />
            </div>
            Ingest New File
          </CardTitle>
          <CardDescription className="text-[11px]">
            Files must not exceed size limits.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <AlertBanner type="error" message={error} />
          <AlertBanner type="success" message={success} />

          <div className="flex flex-col gap-2">
            <label
              htmlFor="file-input"
              className="flex flex-col items-center justify-center gap-3 p-8 rounded-xl border-2 border-dashed border-border/60 hover:border-primary/40 hover:bg-muted/30 transition-all duration-200 cursor-pointer"
            >
              <UploadIcon className="size-8 text-muted-foreground/40" />
              <div className="text-center">
                <p className="text-xs font-medium text-muted-foreground">Click to select a file</p>
                <p className="text-[10px] text-muted-foreground/50 mt-0.5">PDF, DOCX, TXT, MD, XLSX, PPTX up to 50MB</p>
              </div>
            </label>
            <Input
              id="file-input"
              type="file"
              ref={fileInputRef}
              required
              accept=".pdf,.docx,.txt,.md,.xlsx,.pptx"
              className="hidden"
            />
          </div>
        </CardContent>
        <CardFooter>
          <Button
            id="upload-button"
            type="submit"
            disabled={uploading || disabled}
            className="w-full h-9 text-xs font-medium gap-2"
          >
            {uploading ? (
              <>
                <Loader2Icon className="size-4 animate-spin" />
                <span>Uploading...</span>
              </>
            ) : (
              <>
                <UploadIcon className="size-4" />
                <span>Upload Document</span>
              </>
            )}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
