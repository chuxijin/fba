<script setup lang="ts">
import { ref, watch } from 'vue'
import type { PracticeReportPayload } from '../../adapters/fenbi/report'
import { applyReportTiming } from '../../adapters/fenbi/report-timing'

const props = defineProps<{ draft: PracticeReportPayload | null; status: string; message: string }>()
const emit = defineEmits<{ (e:'close'):void; (e:'retry'):void; (e:'save', value:PracticeReportPayload):void }>()
const practiceDate = ref('')
const excludeTiming = ref(false)
const actualSeconds = ref<string | number>('')
const timingError = ref('')
watch(() => props.draft, (draft, previous) => {
  practiceDate.value = draft?.practiced_at || ''
  if (draft && draft.source_key !== previous?.source_key) {
    excludeTiming.value = draft.exclude_source_timing ?? false
    actualSeconds.value = draft.manual_duration_seconds ?? ''
  }
  timingError.value = ''
}, { immediate:true })
function duration(seconds:number|null) {
  return seconds == null ? '—' : `${Math.floor(seconds/60)}分${seconds%60}秒`
}
function accuracy(correct:number,total:number) { return `${(correct/total*100).toFixed(1)}%` }
function referenceCount(draft: PracticeReportPayload) {
  return (draft.questions || []).filter(q => q.platform_reference?.correct_ratio_percent != null).length
}
function save() {
  if (!props.draft || !practiceDate.value || props.status === 'saving') return
  try {
    timingError.value = ''
    emit('save', { ...applyReportTiming(props.draft, excludeTiming.value, actualSeconds.value), practiced_at:practiceDate.value,
      time_source:practiceDate.value === props.draft.practiced_at ? props.draft.time_source : 'manual' })
  } catch (error) {
    timingError.value = error instanceof Error ? error.message : '实际用时不合法'
  }
}
</script>

