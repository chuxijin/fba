<script lang="ts" setup>
import { onHide, onLoad, onPullDownRefresh, onUnload } from '@dcloudio/uni-app'
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { fbaApi } from '@/api/sdk'
import type { AnswerSheetGroup, AnswerSheetItem } from '@/components/AnswerSheet.vue'
import FeedbackPopup from '@/components/FeedbackPopup.vue'
import { useMembershipStore } from '@/store'
import { useResultStore } from '@/store/result'
import {
  formatEvaluationScore,
  getPracticeRecordAIEvaluation,
  isSubjectiveQuestionType,
  normalizeStringList,
  recognizeSubjectiveAnswerImage,
  regeneratePracticeRecordAIEvaluation,
  type PracticeAIEvaluation,
} from '@/utils/aiEvaluation'
import { replaceHtmlWithCachedMedia, warmupQuestionMediaCache } from '@/utils/questionMediaCache'

defineOptions({ name: 'PracticeSessionPage' })
definePage({ style: { navigationStyle: 'custom', navigationBarTextStyle: 'black' } })

type PracticeMode = 'exam' | 'practice' | 'memorize' | 'review'
type UserAnswerValue = string | string[]

interface PracticeJudgeResultItem {
  question_id: number
  record_id?: number | null
  correct_answer?: string | string[]
  analysis?: string
  is_correct?: boolean | null
  correct_rate?: number | string | null
  option_select_stats?: Record<string, unknown> | null
  score?: number | string | null
  full_score?: number | string | null
  ai_evaluation_id?: number | null
  summary_text?: string | null
  error_message?: string | null
}

interface BatchUpsertPracticeRecordsResult {
  upserted_count: number
  judge_results: PracticeJudgeResultItem[]
}

interface AnswerState {
  userAnswer?: UserAnswerValue
  answerTime: number
  isAnswered: boolean
  isCorrect: boolean | null
  score: number | null
  locked: boolean
}

const loading = ref(false)
const submitting = ref(false)
const actionQuestionId = ref(0)
const showAnswerSheet = ref(false)
const showFeedbackPopup = ref(false)
const showDraftOverlay = ref(false)
const draftQuestionId = ref(0)
const canvasPenColor = ref('#FF3B30')
const canvasPenWidth = ref(3)
const strokesMap = reactive<Record<number, Array<{ points: Array<{ x: number, y: number }>, color: string, width: number }>>>({})
const sessionId = ref(0)
const autoDestroy = ref(false)
const routeMode = ref<PracticeMode>('practice')
const routeViewMode = ref<'all' | 'wrong'>('all')
const routeWrongQuestionIds = ref<number[]>([])
const routeDisplayTotalCount = ref(0)
const pendingGotoIndex = ref<number | null>(null)
const pendingGotoQuestionId = ref<number | null>(null)
const currentIndex = ref(0)
const isTimingPaused = ref(false)
const session = ref<any>(null)
const questionMap = reactive<Record<number, any>>({})
const materialMap = reactive<Record<number, any>>({})
const materialTabIndex = reactive<Record<number, number>>({})  // 每题当前选中的材料 tab
const solutionMap = reactive<Record<number, any>>({})
const solutionKeyMap = reactive<Record<number, string>>({})
const solutionLoadingMap = reactive<Record<number, boolean>>({})
const aiEvaluationMap = reactive<Record<number, PracticeAIEvaluation | null>>({})
const aiEvaluationLoadingMap = reactive<Record<number, boolean>>({})
const aiEvaluationErrorMap = reactive<Record<number, string>>({})
const ocrLoadingMap = reactive<Record<number, boolean>>({})
const favoritedMap = reactive<Record<number, boolean>>({})
const answerStateMap = reactive<Record<number, AnswerState>>({})
const draftMap = reactive<Record<number, boolean>>({})
const noteMap = reactive<Record<number, any>>({})
const noteLoadingMap = reactive<Record<number, boolean>>({})
const noteEditingMap = reactive<Record<number, boolean>>({})
const noteContentMap = reactive<Record<number, string>>({})
const publicNotesMap = reactive<Record<number, any[]>>({})
const publicNotesLoadingMap = reactive<Record<number, boolean>>({})
const noteTabMap = reactive<Record<number, 'mine' | 'public'>>({})
const activeQuestionStartedAt = ref(Date.now())
const nowTick = ref(Date.now())
const { statusBarHeight } = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
const topInset = statusBarHeight || 20
let tickTimer: ReturnType<typeof setInterval> | null = null

const questions = computed(() => [...(session.value?.session_questions || [])].sort((a, b) => Number(a.seq_no) - Number(b.seq_no)))
const routeWrongQuestionIdSet = computed(() => new Set(routeWrongQuestionIds.value))
const visibleQuestions = computed(() => {
  if (routeViewMode.value !== 'wrong')
    return questions.value
  if (routeWrongQuestionIdSet.value.size > 0)
    return questions.value.filter(item => routeWrongQuestionIdSet.value.has(Number(item.question_id)))
  return questions.value.filter(item => getState(item.question_id).isCorrect === false)
})
const pageTitle = computed(() => session.value?.practice_name || '刷题练习')
const mode = computed<PracticeMode>(() => {
  if (routeMode.value === 'review')
    return 'review'
  return session.value?.session_type === 'exam' ? 'exam' : routeMode.value
})
const isReviewMode = computed(() => mode.value === 'review')
const isCompleted = computed(() => session.value?.status === 'completed')
const totalCount = computed(() => visibleQuestions.value.length)
const displayTotalCount = computed(() => {
  if (routeViewMode.value === 'wrong')
    return totalCount.value

  const routeCount = toNumber(routeDisplayTotalCount.value)
  if (routeCount > 0)
    return routeCount

  const configCount = toNumber(session.value?.exam_config?.display_total_count)
  if (configCount > 0)
    return configCount

  return totalCount.value
})
const questionGroups = computed<AnswerSheetGroup[]>(() => {
  const groups: AnswerSheetGroup[] = []
  let lastChapter: string | null = null
  for (let i = 0; i < visibleQuestions.value.length; i++) {
    const q = visibleQuestions.value[i]
    const chapterName = q.chapter?.name || ''
    if (chapterName !== lastChapter) {
      groups.push({ title: chapterName, items: [] })
      lastChapter = chapterName
    }
    groups[groups.length - 1].items.push({
      id: q.question_id,
      seq_no: q.seq_no,
      status: sheetTone(q.question_id, i),
    })
  }
  return groups
})

function getQuestionIndex(questionId: number) {
  return visibleQuestions.value.findIndex(q => q.question_id === questionId)
}
const currentSnap = computed(() => visibleQuestions.value[currentIndex.value] || null)
const currentQuestionId = computed(() => Number(currentSnap.value?.question_id || 0))
const currentQuestion = computed(() => questionMap[currentQuestionId.value] || null)
const feedbackTargetText = computed(() => {
  const seqNo = Number(currentSnap.value?.seq_no || currentIndex.value + 1 || 1)
  return `${pageTitle.value} 第 ${seqNo} 题`
})
const currentState = computed(() => currentQuestionId.value ? getState(currentQuestionId.value) : null)
const currentSolution = computed(() => solutionMap[currentQuestionId.value] || null)
const materials = computed(() => (currentQuestion.value?.material_ids || []).map((id: number) => materialMap[id]).filter(Boolean))
const selectedCodes = computed(() => toCodes(currentState.value?.userAnswer))
const correctCodes = computed(() => toCodes(currentSolution.value?.correct_answer))
const answeredCount = computed(() => visibleQuestions.value.filter(item => getState(item.question_id).isAnswered).length)
const correctCount = computed(() => visibleQuestions.value.filter(item => getState(item.question_id).isCorrect === true).length)
const wrongCount = computed(() => visibleQuestions.value.filter(item => getState(item.question_id).isCorrect === false).length)
const totalSeconds = computed(() => {
  const base = Object.values(answerStateMap).reduce((sum, item) => sum + toNumber(item.answerTime), 0)
  if (!currentQuestionId.value || isReviewMode.value || isCompleted.value || isTimingPaused.value)
    return base
  return base + Math.max(0, Math.floor((nowTick.value - activeQuestionStartedAt.value) / 1000))
})
const currentSeconds = computed(() => {
  if (!currentState.value)
    return 0
  if (isReviewMode.value || isCompleted.value || isTimingPaused.value)
    return currentState.value.answerTime
  return currentState.value.answerTime + Math.max(0, Math.floor((nowTick.value - activeQuestionStartedAt.value) / 1000))
})
const isMulti = computed(() => currentQuestion.value?.type === 'multiple')
const isText = computed(() => ['fill', 'shortAnswer'].includes(currentQuestion.value?.type || ''))
const locked = computed(() => !currentState.value || isReviewMode.value || isCompleted.value || (mode.value !== 'exam' && currentState.value.locked))
const shouldShowSolution = computed(() => isReviewMode.value || isCompleted.value || mode.value === 'memorize' || (mode.value === 'practice' && currentState.value?.locked))
const textAnswer = computed({
  get: () => typeof currentState.value?.userAnswer === 'string' ? currentState.value.userAnswer : '',
  set: (value: string) => {
    if (!currentState.value || locked.value)
      return
    currentState.value.userAnswer = value
    currentState.value.isCorrect = null
    currentState.value.score = null
  },
})

let canvasCtx: UniApp.CanvasContext | null = null
let currentStroke: { points: Array<{ x: number, y: number }>, color: string, width: number } | null = null

function toNumber(value: unknown) {
  const num = Number(value)
  return Number.isFinite(num) ? num : 0
}

function formatSeconds(value: number) {
  const safe = Math.max(0, Math.floor(value))
  const hours = Math.floor(safe / 3600)
  const minutes = Math.floor((safe % 3600) / 60)
  const seconds = safe % 60
  return [hours, minutes, seconds].map(item => String(item).padStart(2, '0')).join(':')
}

function formatClock(value: number) {
  const safe = Math.max(0, Math.floor(value))
  const minutes = Math.floor(safe / 60)
  const seconds = safe % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
}

function formatDuration(value: number) {
  const safe = Math.max(0, Math.floor(value))
  if (safe < 60)
    return `${safe}秒`
  const minutes = Math.floor(safe / 60)
  const seconds = safe % 60
  return seconds > 0 ? `${minutes}分${seconds}秒` : `${minutes}分`
}

function formatPercent(value: number) {
  return `${Math.round(Number.isFinite(value) ? value : 0)}%`
}

function html(value: unknown) {
  return replaceHtmlWithCachedMedia(String(value || '').replace(/\n/g, '<br/>'))
}

function typeLabel(type?: string) {
  return ({ single: '单选题', multiple: '多选题', judgement: '判断题', fill: '填空题', shortAnswer: '简答题' } as Record<string, string>)[type || ''] || '题目'
}

