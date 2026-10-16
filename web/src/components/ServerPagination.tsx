import { ChevronLeft, ChevronRight } from 'lucide-react'

interface ServerPaginationProps {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
  label?: string
}

export function ServerPagination({ page, pageSize, total, onPageChange, label = 'Résultats' }: ServerPaginationProps) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize))
  const firstItem = total === 0 ? 0 : (page - 1) * pageSize + 1
  const lastItem = Math.min(page * pageSize, total)

  return (
    <nav className="flex flex-wrap items-center justify-between gap-3" aria-label="Pagination des résultats">
      <p className="text-sm text-muted-foreground" aria-live="polite">
        {label} : {firstItem}–{lastItem} sur {total}
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="inline-flex min-h-9 items-center gap-1 rounded-md border border-border bg-card px-3 text-sm text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="Page précédente"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft aria-hidden="true" size={16} /> Précédent
        </button>
        <span className="min-w-20 text-center text-sm text-foreground" aria-current="page">
          {page} / {pageCount}
        </span>
        <button
          type="button"
          className="inline-flex min-h-9 items-center gap-1 rounded-md border border-border bg-card px-3 text-sm text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="Page suivante"
          disabled={page >= pageCount}
          onClick={() => onPageChange(page + 1)}
        >
          Suivant <ChevronRight aria-hidden="true" size={16} />
        </button>
      </div>
    </nav>
  )
}
