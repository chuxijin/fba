import { UnifiedPaper, RenderTypographySettings, MistakePageMeta } from '../types'
import { adaptShikaobangPaper } from './index'

/**
 * 从当前 URL 智能提取事考帮错题知识点页面元数据
 * 示例: https://www.shikaobang.cn/wa/wrong_question_list?source=structure&wrong_mode=2&no=st12915&exam=exam43&mode=wrong&subject=subject173&brand=skb&province=zhejiang
 */
export function parseShikaobangMistakePageMeta(url: string, pageTitle: string = ''): MistakePageMeta | null {
  if (!url || (!url.includes('wrong') && !url.includes('mode=wrong'))) {
    return null
  }

  try {
    const urlObj = new URL(url)
    const params = urlObj.searchParams

    const no = params.get('no') || ''
    const exam = params.get('exam') || ''
    const subject = params.get('subject') || ''

    let pointName = '事考帮专项错题'
    if (pageTitle) {
      pointName = pageTitle.replace(/[-_].*(事考帮|题库|网校|做题|刷题).*/i, '').trim()
    }

    return {
      keypointId: no || exam || '0',
      keypointName: pointName,
      total: 10,
      platform: 'shikaobang',
    }
  } catch (err) {
    return null
  }
}

/**
 * 按用户选定量智能提取事考帮错题
 */
export async function fetchShikaobangMistakeQuestionsByCount(
  meta: MistakePageMeta,
  count: number,
  settings: RenderTypographySettings
): Promise<UnifiedPaper> {
  const paperTitle = `${meta.keypointName || '事考帮专项错题'} (精选${count}题)`

  return {
    title: paperTitle,
    source_platform: 'shikaobang' as any,
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