function formatAnswer(answer: unknown) {
  if (Array.isArray(answer))
    return answer.join('、')
  return String(answer || '未作答')
}

function errorProneOption(stats: Record<string, any> | null | undefined, correctAnswer: unknown) {
  if (!stats || typeof stats !== 'object')
    return null
  const correctCodes = toCodes(correctAnswer)
  let maxCode = ''
  let maxCount = 0
  for (const [code, count] of Object.entries(stats)) {
    const num = Number(count) || 0
    if (!correctCodes.includes(code.toUpperCase()) && num > maxCount) {
      maxCode = code.toUpperCase()
      maxCount = num
    }
  }
  if (!maxCode || maxCount <= 0)
    return null
  const totalSelects = Object.values(stats).reduce((sum: number, v) => sum + (Number(v) || 0), 0)
  const rate = totalSelects > 0 ? Math.round((maxCount / totalSelects) * 100) : 0
  return { code: maxCode, rate }
}

function copyAnalysis(questionId: number) {
  const text = solutionMap[questionId]?.analysis
  if (!text) {
    uni.showToast({ title: '暂无解析内容', icon: 'none' })
    return
  }
  const plain = String(text).replace(/<[^>]+>/g, '').replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').trim()
  uni.setClipboardData({
    data: plain,
    success: () => uni.showToast({ title: '已复制解析', icon: 'success' }),
    fail: () => uni.showToast({ title: '复制失败', icon: 'none' }),
  })
}

function openDraftOverlay(questionId: number) {
  draftQuestionId.value = questionId
  showDraftOverlay.value = true
  nextTick(() => {
    canvasCtx = uni.createCanvasContext('draftCanvas')
    redrawCanvas()
  })
}

function closeDraftOverlay() {
  showDraftOverlay.value = false
  const qid = draftQuestionId.value
  if (getStrokes().length)
    draftMap[qid] = true
  else
    delete draftMap[qid]
  canvasCtx = null
}

function getStrokes() {
  return strokesMap[draftQuestionId.value] || []
}

function redrawCanvas() {
  if (!canvasCtx)
    return
  const systemInfo = uni.getWindowInfo ? uni.getWindowInfo() : uni.getSystemInfoSync()
  canvasCtx.clearRect(0, 0, systemInfo.windowWidth, systemInfo.windowHeight)
  for (const stroke of getStrokes()) {
    if (stroke.points.length < 2)
      continue
    canvasCtx.beginPath()
    canvasCtx.setStrokeStyle(stroke.color)
    canvasCtx.setLineWidth(stroke.width)
    canvasCtx.setLineCap('round')
    canvasCtx.setLineJoin('round')
    canvasCtx.setGlobalAlpha(0.9)
    canvasCtx.moveTo(stroke.points[0].x, stroke.points[0].y)
    for (let i = 1; i < stroke.points.length; i++)
      canvasCtx.lineTo(stroke.points[i].x, stroke.points[i].y)
    canvasCtx.stroke()
  }
  canvasCtx.draw()
}

function onCanvasTouchStart(e: any) {
  const touch = e.touches?.[0] || e.changedTouches?.[0]
  if (!touch)
    return
  currentStroke = {
    points: [{ x: touch.x, y: touch.y }],
    color: canvasPenColor.value,
    width: canvasPenWidth.value,
  }
}

function onCanvasTouchMove(e: any) {
  const touch = e.touches?.[0] || e.changedTouches?.[0]
  if (!touch || !currentStroke || !canvasCtx)
    return
  currentStroke.points.push({ x: touch.x, y: touch.y })
  const pts = currentStroke.points
  if (pts.length >= 2) {
    canvasCtx.beginPath()
    canvasCtx.setStrokeStyle(currentStroke.color)
    canvasCtx.setLineWidth(currentStroke.width)
    canvasCtx.setLineCap('round')
    canvasCtx.setLineJoin('round')
    canvasCtx.setGlobalAlpha(0.9)
    canvasCtx.moveTo(pts[pts.length - 2].x, pts[pts.length - 2].y)
    canvasCtx.lineTo(pts[pts.length - 1].x, pts[pts.length - 1].y)
    canvasCtx.stroke()
    canvasCtx.draw(true)
  }
}

function onCanvasTouchEnd() {
  if (currentStroke && currentStroke.points.length >= 2) {
    if (!strokesMap[draftQuestionId.value])
      strokesMap[draftQuestionId.value] = []
    strokesMap[draftQuestionId.value].push(currentStroke)
  }
  currentStroke = null
}

function undoStroke() {
  const strokes = strokesMap[draftQuestionId.value]
  if (strokes?.length) {
    strokes.pop()
    redrawCanvas()
  }
}

function clearCanvas() {
  strokesMap[draftQuestionId.value] = []
  delete draftMap[draftQuestionId.value]
  redrawCanvas()
}

function isFavorited(questionId: number) {
  return Boolean(favoritedMap[questionId])
}

function questionMaterials(question: any) {
  return (question?.material_ids || []).map((id: number) => materialMap[id]).filter(Boolean)
}

function isQuestionMulti(question: any) {
  return question?.type === 'multiple'
}

function isQuestionText(question: any) {
  return ['fill', 'shortAnswer'].includes(question?.type || '')
}

function isQuestionSubjective(question: any) {
  return isSubjectiveQuestionType(question?.type)
}

function isQuestionLocked(questionId: number) {
  const state = getState(questionId)
  return isReviewMode.value || isCompleted.value || (mode.value !== 'exam' && state.locked)
}

function questionSelectedCodes(questionId: number) {
  return toCodes(getState(questionId).userAnswer)
}

function questionCorrectCodes(questionId: number) {
  return toCodes(solutionMap[questionId]?.correct_answer)
}

function questionShouldShowSolution(questionId: number) {
  if (isReviewMode.value)
    return Boolean(solutionMap[questionId])
  if (isCompleted.value)
    return Boolean(solutionMap[questionId])
  if (mode.value === 'memorize')
    return Boolean(solutionMap[questionId])
  return mode.value === 'practice' && Boolean(getState(questionId).locked)
}

function questionSeconds(questionId: number) {
  const state = getState(questionId)
  if (isReviewMode.value || isCompleted.value || isTimingPaused.value)
    return state.answerTime
  if (questionId !== currentQuestionId.value)
    return state.answerTime
  return state.answerTime + Math.max(0, Math.floor((nowTick.value - activeQuestionStartedAt.value) / 1000))
}

function questionOptionTone(questionId: number, code: string) {
  const selected = questionSelectedCodes(questionId)
  const correct = questionCorrectCodes(questionId)
  if (questionShouldShowSolution(questionId) && correct.length) {
    if (correct.includes(code))
      return 'correct'
    if (selected.includes(code) && !correct.includes(code))
      return 'wrong'
  }
  return selected.includes(code) ? 'selected' : 'default'
}

function questionTextAnswer(questionId: number) {
  const answer = getState(questionId).userAnswer
  return typeof answer === 'string' ? answer : ''
}

function handleQuestionTextInput(questionId: number, event: any) {
  if (isQuestionLocked(questionId))
    return
  const state = getState(questionId)
  state.userAnswer = String(event?.detail?.value || '')
  state.isCorrect = null
  state.score = null
}

function normalizeAnswer(raw: unknown): UserAnswerValue | undefined {
  if (Array.isArray(raw))
    return raw.map(item => String(item || '').trim()).filter(Boolean)
  if (typeof raw === 'string') {
    const value = raw.trim()
    if (!value)
      return undefined
    if (value.startsWith('[') && value.endsWith(']')) {
      try {
        const parsed = JSON.parse(value)
        if (Array.isArray(parsed))
          return parsed.map(item => String(item || '').trim()).filter(Boolean)
      }
      catch {}
    }
    return value
  }
  return undefined
}

function toCodes(raw: unknown) {
  if (Array.isArray(raw))
    return raw.map(item => String(item || '').trim().toUpperCase()).filter(Boolean)
  if (typeof raw === 'string')
    return raw.split(/[\s,，、|/]+/).map(item => item.trim().toUpperCase()).filter(Boolean)
  return []
}

function serializeAnswer(answer?: UserAnswerValue) {
  if (Array.isArray(answer))
    return JSON.stringify(answer)
  return answer || undefined
}

function solutionCacheKey(answer?: UserAnswerValue) {
  return serializeAnswer(answer) || '__EMPTY__'
}

function hasAnswer(answer?: UserAnswerValue) {
  if (Array.isArray(answer))
    return answer.length > 0
  return Boolean(String(answer || '').trim())
}

function getState(questionId: number): AnswerState {
  if (!answerStateMap[questionId]) {
    answerStateMap[questionId] = { userAnswer: undefined, answerTime: 0, isAnswered: false, isCorrect: null, score: null, locked: false }
  }
  return answerStateMap[questionId]
}

function snapshotOf(questionId: number) {
  return questions.value.find(item => item.question_id === questionId)
}

function resolveInitialQuestionIndex() {
  if (!visibleQuestions.value.length)
    return 0

  if (pendingGotoQuestionId.value) {
    const questionIndex = visibleQuestions.value.findIndex(
      item => Number(item.question_id) === pendingGotoQuestionId.value,
    )
    if (questionIndex >= 0)
      return questionIndex
  }

  if (pendingGotoIndex.value !== null)
    return Math.min(Math.max(pendingGotoIndex.value, 0), visibleQuestions.value.length - 1)

  if (routeViewMode.value === 'wrong')
    return 0

  const firstUnanswered = visibleQuestions.value.findIndex(item => !getState(item.question_id).isAnswered)
  return firstUnanswered >= 0 ? firstUnanswered : 0
}

function questionProgressLabel(item: any, index: number) {
  if (routeViewMode.value === 'wrong')
    return `错题 ${index + 1}/${totalCount.value}`
  return `${item.seq_no}/${displayTotalCount.value}`
}

function parseNumberList(value: unknown) {
  return String(value || '')
    .split(',')
    .map(item => Number(item))
    .filter(item => Number.isFinite(item) && item > 0)
}

function recordOf(questionId: number) {
  return session.value?.records?.find((item: any) => Number(item?.question_id) === questionId) || null
}

function recordIdOf(questionId: number) {
  const recordId = Number(recordOf(questionId)?.id || 0)
  return recordId > 0 ? recordId : 0
}

function getAIEvaluation(questionId: number) {
  return aiEvaluationMap[questionId] || null
}

function aiEvaluationFailed(questionId: number) {
  return getAIEvaluation(questionId)?.status === 'failed'
}

function aiEvaluationMessage(questionId: number) {
  const loading = aiEvaluationLoadingMap[questionId]
  if (loading)
    return '生成中'
  if (aiEvaluationErrorMap[questionId])
    return '生成失败'
  if (aiEvaluationFailed(questionId))
    return '无法生成'
  if (getAIEvaluation(questionId))
    return '已生成'
  return '待生成'
}

