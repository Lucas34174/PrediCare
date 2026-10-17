import {
  Activity,
  BriefcaseMedical,
  ClipboardCheck,
  FileHeart,
  Gauge,
  FilePlus2,
  type LucideIcon,
} from 'lucide-react'
import type { UiRole } from '@/api/types'

export interface MenuEntry {
  label: string
  path: string
  icon: LucideIcon
}

export const roleLabels: Record<UiRole, string> = {
  gestionnaire: 'Gestionnaire',
  professionnel_sante: 'Professionnel de santé',
  assure: 'Assuré',
  admin: 'Administrateur',
}

export const roleTitles: Record<UiRole, string> = {
  gestionnaire: 'Vue des remboursements',
  professionnel_sante: 'Activité de votre établissement',
  assure: 'Suivi de votre couverture',
  admin: 'Supervision de la plateforme',
}

export const roleMenus: Record<UiRole, MenuEntry[]> = {
  gestionnaire: [
    { label: 'Vue d’ensemble', path: '/app', icon: Gauge },
    { label: 'Dossiers à examiner', path: '/gestionnaire/dossiers', icon: ClipboardCheck },
    { label: 'Factures', path: '/gestionnaire/factures/nouvelle', icon: FilePlus2 },
  ],
  professionnel_sante: [
    { label: 'Mon activité', path: '/app', icon: Activity },
    { label: 'Mes dossiers', path: '/professionnel-sante', icon: BriefcaseMedical },
  ],
  assure: [
    { label: 'Mon espace', path: '/app', icon: FileHeart },
    { label: 'Mon dossier', path: '/assure', icon: ClipboardCheck },
  ],
  admin: [
    { label: 'Supervision', path: '/app', icon: Gauge },
    { label: 'Administration', path: '/admin', icon: Activity },
  ],
}

export const rolePaths: Record<UiRole, string> = {
  gestionnaire: '/gestionnaire',
  professionnel_sante: '/professionnel-sante',
  assure: '/assure',
  admin: '/admin',
}
