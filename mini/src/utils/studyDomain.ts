export type StudyDomainCode = 'cet' | 'kaoyan' | 'gongkao' | 'jiaozhi'

export interface StudyDomainOption {
  code: StudyDomainCode
  label: string
  shortLabel: string
  icon: string
  iconClass: string
  bgClass: string
  ringClass: string
}

export const STUDY_DOMAIN_OPTIONS: StudyDomainOption[] = [
  {
    code: 'cet',
    label: '四六级',
    shortLabel: '四六级',
    icon: 'i-carbon-result',
    iconClass: 'text-[#38BDF8]',
    bgClass: 'from-[#EFF6FF] to-[#DBEAFE]',
    ringClass: 'shadow-[0_10px_24px_-16px_rgba(56,189,248,0.75)]',
  },
  {
    code: 'kaoyan',
    label: '考研',
    shortLabel: '考研',
    icon: 'i-carbon-education',
    iconClass: 'text-[#F59E0B]',
    bgClass: 'from-[#FFF7ED] to-[#FFEDD5]',
    ringClass: 'shadow-[0_10px_24px_-16px_rgba(245,158,11,0.75)]',
  },
  {
    code: 'gongkao',
    label: '考公',
    shortLabel: '考公',
    icon: 'i-carbon-document-add',
    iconClass: 'text-[#06B6D4]',
    bgClass: 'from-[#ECFEFF] to-[#CFFAFE]',
    ringClass: 'shadow-[0_10px_24px_-16px_rgba(6,182,212,0.75)]',
  },
  {
    code: 'jiaozhi',
    label: '教资',
    shortLabel: '教资',
    icon: 'i-carbon-notebook-reference',
    iconClass: 'text-[#FB7185]',
    bgClass: 'from-[#FFF1F2] to-[#FFE4E6]',
    ringClass: 'shadow-[0_10px_24px_-16px_rgba(251,113,133,0.75)]',
  },
]

export const DEFAULT_STUDY_DOMAIN: StudyDomainCode = 'gongkao'

export function normalizeStudyDomainCode(value: unknown): StudyDomainCode {
  if (value === 'cet' || value === 'kaoyan' || value === 'gongkao' || value === 'jiaozhi') {
    return value
  }

  if (value === 'jiaoshi') {
    return 'jiaozhi'
  }

  return DEFAULT_STUDY_DOMAIN
}

export function getStudyDomainOption(value: unknown): StudyDomainOption {
  const code = normalizeStudyDomainCode(value)
  return STUDY_DOMAIN_OPTIONS.find(item => item.code === code) || STUDY_DOMAIN_OPTIONS[0]
}