function aiEvaluationPayload(questionId: number) {
  return getAIEvaluation(questionId)?.result_payload || null
}

function subjectiveScoreText(questionId: number) {
  const evaluation = getAIEvaluation(questionId)
  return formatEvaluationScore(evaluation?.score, evaluation?.max_score)
}

function subjectiveStrengths(questionId: number) {
  return normalizeStringList(aiEvaluationPayload(questionId)?.strengths)
}

function subjectiveMissingPoints(questionId: number) {
  return normalizeStringList(aiEvaluationPayload(questionId)?.missing_points)
}

function subjectiveSuggestions(questionId: number) {
  return normalizeStringList(aiEvaluationPayload(questionId)?.improvement_suggestions)
}

function subjectiveReferenceAnswer(questionId: number) {
  const payload = aiEvaluationPayload(questionId)
  return String(payload?.reference_answer || '').trim()
}

function subjectiveGradingSummary(questionId: number) {
  const payload = aiEvaluationPayload(questionId)
  return String(payload?.grading_summary || getAIEvaluation(questionId)?.summary_text || '').trim()
}

function subjectiveEncouragement(questionId: number) {
  const payload = aiEvaluationPayload(questionId)
  return String(payload?.encouragement || '').trim()
}

function clearMap(target: Record<number, any>) {
  Object.keys(target).forEach((key) => {
    delete target[Number(key)]
  })
}

function mergeRecognizedText(originalText: string, nextText: string) {
  const current = originalText.trim()
  const incoming = nextText.trim()
  if (!incoming)
    return current
  if (!current)
    return incoming
  return `${current}\n${incoming}`
}

function commitTime(questionId = currentQuestionId.value) {
  if (!questionId || isReviewMode.value || isCompleted.value || isTimingPaused.value)
    return
  const delta = Math.max(0, Math.floor((Date.now() - activeQuestionStartedAt.value) / 1000))
  if (delta > 0)
    getState(questionId).answerTime += delta
  activeQuestionStartedAt.value = Date.now()
}

function toggleTimerPause() {
  if (!currentQuestionId.value || isReviewMode.value || isCompleted.value)
    return

  if (isTimingPaused.value) {
    activeQuestionStartedAt.value = Date.now()
    isTimingPaused.value = false
    uni.showToast({ title: '已继续计时', icon: 'none' })
    return
  }

  commitTime(currentQuestionId.value)
  isTimingPaused.value = true
  uni.showToast({ title: '已暂停计时', icon: 'none' })
}

function syncRecord(questionId: number) {
  if (!session.value)
    return
  const snap = snapshotOf(questionId)
  if (!snap)
    return
  const state = getState(questionId)
  const index = session.value.records.findIndex((item: any) => item.question_id === questionId)
  const record = {
    id: index >= 0 ? session.value.records[index].id : -questionId,
    session_id: session.value.id,
    seq_no: snap.seq_no,
    question_id: questionId,
    placement_id: snap.placement_id,
    user_answer: Array.isArray(state.userAnswer) ? [...state.userAnswer] : (state.userAnswer || ''),
    is_correct: state.isCorrect,
    score: state.score,
    full_score: snap.full_score,
    answer_time: state.answerTime,
  }
  if (index >= 0)
    session.value.records.splice(index, 1, record)
  else
    session.value.records.push(record)
}

function applySessionSolutions(items: any[]) {
  items.forEach((item) => {
    const questionId = Number(item?.question_id || 0)
    if (!questionId)
      return

    const state = getState(questionId)
    const answer = normalizeAnswer(item.user_answer)
    state.userAnswer = answer
    state.answerTime = toNumber(item.answer_time)
    state.isAnswered = hasAnswer(answer)
    state.isCorrect = typeof item.is_correct === 'boolean' ? item.is_correct : null
    state.score = item.score == null ? null : toNumber(item.score)
    state.locked = true

    solutionMap[questionId] = item
    solutionKeyMap[questionId] = solutionCacheKey(answer)
    syncRecord(questionId)
  })
}

function applyJudgeSolution(questionId: number, answer: UserAnswerValue | undefined, judge: PracticeJudgeResultItem) {
  solutionMap[questionId] = {
    question_id: judge.question_id,
    record_id: judge.record_id || null,
    correct_answer: judge.correct_answer ?? '',
    analysis: judge.analysis ?? '',
    is_correct: typeof judge.is_correct === 'boolean' ? judge.is_correct : null,
    correct_rate: Number(judge.correct_rate || 0),
    option_select_stats: judge.option_select_stats || {},
    score: judge.score ?? null,
    full_score: judge.full_score ?? null,
    ai_evaluation_id: judge.ai_evaluation_id ?? null,
    summary_text: judge.summary_text ?? null,
    error_message: judge.error_message ?? null,
  }
  solutionKeyMap[questionId] = solutionCacheKey(answer)
}

async function loadSolution(questionId: number) {
  if (!questionId)
    return

  try {
    const state = getState(questionId)
    const cacheKey = solutionCacheKey(state.userAnswer)

    if (solutionMap[questionId] && solutionKeyMap[questionId] === cacheKey)
      return solutionMap[questionId]

    if (solutionLoadingMap[questionId])
      return solutionMap[questionId]

    // 优先从 result store 的预取整卷数据中取
    const resultStore = useResultStore()
    const prefetched = resultStore.state.solutionData
    if (resultStore.state.sessionId === sessionId.value && Array.isArray(prefetched)) {
      const found = prefetched.find((item: any) => item.question_id === questionId)
      if (found) {
        solutionMap[questionId] = found
        solutionKeyMap[questionId] = cacheKey
        if (found.is_correct != null) {
          state.isCorrect = found.is_correct
          syncRecord(questionId)
        }
        return found
      }
    }

    if (isReviewMode.value)
      return solutionMap[questionId] || null

    // 降级：请求单题 API
    solutionLoadingMap[questionId] = true
    solutionMap[questionId] = await fbaApi.qbank.question.getSolution(questionId, serializeAnswer(state.userAnswer)) as any
    solutionKeyMap[questionId] = cacheKey

    if (solutionMap[questionId]?.is_correct != null) {
      state.isCorrect = solutionMap[questionId].is_correct
      syncRecord(questionId)
    }

    return solutionMap[questionId]
  }
  catch (error) {
    console.error('加载题目解析失败:', error)
  }
  finally {
    solutionLoadingMap[questionId] = false
  }
}

async function loadAIEvaluation(questionId: number, forceRegenerate = false) {
  if (!questionId)
    return null

  const question = questionMap[questionId]
  if (!isQuestionSubjective(question))
    return null

  const recordId = recordIdOf(questionId)
  if (!recordId)
    return null

  if (!forceRegenerate && aiEvaluationMap[questionId])
    return aiEvaluationMap[questionId]

  if (aiEvaluationLoadingMap[questionId])
    return aiEvaluationMap[questionId] || null

  aiEvaluationLoadingMap[questionId] = true
  aiEvaluationErrorMap[questionId] = ''
  try {
    const evaluation = forceRegenerate
      ? await regeneratePracticeRecordAIEvaluation(recordId)
      : await getPracticeRecordAIEvaluation(recordId)
    aiEvaluationMap[questionId] = evaluation || null
    return evaluation || null
  }
  catch (error: any) {
    const status = Number(error?.response?.status || error?.statusCode || 0)
    if (status === 404) {
      aiEvaluationMap[questionId] = null
      return null
    }

    const message = String(error?.response?.data?.msg || error?.message || 'AI 点评加载失败').trim()
    aiEvaluationErrorMap[questionId] = message
    return null
  }
  finally {
    aiEvaluationLoadingMap[questionId] = false
  }
}

async function maybeLoadCurrentSolution() {
  if (currentQuestionId.value && shouldShowSolution.value)
    await loadSolution(currentQuestionId.value)
}

async function maybeLoadCurrentAIEvaluation() {
  if (!currentQuestionId.value || !shouldShowSolution.value)
    return
  await loadAIEvaluation(currentQuestionId.value)
}

async function regenerateAIEvaluation(questionId: number) {
  try {
    const evaluation = await loadAIEvaluation(questionId, true)
    if (!evaluation) {
      uni.showToast({ title: '当前暂无可生成的 AI 点评', icon: 'none' })
      return
    }
    uni.showToast({ title: 'AI 点评已更新', icon: 'success' })
  }
  catch {
    uni.showToast({ title: 'AI 点评更新失败', icon: 'none' })
  }
}

async function recognizeAnswerFromImages(questionId: number) {
  const question = questionMap[questionId]
  if (!question || !isQuestionSubjective(question) || isQuestionLocked(questionId))
    return
  if (ocrLoadingMap[questionId])
    return

  try {
    const chooseResult = await new Promise<UniApp.ChooseMediaSuccessCallbackResult>((resolve, reject) => {
      uni.chooseMedia({
        count: 3,
        mediaType: ['image'],
        sourceType: ['album', 'camera'],
        success: resolve,
        fail: reject,
      })
    })

    const filePaths = (chooseResult.tempFiles || [])
      .map((item: any) => item.tempFilePath || item.path || '')
      .filter(Boolean)

    if (!filePaths.length)
      return

    ocrLoadingMap[questionId] = true
    const state = getState(questionId)
    const recognizedParts: string[] = []

    for (const filePath of filePaths) {
      const result = await recognizeSubjectiveAnswerImage(filePath)
      if (result?.text?.trim())
        recognizedParts.push(result.text.trim())
    }

    if (!recognizedParts.length) {
      uni.showToast({ title: '未识别到文字，请重试', icon: 'none' })
      return
    }

    state.userAnswer = mergeRecognizedText(
      typeof state.userAnswer === 'string' ? state.userAnswer : '',
      recognizedParts.join('\n'),
    )
    state.isCorrect = null
    state.score = null
    state.isAnswered = hasAnswer(state.userAnswer)
    syncRecord(questionId)
    uni.showToast({ title: '识别结果已填入', icon: 'success' })
  }
  catch (error: any) {
    if (error?.errMsg?.includes('cancel'))
      return

    if (error?.message === 'SUBJECTIVE_OCR_LOGIN_REQUIRED') {
      uni.showToast({ title: '登录后可使用拍照识别', icon: 'none' })
      return
    }

    console.error('主观题 OCR 失败:', error)
    uni.showToast({ title: String(error?.message || '识别失败，请手动输入').slice(0, 20), icon: 'none' })
  }
  finally {
    ocrLoadingMap[questionId] = false
  }
}

async function loadFavoriteStates() {
  if (!sessionId.value)
    return
  try {
    clearMap(favoritedMap)
    const statusMap = await fbaApi.qbank.question.checkFavorites(sessionId.value)
    Object.keys(statusMap || {}).forEach((key) => {
      favoritedMap[Number(key)] = Boolean((statusMap as any)[key])
    })
  }
  catch (error) {
    console.error('加载收藏状态失败:', error)
  }
}

