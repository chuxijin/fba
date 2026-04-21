import { fbaApi } from '@/api/sdk'
import {
  getStudyDomainOption,
  normalizeStudyDomainCode,
  type StudyDomainCode,
} from '@/utils/studyDomain'

export type StudyDomainScopeType = 'product_catalog' | 'knowledge_point' | 'resource_exam'

export interface StudyDomainCategoryNode {
  id: number
  parent_id: number | null
  name: string
  code?: string | null
  type: string
  children?: StudyDomainCategoryNode[] | null
}

interface BankNode {
  id: number
  cat_id: number
  name: string
  children?: BankNode[] | null
}

interface GroupTreeNode {
  id: number | null
  name: string
  count: number
  bank_id?: number | null
  children: GroupTreeNode[]
}

interface StudyDomainScopeResponse {
  code: StudyDomainCode
  label: string
  app_code: string
  product_catalog_codes: string[]
  knowledge_point_codes: string[]
  resource_exam_codes: string[]
  product_catalog_roots: StudyDomainCategoryNode[]
  knowledge_point_roots: StudyDomainCategoryNode[]
  resource_exam_roots: StudyDomainCategoryNode[]
}

export interface StudyDomainQuestionScope {
  code: StudyDomainCode
  label: string
  bankIdSet: Set<number>
  knowledgeRootNameSet: Set<string>
  knowledgeNameSet: Set<string>
}

const scopePromiseMap = new Map<StudyDomainCode, Promise<StudyDomainScopeResponse>>()
const questionScopePromiseMap = new Map<StudyDomainCode, Promise<StudyDomainQuestionScope>>()
let bankTreePromise: Promise<BankNode[]> | null = null

function cloneCategoryTree<T extends StudyDomainCategoryNode>(nodes: T[] | null | undefined): T[] {
  return (nodes || []).map(node => ({
    ...node,
    children: cloneCategoryTree(node.children as T[] | null | undefined),
  }))
}

function cloneGroupTreeNodes(nodes: GroupTreeNode[] | null | undefined): GroupTreeNode[] {
  return (nodes || []).map(node => ({
    ...node,
    children: cloneGroupTreeNodes(node.children),
  }))
}

function flattenBankTree(nodes: BankNode[] | null | undefined): BankNode[] {
  const result: BankNode[] = []

  for (const node of nodes || []) {
    result.push(node)
    if (node.children?.length) {
      result.push(...flattenBankTree(node.children))
    }
  }

  return result
}

function collectCategoryIds(nodes: StudyDomainCategoryNode[] | null | undefined): Set<number> {
  const ids = new Set<number>()

  const walk = (list: StudyDomainCategoryNode[] | null | undefined) => {
    for (const node of list || []) {
      ids.add(Number(node.id))
      if (node.children?.length) {
        walk(node.children)
      }
    }
  }

  walk(nodes)
  return ids
}

function collectCategoryNames(nodes: StudyDomainCategoryNode[] | null | undefined): Set<string> {
  const names = new Set<string>()

  const walk = (list: StudyDomainCategoryNode[] | null | undefined) => {
    for (const node of list || []) {
      const name = String(node.name || '').trim()
      if (name) {
        names.add(name)
      }
      if (node.children?.length) {
        walk(node.children)
      }
    }
  }

  walk(nodes)
  return names
}

function sumGroupCounts(nodes: GroupTreeNode[] | null | undefined): number {
  return (nodes || []).reduce((sum, node) => sum + Number(node.count || 0), 0)
}

async function getBankTree(): Promise<BankNode[]> {
  if (!bankTreePromise) {
    bankTreePromise = fbaApi.qbank.bank.getList({ status: 1 }) as Promise<BankNode[]>
  }

  return await bankTreePromise
}

export async function getStudyDomainScope(value: unknown): Promise<StudyDomainScopeResponse> {
  const code = normalizeStudyDomainCode(value)
  const cachedPromise = scopePromiseMap.get(code)
  if (cachedPromise) {
    return await cachedPromise
  }

  const scopePromise = (async () => {
    const data = await fbaApi.qbank.request.get<StudyDomainScopeResponse>('/study-domains/scope', {
      params: { code },
    })

    return {
      ...data,
      code: normalizeStudyDomainCode(data?.code || code),
      label: String(data?.label || getStudyDomainOption(code).label),
      product_catalog_roots: cloneCategoryTree(data?.product_catalog_roots),
      knowledge_point_roots: cloneCategoryTree(data?.knowledge_point_roots),
      resource_exam_roots: cloneCategoryTree(data?.resource_exam_roots),
      product_catalog_codes: [...(data?.product_catalog_codes || [])],
      knowledge_point_codes: [...(data?.knowledge_point_codes || [])],
      resource_exam_codes: [...(data?.resource_exam_codes || [])],
    }
  })()

  scopePromiseMap.set(code, scopePromise)
  return await scopePromise
}

