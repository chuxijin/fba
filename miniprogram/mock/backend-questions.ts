import type { QuestionDetail } from '@/api/types/question'
import { QuestionType } from '@/api/types/question'

/**
 * Mock 题目数据（符合后端格式）
 * 包含所有 6 种题型的完整示例
 */

/** ==================== 单选题 ==================== */
const singleChoiceQuestions: QuestionDetail[] = [
  {
    id: 1,
    bank_id: 1,
    chapter_id: null,
    type_id: QuestionType.Single,
    diff_id: 2,  // 中等难度
    stem: '习近平强调，要"树立大农业观、大食物观，多途径开发食物资源"。这体现的哲学原理是？',
    answer_json: { correct: ['C'] },
    answer_text: 'C',
    analysis: '题干强调"多途径开发食物资源"，体现了从整体、全面、联系的角度看问题，这是系统思维的体现。系统思维要求我们从整体和部分的相互联系中把握事物，强调整体性、关联性、层次性。',
    media_assets: null,
    score: 2.0,
    keyword: '哲学,系统思维,大农业观',
    source: '2024年时政热点',
    year: 2024,
    is_active: true,
    version: 1,
    review_status: 20,  // 已审核
    create_user: 1,
    update_user: null,
    created_time: '2024-01-15T10:00:00',
    updated_time: null,
    options: [
      { id: 1, question_id: 1, label: 'A', content: '极限思维', content_html: null, media_assets: null, is_correct: false, sort_order: 1 },
      { id: 2, question_id: 1, label: 'B', content: '历史思维', content_html: null, media_assets: null, is_correct: false, sort_order: 2 },
      { id: 3, question_id: 1, label: 'C', content: '系统思维', content_html: null, media_assets: null, is_correct: true, sort_order: 3 },
      { id: 4, question_id: 1, label: 'D', content: '逆向思维', content_html: null, media_assets: null, is_correct: false, sort_order: 4 }
    ]
  },
  {
    id: 2,
    bank_id: 1,
    chapter_id: null,
    type_id: QuestionType.Single,
    diff_id: 1,  // 简单
    stem: '2024年中央一号文件指出，要确保国家粮食安全，把中国人的饭碗牢牢端在自己手中。我国粮食产量连续多年保持在（　）万亿斤以上。',
    answer_json: { correct: ['B'] },
    answer_text: 'B',
    analysis: '根据2023年官方数据，我国粮食产量连续多年保持在1.3万亿斤以上，实现了粮食生产"十九连丰"。这是国家粮食安全的重要保障。',
    media_assets: null,
    score: 2.0,
    keyword: '粮食安全,中央一号文件',
    source: '2024年中央一号文件',
    year: 2024,
    is_active: true,
    version: 1,
    review_status: 20,
    create_user: 1,
    update_user: null,
    created_time: '2024-01-15T10:10:00',
    updated_time: null,
    options: [
      { id: 5, question_id: 2, label: 'A', content: '1.2', content_html: null, media_assets: null, is_correct: false, sort_order: 1 },
      { id: 6, question_id: 2, label: 'B', content: '1.3', content_html: null, media_assets: null, is_correct: true, sort_order: 2 },
      { id: 7, question_id: 2, label: 'C', content: '1.4', content_html: null, media_assets: null, is_correct: false, sort_order: 3 },
      { id: 8, question_id: 2, label: 'D', content: '1.5', content_html: null, media_assets: null, is_correct: false, sort_order: 4 }
    ]
  },
  {
    id: 3,
    bank_id: 1,
    chapter_id: null,
    type_id: QuestionType.Single,
    diff_id: 2,
    stem: '在全面建设社会主义现代化国家新征程中，必须把（　）作为重中之重。',
    answer_json: { correct: ['C'] },
    answer_text: 'C',
    analysis: '党的二十大报告明确指出，全面建设社会主义现代化国家，最艰巨最繁重的任务仍然在农村。必须坚持把解决好"三农"问题作为全党工作重中之重。',
    media_assets: null,
    score: 2.0,
    keyword: '三农问题,重中之重',
    source: '党的二十大报告',
    year: 2024,
    is_active: true,
    version: 1,
    review_status: 20,
    create_user: 1,
    update_user: null,
    created_time: '2024-01-15T10:20:00',
    updated_time: null,
    options: [
      { id: 9, question_id: 3, label: 'A', content: '城市建设', content_html: null, media_assets: null, is_correct: false, sort_order: 1 },
      { id: 10, question_id: 3, label: 'B', content: '工业发展', content_html: null, media_assets: null, is_correct: false, sort_order: 2 },
      { id: 11, question_id: 3, label: 'C', content: '农业农村', content_html: null, media_assets: null, is_correct: true, sort_order: 3 },
      { id: 12, question_id: 3, label: 'D', content: '科技创新', content_html: null, media_assets: null, is_correct: false, sort_order: 4 }
    ]
  }
]