async function loadNotes() {
  if (!sessionId.value)
    return
  try {
    clearMap(noteMap)
    clearMap(noteContentMap)
    const result = await fbaApi.qbank.question.getNotes(sessionId.value) as any
    Object.keys(result || {}).forEach((key) => {
      const qid = Number(key)
      noteMap[qid] = result[key]
      if (result[key]?.content)
        noteContentMap[qid] = result[key].content
    })
  }
  catch (error) {
    console.error('加载笔记失败:', error)
  }
}

async function saveNote(questionId: number) {
  const content = noteContentMap[questionId]
  if (!content?.trim()) {
    uni.showToast({ title: '请输入笔记内容', icon: 'none' })
    return
  }
  noteLoadingMap[questionId] = true
  try {
    const existing = noteMap[questionId]
    if (existing?.id) {
      await fbaApi.qbank.note.update(existing.id, { content } as any)
      noteMap[questionId] = { ...existing, content }
    }
    else {
      const result = await fbaApi.qbank.note.create({ question_id: questionId, content, is_public: false } as any) as any
      noteMap[questionId] = result?.data || { id: Date.now(), question_id: questionId, content, is_public: false }
    }
    noteEditingMap[questionId] = false
    uni.showToast({ title: '笔记已保存', icon: 'success' })
  }
  catch (error) {
    console.error('保存笔记失败:', error)
    uni.showToast({ title: '保存笔记失败', icon: 'none' })
  }
  finally {
    noteLoadingMap[questionId] = false
  }
}

async function toggleNotePublic(questionId: number) {
  const note = noteMap[questionId]
  if (!note?.id)
    return
  const newPublic = !note.is_public
  try {
    await fbaApi.qbank.note.update(note.id, { is_public: newPublic } as any)
    noteMap[questionId] = { ...note, is_public: newPublic }
    uni.showToast({ title: newPublic ? '笔记已公开' : '笔记已设为私密', icon: 'none' })
  }
  catch (error) {
    console.error('切换公开状态失败:', error)
    uni.showToast({ title: '操作失败', icon: 'none' })
  }
}

async function loadPublicNotes(questionId: number) {
  if (publicNotesMap[questionId])
    return
  publicNotesLoadingMap[questionId] = true
  try {
    const result = await fbaApi.qbank.note.getQuestionPublic(questionId) as any
    publicNotesMap[questionId] = result?.data || result || []
  }
  catch (error) {
    console.error('加载公开笔记失败:', error)
    publicNotesMap[questionId] = []
  }
  finally {
    publicNotesLoadingMap[questionId] = false
  }
}

function switchNoteTab(questionId: number, tab: 'mine' | 'public') {
  noteTabMap[questionId] = tab
  if (tab === 'public')
    loadPublicNotes(questionId)
}

async function loadSession() {
  loading.value = true
  try {
    const shouldLoadReviewSolution = routeMode.value === 'review'
    const resultStore = useResultStore()
    const sameResultSession = resultStore.state.sessionId === sessionId.value
    const cachedSolutions = sameResultSession && Array.isArray(resultStore.state.solutionData)
      ? resultStore.state.solutionData
      : null
    const solutionPromise = shouldLoadReviewSolution
      ? cachedSolutions
        ? Promise.resolve(cachedSolutions)
        : fbaApi.qbank.session.getSolution(sessionId.value).catch((error) => {
          console.error('加载整套解析失败:', error)
          uni.showToast({ title: '加载整套解析失败', icon: 'none' })
          return []
        })
      : Promise.resolve([])
    const [detail, content, reviewSolutions] = await Promise.all([
      fbaApi.qbank.session.getDetail(sessionId.value),
      fbaApi.qbank.question.getSessionQuestions(sessionId.value),
      solutionPromise,
    ]) as any
    session.value = detail
    clearMap(answerStateMap)
    clearMap(solutionMap)
    clearMap(solutionKeyMap)
    clearMap(solutionLoadingMap)
    clearMap(aiEvaluationMap)
    clearMap(aiEvaluationLoadingMap)
    clearMap(aiEvaluationErrorMap)
    clearMap(ocrLoadingMap)
    detail.session_questions.forEach((item: any) => {
      answerStateMap[item.question_id] = { userAnswer: undefined, answerTime: 0, isAnswered: false, isCorrect: null, score: null, locked: false }
    })
    detail.records.forEach((record: any) => {
      const state = getState(record.question_id)
      const answer = normalizeAnswer(record.user_answer)
      state.userAnswer = answer
      state.answerTime = toNumber(record.answer_time)
      state.isAnswered = hasAnswer(answer)
      state.isCorrect = typeof record.is_correct === 'boolean' ? record.is_correct : null
      state.score = record.score == null ? null : toNumber(record.score)
      state.locked = isReviewMode.value || (mode.value !== 'exam' && hasAnswer(answer))
    })
    if (shouldLoadReviewSolution && Array.isArray(reviewSolutions)) {
      applySessionSolutions(reviewSolutions)
      resultStore.setResult(
        sessionId.value,
        sameResultSession ? resultStore.state.reportData : null,
        reviewSolutions,
        sameResultSession ? resultStore.state.submitResult : null,
      )
    }
    clearMap(questionMap)
    clearMap(materialMap)
    content.questions.forEach((item: any) => { questionMap[item.question_id] = item })
    content.materials.forEach((item: any) => { materialMap[item.id] = item })
    currentIndex.value = resolveInitialQuestionIndex()
    isTimingPaused.value = false
    activeQuestionStartedAt.value = Date.now()
    await Promise.all([loadFavoriteStates(), loadNotes()])
    await maybeLoadCurrentSolution()
    await maybeLoadCurrentAIEvaluation()

    // 后台预热题目资源缓存（不阻塞渲染）
    const allHtmlContent: string[] = []
    Object.values(questionMap).forEach((q: any) => {
      if (q.stem) allHtmlContent.push(q.stem)
      q.options?.forEach((opt: any) => { if (opt.content) allHtmlContent.push(opt.content) })
    })
    Object.values(materialMap).forEach((m: any) => {
      if (m.content) allHtmlContent.push(m.content)
    })
    warmupQuestionMediaCache(allHtmlContent).catch(() => {})
  }
  catch (error) {
    console.error('加载刷题会话失败:', error)
    uni.showToast({ title: '加载刷题会话失败', icon: 'none' })
  }
  finally {
    loading.value = false
    uni.stopPullDownRefresh()
  }
}

async function persistAnswer(questionId: number, judgeNow: boolean, silent = false) {
  if (isReviewMode.value)
    return false

  const snap = snapshotOf(questionId)
  const state = getState(questionId)
  if (!snap || !hasAnswer(state.userAnswer))
    return false
  if (currentQuestionId.value === questionId)
    commitTime(questionId)
  actionQuestionId.value = questionId
  try {
    const result = await fbaApi.qbank.session.upsertRecords(sessionId.value, {
      session_id: sessionId.value,
      judge_now: judgeNow,
      records: [{
        seq_no: snap.seq_no,
        question_id: snap.question_id,
        placement_id: snap.placement_id,
        user_answer: Array.isArray(state.userAnswer) ? [...state.userAnswer] : (state.userAnswer || ''),
        answer_time: state.answerTime,
      }],
    } as any) as BatchUpsertPracticeRecordsResult

    state.isAnswered = true
    if (judgeNow && mode.value !== 'exam')
      state.locked = true
    const judge = Array.isArray(result?.judge_results)
      ? result.judge_results.find(item => Number(item?.question_id) === questionId) || null
      : null
    if (judge) {
      state.isCorrect = typeof judge.is_correct === 'boolean' ? judge.is_correct : null
      if (judge.score != null)
        state.score = toNumber(judge.score)
      else if (typeof judge.is_correct === 'boolean')
        state.score = judge.is_correct ? toNumber(snap.full_score) : 0
      else
        state.score = null

      aiEvaluationErrorMap[questionId] = judge.error_message ? String(judge.error_message) : ''
    }
    else if (!judgeNow) {
      state.isCorrect = null
      state.score = null
    }
    syncRecord(questionId)
    if (judge?.record_id) {
      const record = recordOf(questionId)
      if (record)
        record.id = Number(judge.record_id)
    }

    if (judgeNow && mode.value !== 'exam') {
      if (judge)
        applyJudgeSolution(questionId, state.userAnswer, judge)
      else
        void loadSolution(questionId)

      if (isQuestionSubjective(questionMap[questionId]) && judge?.record_id)
        void loadAIEvaluation(questionId, true)
    }

    return true
  }
  catch (error) {
    console.error('保存作答失败:', error)
    if (!silent)
      uni.showToast({ title: '保存作答失败', icon: 'none' })
    return false
  }
  finally {
    actionQuestionId.value = 0
  }
}

async function persistDraftIfNeeded() {
  if (isReviewMode.value)
    return true
  if (!currentQuestionId.value || locked.value || !currentQuestion.value || !hasAnswer(currentState.value?.userAnswer))
    return true
  if (isMulti.value || isText.value)
    return await persistAnswer(currentQuestionId.value, false, true)
  return true
}

async function persistDraftForQuestion(questionId: number, silent = true) {
  if (isReviewMode.value)
    return true
  const question = questionMap[questionId]
  if (!question || isQuestionLocked(questionId) || !hasAnswer(getState(questionId).userAnswer))
    return true
  if (isQuestionMulti(question) || isQuestionText(question))
    return await persistAnswer(questionId, false, silent)
  return true
}

function handleOptionClick(code: string) {
  if (!currentQuestion.value || !currentState.value || locked.value)
    return
  if (currentQuestion.value.type === 'multiple') {
    const selected = Array.isArray(currentState.value.userAnswer) ? [...currentState.value.userAnswer] : []
    const index = selected.indexOf(code)
    if (index >= 0)
      selected.splice(index, 1)
    else
      selected.push(code)
    currentState.value.userAnswer = selected.sort()
    currentState.value.isCorrect = null
    currentState.value.score = null
    return
  }
  currentState.value.userAnswer = code
  currentState.value.isCorrect = null
  currentState.value.score = null
  void persistAnswer(currentQuestionId.value, mode.value !== 'exam')
}

function handleQuestionOptionClick(questionId: number, question: any, code: string) {
  if (!question || isQuestionLocked(questionId))
    return

  const state = getState(questionId)
  if (question.type === 'multiple') {
    const selected = Array.isArray(state.userAnswer) ? [...state.userAnswer] : []
    const index = selected.indexOf(code)
    if (index >= 0)
      selected.splice(index, 1)
    else
      selected.push(code)
    state.userAnswer = selected.sort()
    state.isCorrect = null
    state.score = null
    return
  }

  state.userAnswer = code
  state.isCorrect = null
  state.score = null
  void persistAnswer(questionId, mode.value !== 'exam')
}

