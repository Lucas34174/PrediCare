// web/src/features/claims/JustificatifsSection.tsx
import { FileText, PenLine } from 'lucide-react'
import { FileDropZone } from './FileDropZone'
import { saveFile, deleteFile } from '@/lib/fileStorage'
import type { JustificatifBlock, JustificatifErrors, JustificatifMode } from '@/api/types'

interface JustificatifsSectionProps {
  facture: JustificatifBlock
  ordonnance: JustificatifBlock
  onFactureChange: (next: JustificatifBlock) => void
  onOrdonnanceChange: (next: JustificatifBlock) => void
  errors?: JustificatifErrors
}

function ModeRadio({
  value,
  current,
  onChange,
  icon: Icon,
  label,
  groupName,
}: {
  value: JustificatifMode
  current: JustificatifMode
  onChange: (v: JustificatifMode) => void
  icon: typeof FileText
  label: string
  groupName: string
}) {
  return (
    <label className={`justif-radio ${current === value ? 'is-active' : ''}`}>
      <input
        type="radio"
        name={groupName}
        checked={current === value}
        onChange={() => onChange(value)}
      />
      <Icon aria-hidden="true" size={15} />
      <span>{label}</span>
    </label>
  )
}

function Block({
  title,
  block,
  onChange,
  error,
  groupName,
}: {
  title: string
  block: JustificatifBlock
  onChange: (next: JustificatifBlock) => void
  error?: string
  groupName: string
}) {
  async function handleFile(file: File) {
    const stored = await saveFile(file)
    onChange({
      ...block,
      mode: 'UPLOAD',
      file: { id: stored.id, name: stored.name, size: stored.size },
    })
  }

  async function removeFile() {
    if (block.file) await deleteFile(block.file.id).catch(() => {})
    onChange({ ...block, file: null })
  }

  function setMode(mode: JustificatifMode) {
    if (block.mode === 'UPLOAD' && mode !== 'UPLOAD' && block.file) {
      void deleteFile(block.file.id).catch(() => {})
    }
    onChange({ ...block, mode, file: mode === 'UPLOAD' ? block.file : null })
  }

  function setManual<K extends keyof JustificatifBlock['manual']>(key: K, value: string) {
    onChange({ ...block, manual: { ...block.manual, [key]: value } })
  }

  return (
    <fieldset className="justif-block">
      <legend>{title}</legend>

      <div className="justif-modes">
        <ModeRadio value="NONE" current={block.mode} onChange={setMode} icon={FileText} label="Aucun" groupName={`${groupName}-none`} />
        <ModeRadio value="UPLOAD" current={block.mode} onChange={setMode} icon={FileText} label="Téléverser" groupName={`${groupName}-upload`} />
        <ModeRadio value="MANUAL" current={block.mode} onChange={setMode} icon={PenLine} label="Remplir" groupName={`${groupName}-manual`} />
      </div>

      {block.mode === 'UPLOAD' && (
        <FileDropZone
          label="Fichier PDF"
          file={block.file}
          onFile={handleFile}
          onRemove={() => void removeFile()}
        />
      )}

      {block.mode === 'MANUAL' && (
        <div className="justif-manual">
          <div className="claim-field">
            <label>Numéro</label>
            <input
              value={block.manual.numero}
              onChange={(e) => setManual('numero', e.target.value)}
              placeholder={title === 'Facture' ? 'FAC-2026-00123' : 'ORD-2026-00456'}
            />
          </div>
          <div className="claim-field">
            <label>Date</label>
            <input
              type="date"
              value={block.manual.date}
              onChange={(e) => setManual('date', e.target.value)}
            />
          </div>
          <div className="claim-field">
            <label>Prescripteur / Émetteur</label>
            <input
              value={block.manual.prescripteur}
              onChange={(e) => setManual('prescripteur', e.target.value)}
              placeholder="Dr. Rakoto"
            />
          </div>
          <div className="claim-field justif-notes">
            <label>Notes</label>
            <textarea
              rows={2}
              value={block.manual.notes}
              onChange={(e) => setManual('notes', e.target.value)}
              placeholder="Détails libres…"
            />
          </div>
        </div>
      )}

      {error && <p className="claim-field-error">{error}</p>}
    </fieldset>
  )
}

export function JustificatifsSection({
  facture,
  ordonnance,
  onFactureChange,
  onOrdonnanceChange,
  errors,
}: JustificatifsSectionProps) {
  return (
    <section className="claim-section" aria-labelledby="claim-justif-title">
      <div className="claim-section-heading">
        <span className="claim-section-index">03</span>
        <div>
          <h2 id="claim-justif-title">Justificatifs</h2>
          <p>
            Facture et ordonnance sont <strong>optionnelles</strong>, mais au moins
            l’une des deux doit être fournie (téléversée ou remplie).
          </p>
        </div>
      </div>

      {errors?.general && (
        <div className="claim-summary claim-summary-error" role="alert">
          <strong>Justificatifs manquants</strong>
          <span>{errors.general}</span>
        </div>
      )}

      <div className="justif-grid">
        <Block
          title="Facture"
          block={facture}
          onChange={onFactureChange}
          error={errors?.facture}
          groupName="facture"
        />
        <Block
          title="Ordonnance"
          block={ordonnance}
          onChange={onOrdonnanceChange}
          error={errors?.ordonnance}
          groupName="ordonnance"
        />
      </div>
    </section>
  )
}

/** Helpers exportés pour la validation et la sérialisation. */
export function hasJustificatif(block: JustificatifBlock): boolean {
  if (block.mode === 'UPLOAD') return block.file !== null
  if (block.mode === 'MANUAL') {
    return Boolean(block.manual.numero || block.manual.notes || block.manual.date)
  }
  return false
}

export function toJustificatifRef(
  kind: 'FACTURE' | 'ORDONNANCE',
  block: JustificatifBlock,
) {
  if (block.mode === 'UPLOAD' && block.file) {
    return {
      kind,
      mode: 'UPLOAD' as const,
      fileId: block.file.id,
      fileName: block.file.name,
      fileSize: block.file.size,
    }
  }
  if (block.mode === 'MANUAL') {
    return { kind, mode: 'MANUAL' as const, manual: block.manual }
  }
  return null
}