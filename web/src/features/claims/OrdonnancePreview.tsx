// web/src/features/claims/OrdonnancePreview.tsx
import { FileText, User, Calendar, Stethoscope, Pill } from 'lucide-react'
import type { ParsedOrdonnance } from '@/lib/pdfParser'

interface OrdonnancePreviewProps {
  ordonnance: ParsedOrdonnance
}

export function OrdonnancePreview({ ordonnance }: OrdonnancePreviewProps) {
  return (
    <div className="claim-section" style={{ background: 'var(--surface-soft)', border: '1px dashed var(--line)' }}>
      <div className="claim-section-heading">
        <div>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={18} /> Ordonnance extraite (lecture seule)
          </h2>
          <p>Ces informations ont été extraites du PDF et ne peuvent pas être modifiées ici.</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
        <div className="claim-field">
          <label><User size={12} /> Patient</label>
          <input value={ordonnance.patient_nom} readOnly disabled />
        </div>
        <div className="claim-field">
          <label><Calendar size={12} /> Date</label>
          <input value={ordonnance.date} readOnly disabled />
        </div>
        <div className="claim-field">
          <label><Stethoscope size={12} /> Prescripteur</label>
          <input value={ordonnance.prescripteur} readOnly disabled />
        </div>
        <div className="claim-field">
          <label>N° Ordonnance</label>
          <input value={ordonnance.numero_ordonnance} readOnly disabled />
        </div>
        <div className="claim-field">
          <label>Âge</label>
          <input value={ordonnance.patient_age} readOnly disabled />
        </div>
        <div className="claim-field">
          <label>Validité</label>
          <input value={ordonnance.validite_jours ? `${ordonnance.validite_jours} jours` : '—'} readOnly disabled />
        </div>
      </div>

      <div className="claim-field" style={{ marginBottom: '16px' }}>
        <label>Renseignement clinique</label>
        <input value={ordonnance.renseignement_clinique} readOnly disabled />
      </div>

      <div>
        <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--ink-muted)', display: 'block', marginBottom: '8px' }}>
          <Pill size={12} /> Lignes de prescription
        </label>
        <div style={{ display: 'grid', gap: '8px' }}>
          {ordonnance.lignes.map((ligne, idx) => (
            <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px', background: 'var(--surface)', borderRadius: '8px', border: '1px solid var(--line)' }}>
              <div>
                <strong style={{ fontSize: '12px' }}>{ligne.designation}</strong>
                <div style={{ fontSize: '11px', color: 'var(--ink-muted)' }}>{ligne.posologie}</div>
              </div>
              <span style={{ fontSize: '12px', fontWeight: 600 }}>Qté : {ligne.quantite}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}