async function submitCurrentQuestion() {
  if (isReviewMode.value)
    return
  if (!currentQuestionId.value || !hasAnswer(currentState.value?.userAnswer)) {
    uni.showToast({ title: '先完成本题作答', icon: 'none' })
    return
  }
  const ok = await persistAnswer(currentQuestionId.value, mode.value !== 'exam')
  if (ok && mode.value === 'exam')
    uni.showToast({ title: '答案已保存', icon: 'success' })
}

async function submitQuestion(questionId: number) {
  if (isReviewMode.value)
    return
  const state = getState(questionId)
  if (!hasAnswer(state.userAnswer)) {
    uni.showToast({ title: '先完成本题作答', icon: 'none' })
    return
  }
  const ok = await persistAnswer(questionId, mode.value !== 'exam')
  if (ok && mode.value === 'exam')
    uni.showToast({ title: '答案已保存', icon: 'success' })
}

async function goToQuestion(index: number) {
  if (index < 0 || index >= totalCount.value || index === currentIndex.value)
    return
  if (!isReviewMode.value) {
    const ok = await persistDraftIfNeeded()
    if (!ok)
      return
  }
  currentIndex.value = index
  showAnswerSheet.value = false
}

async function handleSwiperChange(event: any) {
  const nextIndex = Number(event?.detail?.current || 0)
  const previousQuestionId = currentQuestionId.value
  if (!isReviewMode.value && previousQuestionId)
    await persistDraftForQuestion(previousQuestionId, true)
  currentIndex.value = nextIndex
  showAnswerSheet.value = false
}

async function submitSession() {
  if (submitting.value || isReviewMode.value || isCompleted.value)
    return
  const ok = await persistDraftIfNeeded()
  if (!ok)
    return
  const confirmed = await new Promise<boolean>((resolve) => {
    uni.showModal({
      title: '确认交卷',
      content: `已作答 ${answeredCount.value}/${totalCount.value} 题，提交后会结束本次练习。`,
      confirmText: '确认提交',
      cancelText: '再看看',
      success: res => resolve(Boolean(res.confirm)),
      fail: () => resolve(false),
    })
  })
  if (!confirmed)
    return
  submitting.value = true
  try {
    const submitResult = await fbaApi.qbank.session.submit(sessionId.value, { total_time: totalSeconds.value } as any) as any
    if (Number(submitResult?.reward_exp || 0) > 0) {
      void useMembershipStore().fetchMembership()
      const checkInReward = Number(submitResult?.check_in_reward_exp || 0)
      const title = checkInReward > 0
        ? `本次 +${submitResult.reward_exp} 经验，已自动签到`
        : `本次 +${submitResult.reward_exp} 经验`
      uni.showToast({ title, icon: 'none' })
    }

    const [reportData, solutionData] = await Promise.all([
      fbaApi.qbank.session.getReport(sessionId.value).catch(() => null),
      fbaApi.qbank.session.getSolution(sessionId.value).catch(() => null),
    ])

    const resultStore = useResultStore()
    resultStore.setResult(sessionId.value, reportData, solutionData, submitResult)
    uni.redirectTo({
      url: `/pages/practice/result/index?sessionId=${sessionId.value}`,
    })
  }
  catch (error) {
    console.error('提交练习失败:', error)
    uni.showToast({ title: '提交练习失败', icon: 'none' })
  }
  finally {
    submitting.value = false
  }
}

async function toggleFavorite(questionId: number) {
  try {
    if (favoritedMap[questionId]) {
      await fbaApi.qbank.favorite.removeByQuestion(questionId)
      favoritedMap[questionId] = false
      uni.showToast({ title: '已取消收藏', icon: 'success' })
      return
    }

    await fbaApi.qbank.favorite.create({ question_id: questionId } as any)
    favoritedMap[questionId] = true
    uni.showToast({ title: '已加入收藏', icon: 'success' })
  }
  catch (error) {
    console.error('切换收藏失败:', error)
    uni.showToast({ title: '操作收藏失败', icon: 'none' })
  }
}

function optionTone(code: string) {
  if (shouldShowSolution.value) {
    if (correctCodes.value.includes(code))
      return 'correct'
    if (selectedCodes.value.includes(code) && !correctCodes.value.includes(code))
      return 'wrong'
  }
  return selectedCodes.value.includes(code) ? 'selected' : 'default'
}

function sheetTone(questionId: number, index: number) {
  if (index === currentIndex.value)
    return 'active'
  const state = getState(questionId)
  if (state.isCorrect === true)
    return 'correct'
  if (state.isCorrect === false)
    return 'wrong'
  return state.isAnswered ? 'answered' : 'default'
}

function handleSheetSelect(item: AnswerSheetItem) {
  const index = visibleQuestions.value.findIndex(q => q.question_id === item.id)
  if (index >= 0)
    goToQuestion(index)
}

function goBack() {
  uni.navigateBack({ fail: () => uni.switchTab({ url: '/pages/practice/index' }) })
}

watch(currentQuestionId, async (newId, oldId) => {
  if (oldId)
    commitTime(oldId)
  activeQuestionStartedAt.value = Date.now()
  if (newId) {
    await maybeLoadCurrentSolution()
    await maybeLoadCurrentAIEvaluation()
  }
})

onLoad((query) => {
  sessionId.value = Number(query?.sessionId || 0)
  const nextMode = String(query?.mode || 'practice')
  routeMode.value = nextMode === 'exam' || nextMode === 'memorize' || nextMode === 'review' ? nextMode : 'practice'
  routeWrongQuestionIds.value = parseNumberList(query?.wrongQuestionIds)
  routeDisplayTotalCount.value = toNumber(query?.displayTotalCount)
  const shouldShowWrongOnly = query?.viewMode === 'wrong' || query?.wrongOnly === '1' || routeWrongQuestionIds.value.length > 0
  routeViewMode.value = shouldShowWrongOnly ? 'wrong' : 'all'
  const gotoIndex = Number(query?.gotoIndex)
  pendingGotoIndex.value = Number.isFinite(gotoIndex) && gotoIndex >= 0 ? gotoIndex : null
  const gotoQuestionId = Number(query?.gotoQuestionId)
  pendingGotoQuestionId.value = Number.isFinite(gotoQuestionId) && gotoQuestionId > 0 ? gotoQuestionId : null
  autoDestroy.value = query?.autoDestroy === '1'
  if (!sessionId.value) {
    uni.showToast({ title: '会话参数不完整', icon: 'none' })
    setTimeout(goBack, 300)
    return
  }
  tickTimer = setInterval(() => { nowTick.value = Date.now() }, 1000)
  loadSession()
})

onPullDownRefresh(() => { loadSession() })
onHide(() => { commitTime() })
onUnload(() => {
  commitTime()
  if (tickTimer)
    clearInterval(tickTimer)
  // 自动销毁临时 session（错题/收藏/笔记入口创建的）
  if (autoDestroy.value && sessionId.value) {
    fbaApi.qbank.session.remove(sessionId.value).catch(() => {})
  }
})
</script>

