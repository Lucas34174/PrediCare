const formatMGA = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 })

export function Money({ amount, className = '' }: { amount: number; className?: string }) {
  return <span className={className}>{formatMGA.format(amount)} MGA</span>
}
