// web/src/components/navigation.ts
import {
  Activity,
  BriefcaseMedical,
  ClipboardCheck,
  FileHeart,
  Gauge,
  FilePlus2,
  Settings,
  Cpu,
  MessageSquare,
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
  ],
  professionnel_sante: [
    { label: 'Mon activité', path: '/app', icon: Activity },
    { label: 'Nouvelle facture', path: '/professionnel-sante/factures/nouvelle', icon: FilePlus2 },
    { label: 'Mes dossiers', path: '/professionnel-sante/dossiers', icon: BriefcaseMedical },
  ],
  assure: [
    { label: 'Mes dossiers', path: '/assure', icon: FileHeart },
    { label: 'Assistant', path: '/assure/chat', icon: MessageSquare },
  ],
  admin: [
    { label: 'Supervision', path: '/admin', icon: Gauge },
    { label: 'Configuration', path: '/admin/config', icon: Settings },
    { label: 'Modèles ML', path: '/admin/models', icon: Cpu },
  ],
}

export const rolePaths: Record<UiRole, string> = {
  gestionnaire: '/gestionnaire',
  professionnel_sante: '/professionnel-sante',
  assure: '/assure',
  admin: '/admin',
}