<template>
  <view class="h-screen flex flex-col overflow-hidden from-[#DAF0E4] via-[#F0F8F4] to-[#F8FCF9] bg-gradient-to-b text-[#334155]">
    <view class="shrink-0 px-5 pb-3" :style="{ paddingTop: `${topInset}px` }">
      <view class="h-11 flex items-center gap-3">
        <view class="h-9 w-9 flex items-center justify-center rounded-full bg-white/92 text-[#475569] shadow-sm active:scale-95" @click="goBack">
          <view class="i-carbon-arrow-left text-[18px]" />
        </view>
        <view class="min-w-0 flex-1">
          <view class="truncate text-[18px] text-[#14532D] font-black">
            {{ pageTitle }}
          </view>
        </view>
        <view class="w-9 shrink-0" />
      </view>
    </view>

    <view v-if="loading" class="mt-4 px-5">
      <view class="border border-white/70 rounded-[24px] bg-white/90 px-5 py-12 text-center shadow-sm">
        <view class="text-[15px] text-[#1E293B] font-bold">
          正在准备题目内容...
        </view>
      </view>
    </view>

    <swiper
      v-else-if="visibleQuestions.length"
      class="flex-1"
      :current="currentIndex"
      :duration="260"
      @change="handleSwiperChange"
    >
      <swiper-item v-for="(item, idx) in visibleQuestions" :key="item.question_id">
        <scroll-view scroll-y class="box-border h-full px-3 pb-8" :show-scrollbar="false">
          <view v-if="questionMap[item.question_id] && Math.abs(idx - currentIndex) <= 1" class="mt-3 flex flex-col gap-3">

            <!-- 卡片 1：题目 -->
            <view class="section-card">
              <view class="flex items-center justify-between gap-3">
                <view class="min-w-0 flex items-center gap-2.5">
                  <view class="rounded-[8px] bg-[#FFF7ED] px-2.5 py-1 text-[11px] text-[#EA580C] font-bold">
                    {{ typeLabel(questionMap[item.question_id].type) }}
                  </view>
                  <view class="text-[15px] text-[#2563EB] font-black">
                    {{ questionProgressLabel(item, idx) }}
                  </view>
                </view>
                <view class="flex shrink-0 items-center gap-2 text-[12px] text-[#64748B]">
                  <view class="flex items-center gap-1 text-[#64748B] font-semibold active:scale-95" @click="toggleTimerPause">
                    <view :class="isTimingPaused ? 'i-carbon-play-filled text-[14px] text-[#F59E0B]' : 'i-carbon-time text-[14px]'" />
                    <text>{{ formatClock(questionSeconds(item.question_id)) }}</text>
                  </view>
                  <view class="h-[32px] w-[32px] flex items-center justify-center border border-[#D7DEE8] rounded-[10px] bg-white text-[#94A3B8] shadow-[0_2px_8px_rgba(15,23,42,0.04)] active:scale-95" @click="openDraftOverlay(item.question_id)">
                    <view class="i-carbon-edit text-[16px]" :class="draftMap[item.question_id] ? 'text-[#2563EB]' : ''" />
                  </view>
                  <view class="h-[32px] w-[32px] flex items-center justify-center border border-[#D7DEE8] rounded-[10px] bg-white shadow-[0_2px_8px_rgba(15,23,42,0.04)] active:scale-95" @click="toggleFavorite(item.question_id)">
                    <view :class="isFavorited(item.question_id) ? 'i-carbon-star-filled text-[16px] text-[#F59E0B]' : 'i-carbon-star text-[16px] text-[#94A3B8]'" />
                  </view>
                  <view class="h-[32px] w-[32px] flex items-center justify-center border border-[#D7DEE8] rounded-[10px] bg-white text-[#94A3B8] shadow-[0_2px_8px_rgba(15,23,42,0.04)] active:scale-95" @click="showAnswerSheet = true">
                    <view class="i-carbon-menu text-[16px]" />
                  </view>
                </view>
              </view>
              <view v-if="questionMaterials(questionMap[item.question_id]).length" class="mt-5">
                <!-- 多材料：tab 切换 -->
                <template v-if="questionMaterials(questionMap[item.question_id]).length > 1">
                  <scroll-view scroll-x class="flex flex-row mb-3 whitespace-nowrap" style="width:100%">
                    <view class="flex flex-row gap-2 pb-1">
                      <view
                        v-for="(mat, mIdx) in questionMaterials(questionMap[item.question_id])"
                        :key="mat.id"
                        class="px-4 py-[6px] rounded-full text-[13px] font-medium transition-all"
                        :class="(materialTabIndex[item.question_id] ?? 0) === mIdx
                          ? 'bg-[#10B981] text-white shadow-sm'
                          : 'bg-[#F0FDF4] text-[#10B981] border border-[#A7F3D0]'"
                        @click="materialTabIndex[item.question_id] = mIdx"
                      >
                        材料{{ mIdx + 1 }}
                      </view>
                    </view>
                  </scroll-view>
                  <view class="overflow-hidden border border-[#D1FAE5] rounded-[20px] bg-[linear-gradient(135deg,rgba(255,251,235,0.98),rgba(255,255,255,0.98))] px-4 py-4 shadow-sm">
                    <rich-text
                      class="session-rich text-[15px] text-[#475569] leading-[1.8]"
                      :nodes="html(questionMaterials(questionMap[item.question_id])[materialTabIndex[item.question_id] ?? 0]?.content)"
                    />
                  </view>
                </template>
                <!-- 单材料：直接展示 -->
                <template v-else>
                  <view class="overflow-hidden border border-[#D1FAE5] rounded-[20px] bg-[linear-gradient(135deg,rgba(255,251,235,0.98),rgba(255,255,255,0.98))] px-4 py-4 shadow-sm">
                    <rich-text class="session-rich text-[15px] text-[#475569] leading-[1.8]" :nodes="html(questionMaterials(questionMap[item.question_id])[0]?.content)" />
                  </view>
                </template>
              </view>
              <rich-text class="session-rich mt-5 text-[16px] text-[#0F172A] font-medium leading-[1.85]" :nodes="html(questionMap[item.question_id].stem)" />
              <view v-if="questionMap[item.question_id].options?.length" class="mt-5 flex flex-col gap-3">
                <view v-for="option in questionMap[item.question_id].options" :key="option.option_code" class="option-card" :class="`tone-${questionOptionTone(item.question_id, option.option_code)}`" @click="handleQuestionOptionClick(item.question_id, questionMap[item.question_id], option.option_code)">
                  <view class="option-code" :class="questionMap[item.question_id].type === 'multiple' ? 'option-code-square' : ''">
                    {{ option.option_code }}
                  </view>
                  <rich-text class="session-rich option-content" :nodes="html(option.content)" />
                </view>
              </view>
              <view v-else-if="isQuestionText(questionMap[item.question_id])" class="mt-5">
                <textarea :value="questionTextAnswer(item.question_id)" class="box-border min-h-[180px] w-full rounded-[20px] bg-[#F8FAFC] px-4 py-4 text-[14px] text-[#0F172A] leading-[1.8]" placeholder="请输入你的答案" :disabled="isQuestionLocked(item.question_id)" :maxlength="-1" auto-height @input="handleQuestionTextInput(item.question_id, $event)" />
                <view
                  v-if="isQuestionSubjective(questionMap[item.question_id]) && !isQuestionLocked(item.question_id)"
                  class="mt-3 flex items-center justify-between gap-3 rounded-[16px] border border-[#D1FAE5] bg-[#F0FDF4] px-4 py-3"
                >
                  <view class="min-w-0">
                    <view class="text-[13px] text-[#166534] font-bold">
                      拍照识别 / 相册识别
                    </view>
                    <view class="mt-1 text-[12px] text-[#15803D] leading-[1.6]">
                      支持拍照或相册导入，最多 3 张，识别后会直接填入答案框，你还可以继续编辑。
                    </view>
                  </view>
                  <view
                    class="shrink-0 inline-flex items-center gap-1 rounded-full bg-[#059669] px-3 py-1.5 text-[12px] text-white font-bold active:scale-95"
                    @click="recognizeAnswerFromImages(item.question_id)"
                  >
                    <view v-if="ocrLoadingMap[item.question_id]" class="i-carbon-circle-dash animate-spin text-[13px]" />
                    <view v-else class="i-carbon-camera text-[13px]" />
                    <text>{{ ocrLoadingMap[item.question_id] ? '识别中...' : '开始识别' }}</text>
                  </view>
                </view>
              </view>
              <view v-if="(isQuestionMulti(questionMap[item.question_id]) || isQuestionText(questionMap[item.question_id])) && !isQuestionLocked(item.question_id)" class="mt-5">
                <view class="h-11 flex items-center justify-center rounded-full bg-[#059669] text-[14px] text-white font-black active:scale-[0.98]" @click="submitQuestion(item.question_id)">
                  {{ actionQuestionId === item.question_id ? '保存中...' : mode === 'exam' ? '保存本题' : '提交本题' }}
                </view>
              </view>
            </view>

            <!-- 卡片 2：选择数据 -->
            <view
              v-if="questionShouldShowSolution(item.question_id) && solutionLoadingMap[item.question_id] && !solutionMap[item.question_id]"
              class="section-card"
            >
              <view class="flex items-center gap-2">
                <view class="i-carbon-circle-dash animate-spin text-[16px] text-[#2563EB]" />
                <view class="text-[15px] text-[#2563EB] font-black">正在加载答案解析</view>
              </view>
              <view class="mt-4 rounded-[16px] bg-[#F8FAFC] px-4 py-4 text-[13px] text-[#64748B] leading-[1.7]">
                本题已提交，正在补充正确答案、解析和统计数据...
              </view>
            </view>

            <view v-if="questionShouldShowSolution(item.question_id) && solutionMap[item.question_id]" class="section-card">
              <view class="flex items-center gap-2">
                <view class="i-carbon-chart-bar text-[16px] text-[#7C3AED]" />
                <view class="text-[15px] text-[#7C3AED] font-black">选择数据</view>
                <view v-if="solutionMap[item.question_id].is_correct != null" class="ml-auto rounded-full px-3 py-1 text-[11px] font-black" :class="solutionMap[item.question_id].is_correct ? 'bg-[#DCFCE7] text-[#15803D]' : 'bg-[#FEE2E2] text-[#DC2626]'">
                  {{ solutionMap[item.question_id].is_correct ? '回答正确' : '回答错误' }}
                </view>
              </view>
              <view class="mt-4 grid grid-cols-4 gap-2">
                <view class="data-cell">
                  <view class="data-cell-label">正确答案</view>
                  <view class="data-cell-value text-[#16A34A]">{{ formatAnswer(solutionMap[item.question_id].correct_answer) }}</view>
                </view>
                <view class="data-cell">
                  <view class="data-cell-label">我的答案</view>
                  <view class="data-cell-value" :class="solutionMap[item.question_id].is_correct === false ? 'text-[#DC2626]' : 'text-[#0F172A]'">{{ formatAnswer(getState(item.question_id).userAnswer) }}</view>
                </view>
                <view class="data-cell">
                  <view class="data-cell-label">答题时间</view>
                  <view class="data-cell-value text-[#0F172A]">{{ formatDuration(getState(item.question_id).answerTime) }}</view>
                </view>
                <view class="data-cell">
                  <view class="data-cell-label">正确率</view>
                  <view class="data-cell-value text-[#2563EB]">{{ formatPercent(Number(solutionMap[item.question_id].correct_rate || 0)) }}</view>
                </view>
              </view>
              <view v-if="errorProneOption(solutionMap[item.question_id].option_select_stats, solutionMap[item.question_id].correct_answer)" class="mt-3 flex items-center gap-2 rounded-[14px] bg-[#FFF7ED] px-3.5 py-2.5">
                <view class="i-carbon-warning-alt text-[14px] text-[#EA580C]" />
                <view class="text-[13px] text-[#9A3412]">
                  易错项：<text class="font-black">{{ errorProneOption(solutionMap[item.question_id].option_select_stats, solutionMap[item.question_id].correct_answer)?.code }}</text>
                  <text class="ml-1 text-[#B45309]">({{ errorProneOption(solutionMap[item.question_id].option_select_stats, solutionMap[item.question_id].correct_answer)?.rate }}% 选择率)</text>
                </view>
              </view>
            </view>

            <view
              v-if="questionShouldShowSolution(item.question_id) && isQuestionSubjective(questionMap[item.question_id])"
              class="section-card"
            >
              <view class="flex items-center justify-between gap-3">
                <view class="flex items-center gap-2">
                  <view class="i-carbon-ai-generate text-[16px] text-[#0F766E]" />
                  <view class="text-[15px] text-[#0F766E] font-black">AI 主观题点评</view>
                </view>
                <view
                  class="rounded-full px-3 py-1 text-[11px] font-black"
                  :class="aiEvaluationLoadingMap[item.question_id]
                    ? 'bg-[#EFF6FF] text-[#2563EB]'
                    : aiEvaluationErrorMap[item.question_id]
                      ? 'bg-[#FEF2F2] text-[#DC2626]'
                      : aiEvaluationFailed(item.question_id)
                        ? 'bg-[#FEF2F2] text-[#DC2626]'
                        : getAIEvaluation(item.question_id)
                        ? 'bg-[#ECFDF5] text-[#059669]'
                        : 'bg-[#F8FAFC] text-[#64748B]'"
                >
                  {{ aiEvaluationMessage(item.question_id) }}
                </view>
              </view>

              <view v-if="aiEvaluationLoadingMap[item.question_id]" class="mt-4 rounded-[16px] bg-[#F8FAFC] px-4 py-4 text-[13px] text-[#64748B]">
                AI 正在整理这道主观题的评分和建议...
              </view>

              <view v-else-if="aiEvaluationErrorMap[item.question_id]" class="mt-4 rounded-[16px] bg-[#FEF2F2] px-4 py-4">
                <view class="text-[13px] text-[#B91C1C] leading-[1.7]">
                  {{ aiEvaluationErrorMap[item.question_id] }}
                </view>
                <view
                  v-if="recordIdOf(item.question_id)"
                  class="mt-3 inline-flex items-center gap-1 rounded-full bg-white px-3 py-1.5 text-[12px] text-[#DC2626] font-bold active:scale-95"
                  @click="regenerateAIEvaluation(item.question_id)"
                >
                  <view class="i-carbon-renew text-[13px]" />
                  <text>重新生成</text>
                </view>
              </view>

              <view v-else-if="aiEvaluationFailed(item.question_id)" class="mt-4 rounded-[16px] bg-[#FEF2F2] px-4 py-4">
                <view class="text-[13px] text-[#B91C1C] leading-[1.7]">
                  {{ getAIEvaluation(item.question_id)?.error_message || '当前题目暂时无法生成稳定的 AI 点评' }}
                </view>
                <view
                  v-if="recordIdOf(item.question_id)"
                  class="mt-3 inline-flex items-center gap-1 rounded-full bg-white px-3 py-1.5 text-[12px] text-[#DC2626] font-bold active:scale-95"
                  @click="regenerateAIEvaluation(item.question_id)"
                >
                  <view class="i-carbon-renew text-[13px]" />
                  <text>重新生成</text>
                </view>
              </view>

              <view v-else-if="getAIEvaluation(item.question_id)" class="mt-4 flex flex-col gap-4">
                <view class="grid grid-cols-2 gap-3">
                  <view class="data-cell">
                    <view class="data-cell-label">AI 得分</view>
                    <view class="data-cell-value text-[#0F766E]">{{ subjectiveScoreText(item.question_id) }}</view>
                  </view>
                  <view class="data-cell">
                    <view class="data-cell-label">评分置信度</view>
                    <view class="data-cell-value text-[#2563EB]">
                      {{ getAIEvaluation(item.question_id)?.confidence != null ? `${Math.round(Number(getAIEvaluation(item.question_id)?.confidence || 0) * 100)}%` : '--' }}
                    </view>
                  </view>
                </view>

                <view v-if="subjectiveReferenceAnswer(item.question_id)" class="rounded-[16px] bg-[#F0FDF4] px-4 py-4">
                  <view class="text-[12px] text-[#16A34A] font-bold">
                    参考答案
                  </view>
                  <AiRichContent class="mt-2 text-[14px] text-[#166534]" :content="subjectiveReferenceAnswer(item.question_id)" />
                </view>

                <view v-if="subjectiveGradingSummary(item.question_id)" class="rounded-[16px] bg-[#F8FAFC] px-4 py-4">
                  <view class="text-[12px] text-[#475569] font-bold">
                    综合点评
                  </view>
                  <AiRichContent class="mt-2 text-[14px] text-[#334155]" :content="subjectiveGradingSummary(item.question_id)" />
                </view>

                <view v-if="subjectiveStrengths(item.question_id).length" class="rounded-[16px] bg-[#ECFDF5] px-4 py-4">
                  <view class="text-[12px] text-[#15803D] font-bold">
                    回答亮点
                  </view>
                  <view class="mt-2 flex flex-col gap-2 text-[13px] text-[#166534]">
                    <view v-for="(line, lineIndex) in subjectiveStrengths(item.question_id)" :key="lineIndex">
                      {{ line }}
                    </view>
                  </view>
                </view>

                <view v-if="subjectiveMissingPoints(item.question_id).length" class="rounded-[16px] bg-[#FFF7ED] px-4 py-4">
                  <view class="text-[12px] text-[#C2410C] font-bold">
                    失分点
                  </view>
                  <view class="mt-2 flex flex-col gap-2 text-[13px] text-[#9A3412]">
                    <view v-for="(line, lineIndex) in subjectiveMissingPoints(item.question_id)" :key="lineIndex">
                      {{ line }}
                    </view>
                  </view>
                </view>

                <view v-if="subjectiveSuggestions(item.question_id).length" class="rounded-[16px] bg-[#EFF6FF] px-4 py-4">
                  <view class="text-[12px] text-[#1D4ED8] font-bold">
                    改进建议
                  </view>
                  <view class="mt-2 flex flex-col gap-2 text-[13px] text-[#1E3A8A]">
                    <view v-for="(line, lineIndex) in subjectiveSuggestions(item.question_id)" :key="lineIndex">
                      {{ line }}
                    </view>
                  </view>
                </view>

                <view v-if="subjectiveEncouragement(item.question_id)" class="rounded-[16px] bg-[#F5F3FF] px-4 py-4 text-[13px] text-[#6D28D9]">
                  <AiRichContent :content="subjectiveEncouragement(item.question_id)" />
                </view>

                <view
                  v-if="recordIdOf(item.question_id)"
                  class="inline-flex items-center gap-1 self-start rounded-full bg-[#0F766E] px-3 py-1.5 text-[12px] text-white font-bold active:scale-95"
                  @click="regenerateAIEvaluation(item.question_id)"
                >
                  <view class="i-carbon-renew text-[13px]" />
                  <text>重新点评</text>
                </view>
              </view>

              <view v-else class="mt-4 rounded-[16px] bg-[#F8FAFC] px-4 py-4 text-[13px] text-[#64748B]">
                暂无 AI 主观题点评，可稍后重试。
              </view>
            </view>

            <!-- 卡片 3：解析 -->
            <view v-if="questionShouldShowSolution(item.question_id) && solutionMap[item.question_id]?.analysis" class="section-card">
              <view class="flex items-center justify-between gap-2">
                <view class="flex items-center gap-2">
                  <view class="i-carbon-idea text-[16px] text-[#1D4ED8]" />
                  <view class="text-[15px] text-[#1D4ED8] font-black">答案解析</view>
                </view>
                <view class="flex items-center gap-2">
                  <view class="flex items-center gap-1 rounded-full bg-[#EFF6FF] border border-[#BFDBFE] px-2.5 py-1 text-[12px] text-[#2563EB] font-bold active:scale-95" @click="copyAnalysis(item.question_id)">
                    <view class="i-carbon-copy text-[13px]" />
                    <text>复制</text>
                  </view>
                  <view class="flex items-center gap-1 rounded-full bg-[#F5F3FF] border border-[#DDD6FE] px-2.5 py-1 text-[12px] text-[#8B5CF6] font-bold active:scale-95" @click="showFeedbackPopup = true">
                    <view class="i-carbon-chat text-[13px]" />
                    <text>反馈</text>
                  </view>
                </view>
              </view>
              <rich-text class="session-rich mt-4 text-[14px] text-[#475569] leading-[1.8]" :nodes="html(solutionMap[item.question_id].analysis)" />
            </view>

            <!-- 卡片 4：考点 -->
            <view v-if="questionShouldShowSolution(item.question_id) && questionMap[item.question_id].knowledge_point?.length" class="section-card">
              <view class="flex items-center gap-2">
                <view class="i-carbon-tag text-[16px] text-[#0D9488]" />
                <view class="text-[15px] text-[#0D9488] font-black">考点</view>
              </view>
              <view class="mt-3 flex flex-wrap gap-2">
                <view v-for="(kp, kpIdx) in questionMap[item.question_id].knowledge_point" :key="kpIdx" class="rounded-full border border-[#99F6E4] bg-[#F0FDFA] px-3 py-1.5 text-[12px] text-[#0F766E] font-semibold">
                  {{ typeof kp === 'object' ? (kp.name || kp.label || kp.title || JSON.stringify(kp)) : kp }}
                </view>
              </view>
            </view>

            <!-- 卡片 5：笔记 -->
            <view v-if="questionShouldShowSolution(item.question_id)" class="section-card">
              <view class="flex items-center justify-between gap-2">
                <view class="flex items-center gap-2">
                  <view class="i-carbon-notebook text-[16px] text-[#B45309]" />
                  <view class="text-[15px] text-[#B45309] font-black">笔记</view>
                </view>
                <view class="flex items-center gap-2">
                  <!-- 公开/私密开关 -->
                  <view v-if="noteMap[item.question_id]?.id && !noteEditingMap[item.question_id]" class="flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-bold active:scale-95" :class="noteMap[item.question_id]?.is_public ? 'border border-[#BBF7D0] bg-[#F0FDF4] text-[#15803D]' : 'border border-[#E2E8F0] bg-[#F8FAFC] text-[#94A3B8]'" @click="toggleNotePublic(item.question_id)">
                    <view :class="noteMap[item.question_id]?.is_public ? 'i-carbon-view text-[12px]' : 'i-carbon-view-off text-[12px]'" />
                    <text>{{ noteMap[item.question_id]?.is_public ? '公开' : '私密' }}</text>
                  </view>
                  <!-- 编辑/添加按钮 -->
                  <view v-if="!noteEditingMap[item.question_id]" class="rounded-full border border-[#FDE68A] bg-[#FFFBEB] px-3 py-1 text-[12px] text-[#B45309] font-bold active:scale-95" @click="noteEditingMap[item.question_id] = true; if (!noteContentMap[item.question_id] && noteMap[item.question_id]?.content) noteContentMap[item.question_id] = noteMap[item.question_id].content">
                    {{ noteMap[item.question_id]?.content ? '编辑' : '添加笔记' }}
                  </view>
                </view>
              </view>
              <!-- Tab 切换：我的 / 他人笔记 -->
              <view class="mt-3 flex items-center gap-0 rounded-full bg-[#F1F5F9] p-0.5">
                <view class="flex flex-1 items-center justify-center rounded-full py-1.5 text-[12px] font-bold transition-all" :class="(noteTabMap[item.question_id] || 'mine') === 'mine' ? 'bg-white text-[#B45309] shadow-sm' : 'text-[#64748B]'" @click="switchNoteTab(item.question_id, 'mine')">
                  我的笔记
                </view>
                <view class="flex flex-1 items-center justify-center rounded-full py-1.5 text-[12px] font-bold transition-all" :class="noteTabMap[item.question_id] === 'public' ? 'bg-white text-[#B45309] shadow-sm' : 'text-[#64748B]'" @click="switchNoteTab(item.question_id, 'public')">
                  他人笔记
                </view>
              </view>
              <!-- 我的笔记内容 -->
              <view v-if="(noteTabMap[item.question_id] || 'mine') === 'mine'">
                <view v-if="noteEditingMap[item.question_id]" class="mt-3">
                  <textarea :value="noteContentMap[item.question_id] || ''" class="box-border min-h-[120px] w-full rounded-[16px] border border-[#FDE68A] bg-[#FFFBEB] px-4 py-3 text-[14px] text-[#0F172A] leading-[1.8]" placeholder="记录你的学习心得、易错提醒..." :maxlength="-1" auto-height @input="noteContentMap[item.question_id] = $event.detail.value" />
                  <view class="mt-3 flex items-center gap-3">
                    <view class="h-9 flex flex-1 items-center justify-center rounded-full bg-[#F1F5F9] text-[13px] text-[#475569] font-bold active:scale-[0.98]" @click="noteEditingMap[item.question_id] = false">取消</view>
                    <view class="h-9 flex flex-1 items-center justify-center rounded-full bg-[#B45309] text-[13px] text-white font-black active:scale-[0.98]" @click="saveNote(item.question_id)">{{ noteLoadingMap[item.question_id] ? '保存中...' : '保存笔记' }}</view>
                  </view>
                </view>
                <view v-else-if="noteMap[item.question_id]?.content" class="mt-3">
                  <view class="text-[14px] text-[#475569] leading-[1.8]">{{ noteMap[item.question_id].content }}</view>
                </view>
                <view v-else class="mt-3 text-[13px] text-[#94A3B8]">暂无笔记，点击右上角添加</view>
              </view>
              <!-- 他人公开笔记 -->
              <view v-else class="mt-3">
                <view v-if="publicNotesLoadingMap[item.question_id]" class="py-4 text-center text-[13px] text-[#94A3B8]">加载中...</view>
                <view v-else-if="!publicNotesMap[item.question_id]?.length" class="py-4 text-center text-[13px] text-[#94A3B8]">暂无公开笔记</view>
                <view v-else class="flex flex-col gap-3">
                  <view v-for="(pn, pnIdx) in publicNotesMap[item.question_id]" :key="pnIdx" class="rounded-[14px] border border-[#E2E8F0] bg-[#F8FAFC] px-4 py-3">
                    <view class="text-[14px] text-[#334155] leading-[1.8]">{{ pn.content }}</view>
                    <view class="mt-2 flex items-center justify-between text-[11px] text-[#94A3B8]">
                      <text>{{ pn.user_nickname || '匿名用户' }}</text>
                      <view class="flex items-center gap-1">
                        <view class="i-carbon-thumbs-up text-[12px]" />
                        <text>{{ pn.like_count || 0 }}</text>
                      </view>
                    </view>
                  </view>
                </view>
              </view>
            </view>

            <view class="h-4" />
          </view>
        </scroll-view>
      </swiper-item>
    </swiper>

    <view v-else class="px-5 pt-12 text-center text-[14px] text-[#94A3B8]">
      暂时没有可展示的题目
    </view>

    <wd-popup :model-value="showAnswerSheet" position="bottom" custom-class="rounded-t-3xl overflow-hidden bg-[#FAFAFA]" safe-area-inset-bottom :z-index="999999" custom-style="height:auto;max-height:78vh;" @update:model-value="showAnswerSheet = $event">
      <view class="px-5 pb-4 pt-5">
        <view class="flex items-center justify-between gap-3">
          <view>
            <view class="text-[18px] text-[#14532D] font-black">
              答题卡
            </view>
            <view class="mt-1 text-[12px] text-[#64748B]">
              {{ routeViewMode === 'wrong' ? `仅展示错题，共 ${totalCount} 题` : `已作答 ${answeredCount} / ${totalCount} 题` }}
            </view>
          </view>
          <view class="h-8 w-8 flex items-center justify-center rounded-full bg-slate-100 text-slate-400 active:scale-90" @click="showAnswerSheet = false">
            <view class="i-carbon-close text-[18px]" />
          </view>
        </view>
        <view class="grid grid-cols-4 mt-4 gap-3">
          <view class="rounded-[18px] bg-white px-3 py-3 text-center shadow-sm">
            <view class="text-[11px] text-[#94A3B8]">
              答对
            </view><view class="mt-1 text-[17px] text-[#16A34A] font-black">
              {{ correctCount }}
            </view>
          </view>
          <view class="rounded-[18px] bg-white px-3 py-3 text-center shadow-sm">
            <view class="text-[11px] text-[#94A3B8]">
              答错
            </view><view class="mt-1 text-[17px] text-[#F97316] font-black">
              {{ wrongCount }}
            </view>
          </view>
          <view class="rounded-[18px] bg-white px-3 py-3 text-center shadow-sm">
            <view class="text-[11px] text-[#94A3B8]">
              未答
            </view><view class="mt-1 text-[17px] text-[#64748B] font-black">
              {{ totalCount - answeredCount }}
            </view>
          </view>
          <view class="rounded-[18px] bg-white px-3 py-3 text-center shadow-sm">
            <view class="text-[11px] text-[#94A3B8]">
              总用时
            </view><view class="mt-1 text-[13px] text-[#0F172A] font-black">
              {{ formatSeconds(totalSeconds) }}
            </view>
          </view>
        </view>
        <view class="mt-5">
          <AnswerSheet :groups="questionGroups" @select="handleSheetSelect" />
        </view>
        <view v-if="!isCompleted" class="mt-5 h-12 flex items-center justify-center rounded-full bg-[#F59E0B] text-[15px] text-white font-black active:scale-[0.98]" @click="submitSession">
          {{ submitting ? '提交中...' : '交卷完成' }}
        </view>
        <view class="h-safe-area-bottom w-full" />
      </view>
    </wd-popup>

    <!-- 草稿涂鸦遮罩 -->
    <FeedbackPopup
      v-model="showFeedbackPopup"
      title="题目反馈"
      subtitle="题目内容、答案解析、交互异常都可以快速反馈"
      feedback-type="content_error"
      :page-path="`/pages/practice/session/index?sessionId=${sessionId}`"
      target-type="question"
      :target-id="currentQuestionId ? String(currentQuestionId) : null"
      :target-text="feedbackTargetText"
    />

    <view v-if="showDraftOverlay" class="draft-overlay">
      <canvas
        canvas-id="draftCanvas"
        class="draft-canvas"
        disable-scroll
        @touchstart="onCanvasTouchStart"
        @touchmove="onCanvasTouchMove"
        @touchend="onCanvasTouchEnd"
      />
      <!-- 顶部提示 -->
      <view class="draft-top-hint">
        <view class="i-carbon-pen text-[14px]" />
        <text>草稿涂鸦模式 · 在屏幕上直接画</text>
      </view>
      <!-- 底部工具栏 -->
      <view class="draft-toolbar">
        <view class="draft-toolbar-inner">
          <!-- 颜色选择 -->
          <view class="flex items-center gap-2">
            <view v-for="c in ['#FF3B30', '#34C759', '#007AFF', '#0F172A']" :key="c" class="draft-color-dot" :class="{ 'draft-color-active': canvasPenColor === c }" :style="{ background: c }" @click="canvasPenColor = c" />
          </view>
          <!-- 粗细 -->
          <view class="flex items-center gap-1.5">
            <view v-for="w in [2, 4, 6]" :key="w" class="draft-width-dot" :class="{ 'draft-width-active': canvasPenWidth === w }" @click="canvasPenWidth = w">
              <view class="rounded-full bg-current" :style="{ width: `${w + 4}px`, height: `${w + 4}px` }" />
            </view>
          </view>
          <!-- 撤销 + 清除 -->
          <view class="flex items-center gap-2">
            <view class="draft-tool-btn" @click="undoStroke">
              <view class="i-carbon-undo text-[18px]" />
            </view>
            <view class="draft-tool-btn" @click="clearCanvas">
              <view class="i-carbon-trash-can text-[18px]" />
            </view>
          </view>
          <!-- ❌ 关闭 -->
          <view class="draft-close-x" @click="closeDraftOverlay">
            <text>✕</text>
          </view>
        </view>
        <view class="h-safe-area-bottom w-full" />
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
/* ====== 草稿涂鸦遮罩 ====== */
.draft-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 999999;
  background: rgba(255, 255, 255, 0.15);
}

