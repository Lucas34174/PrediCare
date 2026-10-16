import { CircleAlert, CircleCheck, Clock3 } from 'lucide-react'
import type { ClaimStatus } from '@/api/types'
import { claimStatusLabels } from '@/lib/config'

const statusStyles = {
  EN_COURS: { icon: Clock3, className: 'border-info bg-info-soft text-info-soft-foreground' },
  PAYEE: { icon: CircleCheck, className: 'border-success bg-success-soft text-success-soft-foreground' },
  REJETEE: { icon: CircleAlert, className: 'border-danger bg-danger-soft text-danger-soft-foreground' },
} satisfies Record<ClaimStatus, { icon: typeof Clock3; className: string }>

export function StatusBadge({ status }: { status: ClaimStatus }) {
  const { icon: Icon, className } = statusStyles[status]
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${className}`}>
      <Icon aria-hidden="true" size={14} />
      {claimStatusLabels[status]}
    </span>
  )
}
