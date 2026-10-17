import { CircleAlert, CircleCheck, CircleHelp } from 'lucide-react'

const signalStyles = {
  anomaly: {
    Icon: CircleAlert,
    label: 'Signal à examiner',
    className: 'border-warning bg-warning-soft text-warning-soft-foreground',
  },
  clear: {
    Icon: CircleCheck,
    label: 'Aucun signal d’anomalie',
    className: 'border-success bg-success-soft text-success-soft-foreground',
  },
  unknown: {
    Icon: CircleHelp,
    label: 'Analyse non disponible',
    className: 'border-border bg-muted text-muted-foreground',
  },
} as const

/**
 * `anomaly` accepte null : le contrat renvoie un booléen nullable et une absence
 * de valeur ne doit jamais s'afficher comme « aucun signal d'anomalie ».
 */
export function RiskBadge({ anomaly }: { anomaly: boolean | null | undefined }) {
  const { Icon, label, className } = signalStyles[anomaly === true ? 'anomaly' : anomaly === false ? 'clear' : 'unknown']

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${className}`}>
      <Icon aria-hidden="true" size={14} />
      {label}
    </span>
  )
}