.draft-canvas {
  width: 100%;
  height: 100%;
}

.draft-top-hint {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding-top: calc(env(safe-area-inset-top, 20px) + 4px);
  padding-bottom: 6px;
  font-size: 12px;
  font-weight: 700;
  color: rgba(71, 85, 105, 0.7);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.85) 0%, rgba(255, 255, 255, 0) 100%);
  pointer-events: none;
}

.draft-toolbar {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(20px);
  border-top: 1px solid rgba(226, 232, 240, 0.6);
  padding: 10px 16px;
}

.draft-toolbar-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.draft-color-dot {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  transition: transform 0.15s ease;
}

.draft-color-active {
  transform: scale(1.3);
  box-shadow: 0 0 0 2px #fff, 0 0 0 3.5px #2563eb;
}

.draft-width-dot {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  color: #64748b;
  transition: background 0.15s ease;
}

.draft-width-active {
  background: #e2e8f0;
  color: #0f172a;
}

.draft-tool-btn {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  color: #475569;
  background: #f1f5f9;
  transition: all 0.15s ease;
}

.draft-tool-btn:active {
  transform: scale(0.92);
}

.draft-close-x {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(239, 68, 68, 0.12);
  color: #ef4444;
  font-size: 18px;
  font-weight: 800;
  transition: transform 0.15s ease;
}