export async function getStudyDomainCategoryRoots(
  value: unknown,
  allowedTypes: readonly StudyDomainScopeType[],
): Promise<StudyDomainCategoryNode[]> {
  const scope = await getStudyDomainScope(value)
  const result: StudyDomainCategoryNode[] = []

  for (const type of allowedTypes) {
    if (type === 'product_catalog') {
      result.push(...cloneCategoryTree(scope.product_catalog_roots))
      continue
    }

    if (type === 'knowledge_point') {
      result.push(...cloneCategoryTree(scope.knowledge_point_roots))
      continue
    }

    result.push(...cloneCategoryTree(scope.resource_exam_roots))
  }

  return result
}

export async function getStudyDomainQuestionScope(value: unknown): Promise<StudyDomainQuestionScope> {
  const code = normalizeStudyDomainCode(value)
  const cachedPromise = questionScopePromiseMap.get(code)
  if (cachedPromise) {
    return await cachedPromise
  }

  const scopePromise = (async () => {
    const [domainScope, bankTree] = await Promise.all([
      getStudyDomainScope(code),
      getBankTree(),
    ])

    const allowedCategoryIds = collectCategoryIds(domainScope.product_catalog_roots)
    const bankIdSet = new Set<number>()
    for (const bank of flattenBankTree(bankTree)) {
      if (allowedCategoryIds.has(Number(bank.cat_id))) {
        bankIdSet.add(Number(bank.id))
      }
    }

    const knowledgeRootNameSet = new Set(
      domainScope.knowledge_point_roots
        .map(item => String(item.name || '').trim())
        .filter(Boolean),
    )

    return {
      code,
      label: domainScope.label,
      bankIdSet,
      knowledgeRootNameSet,
      knowledgeNameSet: collectCategoryNames(domainScope.knowledge_point_roots),
    }
  })()

  questionScopePromiseMap.set(code, scopePromise)
  return await scopePromise
}

export function filterGroupTreeByStudyDomain(
  nodes: GroupTreeNode[] | null | undefined,
  scope: StudyDomainQuestionScope,
  mode: 'bank' | 'knowledge_point',
): GroupTreeNode[] {
  if (mode === 'knowledge_point') {
    return cloneGroupTreeNodes(nodes).filter(node => scope.knowledgeRootNameSet.has(String(node.name || '').trim()))
  }

  const walk = (list: GroupTreeNode[] | null | undefined): GroupTreeNode[] => {
    const result: GroupTreeNode[] = []

    for (const node of list || []) {
      const children = walk(node.children)
      const bankId = Number(node.bank_id ?? node.id ?? 0)
      const matched = bankId > 0 && scope.bankIdSet.has(bankId)

      if (!matched && !children.length) {
        continue
      }

      result.push({
        ...node,
        count: matched ? Number(node.count || 0) : sumGroupCounts(children),
        children: matched ? cloneGroupTreeNodes(node.children) : children,
      })
    }

    return result
  }

  return walk(nodes)
}

export function sumFilteredGroupCounts(nodes: GroupTreeNode[] | null | undefined): number {
  return sumGroupCounts(nodes)
}

export function filterRenderJobsByStudyDomain<T extends { metadata?: Record<string, unknown> | null }>(
  jobs: T[] | null | undefined,
  scope: StudyDomainQuestionScope,
): T[] {
  return (jobs || []).filter((job) => {
    const metadata = job.metadata || {}
    const studyDomain = normalizeStudyDomainCode(metadata.study_domain)
    if (metadata.study_domain && studyDomain === scope.code) {
      return true
    }

    const bankId = Number(metadata.bank_id || 0)
    if (bankId > 0) {
      return scope.bankIdSet.has(bankId)
    }

    const knowledgePoint = metadata.knowledge_point
    if (Array.isArray(knowledgePoint)) {
      return knowledgePoint.some(item => scope.knowledgeNameSet.has(String(item || '').trim()))
    }

    const knowledgePointName = String(knowledgePoint || '').trim()
    if (knowledgePointName) {
      return scope.knowledgeNameSet.has(knowledgePointName)
    }

    return false
  })
}
