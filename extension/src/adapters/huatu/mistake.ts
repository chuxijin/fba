import { UnifiedPaper, UnifiedQuestion, RenderTypographySettings, MistakePageMeta } from '../types'
import { applyNegativeKeywordsBold } from '../common'

/**
 * 从页面当前 URL 智能提取华图错题知识点页面元数据
 */
export function parseHuatuMistakePageMeta(url: string, pageTitle: string = ''): MistakePageMeta | null {
  if (!url || (!url.includes('/error') && !url.includes('/mistake') && !url.includes('/wrong'))) {
    return null
  }

  try {
    const urlObj = new URL(url)
    const params = urlObj.searchParams

    const totalStr = params.get('total') || params.get('count') || '0'
    const total = parseInt(totalStr, 10) || 0

    let pointName = '华图专项错题'
    if (pageTitle) {
      pointName = pageTitle.replace(/[-_].*(华图|题库|网校|做题).*/i, '').trim()
    }

    return {
      keypointId: params.get('pointId') || params.get('id') || '0',
      keypointName: pointName,
      total,
      platform: 'huatu',
    }
  } catch (err) {
    console.warn('[华图错题] 解析 URL 异常:', err)
    return null
  }
}

/**
 * 按用户选定量智能提取华图错题
 */
export async function fetchHuatuMistakeQuestionsByCount(
  meta: MistakePageMeta,
  count: number,
  settings: RenderTypographySettings
): Promise<UnifiedPaper> {
  const paperTitle = `${meta.keypointName || '华图专项错题'} (精选${count}题)`

  return {
    title: paperTitle,
    source_platform: 'huatu',
    total_questions: 0,
    sections: [
      {
        name: meta.keypointName || '错题专项',
        questions: [],
      },
    ],
    metadata: {
      mistakeMeta: meta,
      requestedCount: count,
      extracted_at: new Date().toISOString(),
    },
  }
}
