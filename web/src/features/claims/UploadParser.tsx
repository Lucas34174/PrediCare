// web/src/features/claims/UploadParser.tsx
import { useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import { CheckCircle2, FileText, Upload, X, AlertTriangle } from 'lucide-react'
import { extractPdfText } from '@/lib/pdfExtract'
import {
  detectDocumentType,
  parseFacture,
  parseOrdonnance,
  type ParsedDocument,
} from '@/lib/pdfParser'

type Phase = 'idle' | 'reading' | 'done' | 'error'

interface UploadParserProps {
  label: string
  accept: 'FACTURE' | 'ORDONNANCE' | 'BOTH'
  onParsed: (doc: ParsedDocument) => void
  onClear: () => void
  parsedSummary?: string | null
  warnings?: string[]
}

export function UploadParser({
  label,
  accept,
  onParsed,
  onClear,
  parsedSummary,
  warnings = [],
}: UploadParserProps) {
  const [phase, setPhase] = useState<Phase>(parsedSummary ? 'done' : 'idle')
  const [fileName, setFileName] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function processFile(file: File) {
    setError(null)
    setPhase('reading')
    setFileName(file.name)
    try {
      const raw = await extractPdfText(file)
      const type = detectDocumentType(raw)
      if (type === 'UNKNOWN') {
        throw new Error(
          'Le document ne semble être ni une facture ni une ordonnance reconnue.',
        )
      }
      if (accept !== 'BOTH' && type !== accept) {
        throw new Error(
          `Ce fichier semble être une ${type.toLowerCase()}, mais vous avez sélectionné le champ ${accept.toLowerCase()}.`,
        )
      }
      const parsed =
        type === 'FACTURE' ? parseFacture(raw) : parseOrdonnance(raw)
      onParsed(parsed)
      setPhase('done')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Extraction impossible.')
      setPhase('error')
    }
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files?.[0]
    if (f) void processFile(f)
  }

  function onChange(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (f) void processFile(f)
    e.target.value = ''
  }

  function reset() {
    setPhase('idle')
    setFileName(null)
    setError(null)
    onClear()
  }

  return (
    <div className="upload-parser">
      <p className="file-drop-label">{label}</p>

      {phase === 'idle' || phase === 'error' ? (
        <div
          className={`file-drop-zone ${dragging ? 'is-dragging' : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') inputRef.current?.click()
          }}
        >
          <Upload aria-hidden="true" size={26} />
          <strong>Glissez un PDF ou cliquez</strong>
          <small>
            {accept === 'FACTURE' && 'Facture PDF uniquement · 5 Mo max'}
            {accept === 'ORDONNANCE' && 'Ordonnance PDF uniquement · 5 Mo max'}
            {accept === 'BOTH' && 'Facture ou ordonnance PDF · 5 Mo max'}
          </small>
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            onChange={onChange}
            style={{ display: 'none' }}
          />
        </div>
      ) : phase === 'reading' ? (
        <div className="upload-parser-reading">
          <FileText aria-hidden="true" size={20} />
          <div>
            <strong>Analyse de « {fileName} »…</strong>
            <small>Extraction des champs en cours.</small>
          </div>
        </div>
      ) : (
        <div className="upload-parser-done">
          <CheckCircle2 aria-hidden="true" size={20} />
          <div>
            <strong>{parsedSummary ?? 'Document analysé'}</strong>
            <small>{fileName}</small>
          </div>
          <button
            type="button"
            className="file-drop-remove"
            onClick={reset}
            aria-label="Retirer le fichier"
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

      {warnings.length > 0 && phase === 'done' && (
        <ul className="upload-parser-warnings">
          {warnings.map((w) => (
            <li key={w}>
              <AlertTriangle aria-hidden="true" size={13} /> {w}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}