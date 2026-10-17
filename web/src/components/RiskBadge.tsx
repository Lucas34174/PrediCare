import { CircleAlert, CircleCheck } from 'lucide-react'

export function RiskBadge({ anomaly }: { anomaly: boolean }) {
  const Icon = anomaly ? CircleAlert : CircleCheck
  const style = anomaly
    ? 'border-warning bg-warning-soft text-warning-soft-foreground'
    : 'border-success bg-success-soft text-success-soft-foreground'

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${style}`}>
      <Icon aria-hidden="true" size={14} />
      {anomaly ? 'Signal à examiner' : 'Aucun signal d’anomalie'}
    </span>
  )
}