/** ==================== 多选题 ==================== */
const multipleChoiceQuestions: QuestionDetail[] = [
  {
    id: 4,
    bank_id: 1,
    chapter_id: null,
    type_id: QuestionType.Multiple,
    diff_id: 3,  // 困难
    stem: '习近平新时代中国特色社会主义思想的核心内容包括哪些方面？（多选）',
    answer_json: { correct: ['A', 'B', 'C', 'D'] },
    answer_text: 'ABCD',
    analysis: '习近平新时代中国特色社会主义思想的核心内容包括：坚持和发展中国特色社会主义，实现中华民族伟大复兴的中国梦，统筹推进"五位一体"总体布局，协调推进"四个全面"战略布局等。选项E"以经济建设为中心"是党的基本路线的内容，不属于核心内容表述。',
    media_assets: null,
    score: 3.0,
    keyword: '习近平新时代中国特色社会主义思想,核心内容',
    source: '党的二十大报告',
    year: 2024,
    is_active: true,
    version: 1,
    review_status: 20,
    create_user: 1,
    update_user: null,
    created_time: '2024-01-15T11:00:00',
    updated_time: null,
    options: [
      { id: 13, question_id: 4, label: 'A', content: '坚持和发展中国特色社会主义', content_html: null, media_assets: null, is_correct: true, sort_order: 1 },
      { id: 14, question_id: 4, label: 'B', content: '实现中华民族伟大复兴的中国梦', content_html: null, media_assets: null, is_correct: true, sort_order: 2 },
      { id: 15, question_id: 4, label: 'C', content: '统筹推进"五位一体"总体布局', content_html: null, media_assets: null, is_correct: true, sort_order: 3 },
      { id: 16, question_id: 4, label: 'D', content: '协调推进"四个全面"战略布局', content_html: null, media_assets: null, is_correct: true, sort_order: 4 },
      { id: 17, question_id: 4, label: 'E', content: '以经济建设为中心', content_html: null, media_assets: null, is_correct: false, sort_order: 5 }
    ]
  },
  {
    id: 5,
    bank_id: 1,
    chapter_id: null,
    type_id: QuestionType.Multiple,
    diff_id: 2,
    stem: '全面建设社会主义现代化国家的战略安排是什么？（多选）',
    answer_json: { correct: ['A', 'B'] },
    answer_text: 'AB',
    analysis: '党的二十大报告明确了分两步走全面建设社会主义现代化国家的战略安排：第一步，从2020到2035年，基本实现社会主义现代化；第二步，从2035年到本世纪中叶，把我国建成富强民主文明和谐美丽的社会主义现代化强国。选项C和D是错误表述。',
    media_assets: null,
    score: 3.0,
    keyword: '战略安排,现代化',
    source: '党的二十大报告',
    year: 2024,
    is_active: true,
    version: 1,
    review_status: 20,
    create_user: 1,
    update_user: null,
    created_time: '2024-01-15T11:10:00',
    updated_time: null,
    options: [
      { id: 18, question_id: 5, label: 'A', content: '从2020到2035年，基本实现社会主义现代化', content_html: null, media_assets: null, is_correct: true, sort_order: 1 },
      { id: 19, question_id: 5, label: 'B', content: '从2035年到本世纪中叶，把我国建成富强民主文明和谐美丽的社会主义现代化强国', content_html: null, media_assets: null, is_correct: true, sort_order: 2 },
      { id: 20, question_id: 5, label: 'C', content: '到2030年，全面建成小康社会', content_html: null, media_assets: null, is_correct: false, sort_order: 3 },
      { id: 21, question_id: 5, label: 'D', content: '到2025年，实现经济总量翻一番', content_html: null, media_assets: null, is_correct: false, sort_order: 4 }
    ]
  }
]