.draft-close-x:active {
  transform: scale(0.9);
}

.section-card {
  border: 1px solid rgba(255, 255, 255, 0.70);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.92);
  padding: 20px;
  box-shadow: 0 12px 24px rgba(148, 163, 184, 0.08);
}

.data-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 6px;
  border-radius: 14px;
  background: #f8fafc;
}

.data-cell-label {
  font-size: 11px;
  color: #94a3b8;
  font-weight: 600;
}

.data-cell-value {
  font-size: 14px;
  font-weight: 800;
  white-space: nowrap;
}

.session-rich {
  display: block;
  word-break: break-word;
}

.session-rich :deep(img),
.session-rich :deep(image),
.session-rich :deep(video),
.session-rich :deep(table) {
  max-width: 100% !important;
  box-sizing: border-box;
}

.session-rich :deep(img),
.session-rich :deep(image) {
  width: auto !important;
  height: auto !important;
  display: block;
}

.session-rich :deep(video) {
  width: 100% !important;
  height: auto !important;
  display: block;
}

.session-rich :deep(table) {
  display: block;
  overflow-x: auto;
}

.option-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 13px 15px;
  border-radius: 12px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.92);
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    background-color 0.2s ease;
}

.option-card:active {
  transform: scale(0.992);
}

.option-card.tone-selected {
  border-color: rgba(59, 130, 246, 0.45);
  background: linear-gradient(135deg, rgba(239, 246, 255, 1), rgba(255, 255, 255, 1));
}

.option-card.tone-correct {
  border-color: rgba(34, 197, 94, 0.45);
  background: linear-gradient(135deg, rgba(240, 253, 244, 1), rgba(255, 255, 255, 1));
}

.option-card.tone-wrong {
  border-color: rgba(239, 68, 68, 0.42);
  background: linear-gradient(135deg, rgba(254, 242, 242, 1), rgba(255, 255, 255, 1));
}

.option-code {
  width: 34px;
  height: 34px;
  flex-shrink: 0;
  border-radius: 999px;
  border: 1px solid #cbd5e1;
  background: #fff;
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 800;
}

.option-code-square {
  border-radius: 12px;
}

.option-card.tone-selected .option-code {
  border-color: #3b82f6;
  background: #3b82f6;
  color: #fff;
}

.option-card.tone-correct .option-code {
  border-color: #22c55e;
  background: #22c55e;
  color: #fff;
}

.option-card.tone-wrong .option-code {
  border-color: #ef4444;
  background: #ef4444;
  color: #fff;
}

.option-content {
  flex: 1;
  min-width: 0;
  color: #0f172a;
  font-size: 15px;
  line-height: 1.78;
}
</style>