<template>
  <div class="gk-report-backdrop" @click.self="status !== 'saving' && emit('close')">
    <section class="gk-report-dialog" role="dialog" aria-modal="true" aria-label="导入练习记录">
      <header class="gk-report-header">
        <div><div class="gk-report-eyebrow">粉笔 · 练习报告</div><h2>导入练习记录</h2></div>
        <button type="button" class="gk-report-close" aria-label="关闭" :disabled="status === 'saving'" @click="emit('close')">×</button>
      </header>
      <div class="gk-report-body">
        <p v-if="status === 'loading'" role="status">正在读取当前页面已加载的报告数据…</p>
        <template v-if="draft">
          <h3>{{ draft.material_title }}</h3>
          <div class="gk-report-summary">
            <div><small>正确率</small><strong>{{ accuracy(draft.correct_count,draft.total_questions) }}</strong></div>
            <div><small>答对 / 总题数</small><strong>{{ draft.correct_count }} / {{ draft.total_questions }}</strong></div>
            <div><small>{{ excludeTiming ? '有效总用时' : '总用时' }}</small><strong>{{ duration(excludeTiming ? (actualSeconds === '' ? null : Number(actualSeconds)) : draft.duration_seconds) }}</strong></div>
          </div>
          <p class="gk-report-note">{{ draft.subject_name }} · 答错 {{ draft.total_questions-draft.correct_count-draft.unanswered_count }} 题 · 未答 {{ draft.unanswered_count }} 题<span v-if="draft.score != null"> · 得分 {{ draft.score }} / {{ draft.full_score ?? '—' }}</span></p>
          <p class="gk-report-note">平台逐题正确率：{{ referenceCount(draft) }}/{{ draft.total_questions }} 题<span v-if="draft.platform_reference?.difficulty_raw != null"> · 原平台难度 {{ draft.platform_reference.difficulty_raw }}</span><span v-if="draft.platform_reference?.average_score != null"> · 平台平均分 {{ draft.platform_reference.average_score }}</span></p>
          <p class="gk-report-note">点击导入会自动识别已有报告：首次正常归档，重导只补缺失统计，已有值不覆盖。未加载的正确率保留未知；可打开粉笔解析后重新读取。补充统计按实际抓取时间保存，不纳入历史趋势。</p>
          <label class="gk-report-date">练习日期<input v-model="practiceDate" type="date" required :disabled="status === 'saving' || status === 'done'"></label>
          <p class="gk-report-note">{{ draft.source_updated_at ? '日期来自粉笔页面已加载的数据，可按实际练习日期校正。' : '当前页面没有练习日期，请填写实际练习日期后导入。' }}</p>
          <label class="gk-report-timing"><input v-model="excludeTiming" type="checkbox" :disabled="status === 'saving' || status === 'done'">纸上作答／仅补录答案</label>
          <template v-if="excludeTiming">
            <label class="gk-report-date">实际总用时（秒，可选）<input v-model="actualSeconds" type="number" min="0" step="1" placeholder="未知请留空" :disabled="status === 'saving' || status === 'done'"></label>
            <p class="gk-report-note">补录答案 · 不计入平台用时。原平台总用时 {{ duration(draft.duration_seconds) }} 及各级用时仍保留；实际总用时只用于整卷，不分配到模块或单题。已有报告请在小程序编辑标记，重导不会覆盖已有选择。</p>
          </template>
          <p v-if="timingError" class="gk-report-message is-error" role="alert">{{ timingError }}</p>
          <div class="gk-report-table-heading"><span>模块 / 子模块 / 细分题型</span><span>答对 / 题数</span><span>正确率</span><span>用时</span></div>
          <details v-for="module in draft.modules" :key="module.module_name" class="gk-report-module">
            <summary><span>{{ module.module_name }}</span><span>{{ module.correct_count }}/{{ module.total_questions }}</span><span>{{ accuracy(module.correct_count,module.total_questions) }}</span><span>{{ duration(excludeTiming ? null : module.duration_seconds) }}</span></summary>
            <template v-for="child in module.children" :key="child.module_name">
              <div class="gk-report-child"><span>{{ child.module_name }}</span><span>{{ child.correct_count }}/{{ child.total_questions }}</span><span>{{ accuracy(child.correct_count,child.total_questions) }}</span><span>{{ duration(excludeTiming ? null : child.duration_seconds) }}</span></div>
              <div v-for="topic in child.children" :key="topic.module_name" class="gk-report-child gk-report-topic"><span>{{ topic.module_name }}</span><span>{{ topic.correct_count }}/{{ topic.total_questions }}</span><span>{{ accuracy(topic.correct_count,topic.total_questions) }}</span><span>{{ duration(excludeTiming ? null : topic.duration_seconds) }}</span></div>
            </template>
            <p v-if="!module.children?.length" class="gk-report-note">本模块没有直属子模块明细。</p>
          </details>
          <p class="gk-report-note">子模块可能覆盖同一道题，各级保留原报告统计。</p>
          <p class="gk-report-note">首次导入前请展开所需题型明细，再点击重新读取；未提供的明细不会自动推算。重导不补题、题型或解析，不改日期、答案、对错及用时。</p>
        </template>
        <p v-if="message" class="gk-report-message" :class="{ 'is-error':status === 'error' }" role="status">{{ message }}</p>
      </div>
      <footer class="gk-report-footer">
        <button type="button" :disabled="status === 'saving'" @click="emit('close')">{{ status === 'done' ? '完成' : '取消' }}</button>
        <button v-if="draft && status !== 'done'" type="button" :disabled="status === 'saving' || status === 'loading'" @click="emit('retry')">重新读取</button>
        <button v-if="status === 'error' && !draft" type="button" class="gk-report-primary" @click="emit('retry')">重新读取</button>
        <button v-else-if="status !== 'done'" type="button" class="gk-report-primary" :disabled="!draft || !practiceDate || status === 'saving' || status === 'loading'" @click="save">{{ status === 'saving' ? '正在保存…' : '确认导入' }}</button>
      </footer>
    </section>
  </div>
</template>
