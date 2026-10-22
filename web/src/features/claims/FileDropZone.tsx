// web/src/features/claims/FileDropZone.tsx
import { useCallback, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { FileText, Upload, X } from 'lucide-react'

export interface UploadedFileInfo {
  id: string
  name: string
  size: number
}

interface FileDropZoneProps {
  label: string
  hint?: string
  file: UploadedFileInfo | null
  onFile: (file: File) => Promise<void>
  onRemove: () => void
  disabled?: boolean
}

const MAX_SIZE = 5 * 1024 * 1024
const ACCEPT = 'application/pdf,.pdf'

const formatSize = (bytes: number) =>
  bytes < 1024 * 1024
    ? `${Math.round(bytes / 1024)} Ko`
    : `${(bytes / 1024 / 1024).toFixed(1)} Mo`

export function FileDropZone({ label, hint, file, onFile, onRemove, disabled }: FileDropZoneProps) {
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(
    async (f: File) => {
      setError(null)
      if (f.type !== 'application/pdf' && !f.name.toLowerCase().endsWith('.pdf')) {
        setError('Seuls les fichiers PDF sont acceptés.')
        return
      }
      if (f.size > MAX_SIZE) {
        setError(`Fichier trop volumineux (${formatSize(f.size)} > 5 Mo).`)
        return
      }
      try {
        await onFile(f)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Erreur lors du téléversement.')
      }
    },
    [onFile],
  )

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragging(false)
    if (disabled) return
    const f = e.dataTransfer.files?.[0]
    if (f) void handleFile(f)
  }

  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) void handleFile(f)
    e.target.value = ''
  }

  return (
    <div className="file-drop-wrapper">
      <p className="file-drop-label">{label}</p>

      {!file ? (
        <div
          className={`file-drop-zone ${dragging ? 'is-dragging' : ''} ${disabled ? 'is-disabled' : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            if (!disabled) setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => !disabled && inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if ((e.key === 'Enter' || e.key === ' ') && !disabled) inputRef.current?.click()
          }}
        >
          <Upload aria-hidden="true" size={26} />
          <strong>Glissez un PDF ou cliquez</strong>
          <small>{hint ?? 'PDF uniquement · 5 Mo max'}</small>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPT}
            onChange={onChange}
            style={{ display: 'none' }}
            disabled={disabled}
          />
        </div>
      ) : (
        <div className="file-drop-preview">
          <FileText aria-hidden="true" size={20} />
          <div className="file-drop-preview-text">
            <strong>{file.name}</strong>
            <small>{formatSize(file.size)}</small>
          </div>
          <button
            type="button"
            className="file-drop-remove"
            onClick={onRemove}
            aria-label="Supprimer le fichier"
          >
            <X aria-hidden="true" size={16} />
          </button>
        </div>
      )}

      {error && (
        <p className="file-drop-error" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}