/** ==================== 判断题 ==================== */
const judgementQuestions: QuestionDetail[] = [
  {
    id: 6,
    bank_id: 1,
    chapter_id: null,
    type_id: QuestionType.Judgement,
    diff_id: 1,
    stem: '中国特色社会主义最本质的特征是中国共产党的领导。',
    answer_json: { correct: ['A'] },
    answer_text: '正确',
    analysis: '这一论断正确。党的十九大报告明确指出："中国特色社会主义最本质的特征是中国共产党领导，中国特色社会主义制度的最大优势是中国共产党领导。"这是对中国特色社会主义的深刻认识。',
    media_assets: null,
    score: 1.0,
    keyword: '中国特色社会主义,党的领导',
    source: '党的十九大报告',
    year: 2024,
    is_active: true,
    version: 1,
    review_status: 20,
    create_user: 1,
    update_user: null,
    created_time: '2024-01-15T12:00:00',
    updated_time: null,
    options: [
      { id: 22, question_id: 6, label: 'A', content: '正确', content_html: null, media_assets: null, is_correct: true, sort_order: 1 },
      { id: 23, question_id: 6, label: 'B', content: '错误', content_html: null, media_assets: null, is_correct: false, sort_order: 2 }
    ]
  },
  {
    id: 7,
    bank_id: 1,
    chapter_id: null,
    type_id: QuestionType.Judgement,
    diff_id: 2,
    stem: '我国社会主要矛盾已经转化为人民日益增长的美好生活需要和落后的社会生产之间的矛盾。',
    answer_json: { correct: ['B'] },
    answer_text: '错误',
    analysis: '这一表述错误。党的十九大报告指出，我国社会主要矛盾已经转化为人民日益增长的美好生活需要和"不平衡不充分的发展"之间的矛盾，而不是"落后的社会生产"。这是对我国发展阶段的准确判断。',
    media_assets: null,
    score: 1.0,
    keyword: '社会主要矛盾',
    source: '党的十九大报告',
    year: 2024,
    is_active: true,
    version: 1,
    review_status: 20,
    create_user: 1,
    update_user: null,
    created_time: '2024-01-15T12:10:00',
    updated_time: null,
    options: [
      { id: 24, question_id: 7, label: 'A', content: '正确', content_html: null, media_assets: null, is_correct: false, sort_order: 1 },
      { id: 25, question_id: 7, label: 'B', content: '错误', content_html: null, media_assets: null, is_correct: true, sort_order: 2 }
    ]
  }
]

/** ==================== 填空题 ==================== */
const fillBlankQuestions: QuestionDetail[] = [
  {
    id: 8,
    bank_id: 1,
    chapter_id: null,
    type_id: QuestionType.Fill,
    diff_id: 1,
    stem: '中国共产党的根本宗旨是____。（请填写完整表述）',
    answer_json: { blanks: [{ index: 1, answers: ['全心全意为人民服务'] }] },
    answer_text: '全心全意为人民服务',
    analysis: '中国共产党的根本宗旨是"全心全意为人民服务"。这是党的性质和指导思想的集中体现，是党区别于其他政党的显著标志。',
    media_assets: null,
    score: 2.0,
    keyword: '根本宗旨,为人民服务',
    source: '党章',
    year: 2024,
    is_active: true,
    version: 1,
    review_status: 20,
    create_user: 1,
    update_user: null,
    created_time: '2024-01-15T13:00:00',
    updated_time: null,
    options: []
  },
  {
    id: 9,
    bank_id: 1,
    chapter_id: null,
    type_id: QuestionType.Fill,
    diff_id: 3,
    stem: '党的二十大报告指出，从现在起，中国共产党的中心任务就是____。',
    answer_json: {
      blanks: [{
        index: 1,
        answers: [
          '团结带领全国各族人民全面建成社会主义现代化强国、实现第二个百年奋斗目标，以中国式现代化全面推进中华民族伟大复兴'
        ]
      }]
    },
    answer_text: '团结带领全国各族人民全面建成社会主义现代化强国、实现第二个百年奋斗目标，以中国式现代化全面推进中华民族伟大复兴',
    analysis: '党的二十大明确指出，从现在起，中国共产党的中心任务就是团结带领全国各族人民全面建成社会主义现代化强国、实现第二个百年奋斗目标，以中国式现代化全面推进中华民族伟大复兴。',
    media_assets: null,
    score: 3.0,
    keyword: '中心任务,中国式现代化',
    source: '党的二十大报告',
    year: 2024,
    is_active: true,
    version: 1,
    review_status: 20,
    create_user: 1,
    update_user: null,
    created_time: '2024-01-15T13:10:00',
    updated_time: null,
    options: []
  }
]

/** ==================== 材料题 ==================== */
const materialQuestions: QuestionDetail[] = [
  {
    id: 10,
    bank_id: 1,
    chapter_id: null,
    type_id: QuestionType.Material,
    diff_id: 3,
    stem: '请根据以下材料回答问题：',
    answer_json: {
      materials: [
        '材料一：2023年中央经济工作会议指出，要坚持稳中求进工作总基调，完整、准确、全面贯彻新发展理念，加快构建新发展格局，着力推动高质量发展。',
        '材料二：党的二十大报告强调，高质量发展是全面建设社会主义现代化国家的首要任务。发展是党执政兴国的第一要务。没有坚实的物质技术基础，就不可能全面建成社会主义现代化强国。',
        '材料三：要坚持以推动高质量发展为主题，把实施扩大内需战略同深化供给侧结构性改革有机结合起来，增强国内大循环内生动力和可靠性，提升国际循环质量和水平。'
      ],
      sub_questions: [11, 12]  // 子题ID
    },
    answer_text: null,
    analysis: '本题考查对高质量发展、新发展理念、新发展格局等重要概念的理解。需要结合材料进行分析，把握当前经济工作的总体要求。',
    media_assets: null,
    score: 5.0,
    keyword: '高质量发展,新发展理念,材料分析',
    source: '中央经济工作会议',
    year: 2024,
    is_active: true,
    version: 1,
    review_status: 20,
    create_user: 1,
    update_user: null,
    created_time: '2024-01-15T14:00:00',
    updated_time: null,
    options: []
  },
  // 材料题的子题1
  {
    id: 11,
    bank_id: 1,
    chapter_id: null,
    type_id: QuestionType.Single,
    diff_id: 2,
    stem: '（1）根据材料，我国经济工作的总基调是？',
    answer_json: { correct: ['A'], parent_id: 10 },
    answer_text: 'A',
    analysis: '根据材料一明确指出，要坚持"稳中求进"工作总基调。这是党中央根据我国经济发展阶段特征作出的科学判断。',
    media_assets: null,
    score: 2.0,
    keyword: '稳中求进',
    source: '中央经济工作会议',
    year: 2024,
    is_active: true,
    version: 1,
    review_status: 20,
    create_user: 1,
    update_user: null,
    created_time: '2024-01-15T14:00:00',
    updated_time: null,
    options: [
      { id: 26, question_id: 11, label: 'A', content: '稳中求进', content_html: null, media_assets: null, is_correct: true, sort_order: 1 },
      { id: 27, question_id: 11, label: 'B', content: '又好又快', content_html: null, media_assets: null, is_correct: false, sort_order: 2 },
      { id: 28, question_id: 11, label: 'C', content: '快速发展', content_html: null, media_assets: null, is_correct: false, sort_order: 3 },
      { id: 29, question_id: 11, label: 'D', content: '跨越发展', content_html: null, media_assets: null, is_correct: false, sort_order: 4 }
    ]
  },
  // 材料题的子题2
  {
    id: 12,
    bank_id: 1,
    chapter_id: null,
    type_id: QuestionType.Multiple,
    diff_id: 2,
    stem: '（2）根据材料，推动高质量发展需要？（多选）',
    answer_json: { correct: ['A', 'B', 'C', 'D'], parent_id: 10 },
    answer_text: 'ABCD',
    analysis: '根据三则材料的内容，推动高质量发展需要：完整、准确、全面贯彻新发展理念，加快构建新发展格局，实施扩大内需战略，深化供给侧结构性改革。四个选项都是正确的。',
    media_assets: null,
    score: 3.0,
    keyword: '高质量发展',
    source: '中央经济工作会议',
    year: 2024,
    is_active: true,
    version: 1,
    review_status: 20,
    create_user: 1,
    update_user: null,
    created_time: '2024-01-15T14:00:00',
    updated_time: null,
    options: [
      { id: 30, question_id: 12, label: 'A', content: '完整、准确、全面贯彻新发展理念', content_html: null, media_assets: null, is_correct: true, sort_order: 1 },
      { id: 31, question_id: 12, label: 'B', content: '加快构建新发展格局', content_html: null, media_assets: null, is_correct: true, sort_order: 2 },
      { id: 32, question_id: 12, label: 'C', content: '实施扩大内需战略', content_html: null, media_assets: null, is_correct: true, sort_order: 3 },
      { id: 33, question_id: 12, label: 'D', content: '深化供给侧结构性改革', content_html: null, media_assets: null, is_correct: true, sort_order: 4 }
    ]
  }
]

/** ==================== 问答题 ==================== */
const qaQuestions: QuestionDetail[] = [
  {
    id: 13,
    bank_id: 1,
    chapter_id: null,
    type_id: QuestionType.QA,
    diff_id: 3,
    stem: '请简述中国式现代化的五个重要特征。（要求：条理清晰，表述准确，不少于200字）',
    answer_json: null,
    answer_text: `中国式现代化具有五个重要特征：

第一，人口规模巨大的现代化。我国14亿多人口整体迈进现代化社会，规模超过现有发达国家人口的总和，艰巨性和复杂性前所未有。

第二，全体人民共同富裕的现代化。这是中国特色社会主义的本质要求，也是一个长期的历史过程。要坚持把实现人民对美好生活的向往作为现代化建设的出发点和落脚点。

第三，物质文明和精神文明相协调的现代化。要求物质富足、精神富有是社会主义现代化的根本要求。物质贫困不是社会主义，精神贫乏也不是社会主义。

第四，人与自然和谐共生的现代化。尊重自然、顺应自然、保护自然，是全面建设社会主义现代化国家的内在要求。必须牢固树立和践行绿水青山就是金山银山的理念。

第五，走和平发展道路的现代化。我国不走一些国家通过战争、殖民、掠夺等方式实现现代化的老路，而是坚定站在历史正确的一边、站在人类文明进步的一边。`,
    analysis: '本题考查对中国式现代化特征的全面理解。答题时要注意：1.五个特征要全部答出；2.每个特征要有简要说明；3.表述要准确，体现政治性；4.字数要达到要求。',
    media_assets: null,
    score: 10.0,
    keyword: '中国式现代化,五个特征',
    source: '党的二十大报告',
    year: 2024,
    is_active: true,
    version: 1,
    review_status: 20,
    create_user: 1,
    update_user: null,
    created_time: '2024-01-15T15:00:00',
    updated_time: null,
    options: []
  }
]

/** ==================== 汇总所有题目 ==================== */
export const allBackendQuestions: QuestionDetail[] = [
  ...singleChoiceQuestions,
  ...multipleChoiceQuestions,
  ...judgementQuestions,
  ...fillBlankQuestions,
  ...materialQuestions,
  ...qaQuestions
]

/** ==================== 题库信息 ==================== */
export const mockBankInfo = {
  id: 1,
  name: '2024年时政热点题库',
  description: '包含单选、多选、判断、填空、材料、问答6种题型',
  totalQuestions: allBackendQuestions.length,
  category: '政治',
  coverUrl: ''
}

/** 导出默认数据 */
export default {
  allBackendQuestions,
  mockBankInfo
}
