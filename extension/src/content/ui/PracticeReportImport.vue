<script setup lang="ts">
import { ref, watch } from 'vue'
import type { PracticeReportPayload } from '../../adapters/fenbi/report'

const props = defineProps<{ draft: PracticeReportPayload | null; status: string; message: string }>()
const emit = defineEmits<{ (e:'close'):void; (e:'retry'):void; (e:'save', value:PracticeReportPayload):void }>()
const practiceDate = ref('')
watch(() => props.draft, draft => { practiceDate.value = draft?.practiced_at || '' }, { immediate:true })
function duration(seconds:number|null) {
  return seconds == null ? '—' : `${Math.floor(seconds/60)}分${seconds%60}秒`
}
function accuracy(correct:number,total:number) { return `${(correct/total*100).toFixed(1)}%` }
function save() {
  if (!props.draft || !practiceDate.value || props.status === 'saving') return
  emit('save', { ...props.draft, practiced_at:practiceDate.value,
    time_source:practiceDate.value === props.draft.practiced_at ? props.draft.time_source : 'manual' })
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
        <p v-if="status === 'loading'" role="status">正在读取报告并匹配练习日期，请稍候…</p>
        <template v-if="draft">
          <h3>{{ draft.material_title }}</h3>
          <div class="gk-report-summary">
            <div><small>正确率</small><strong>{{ accuracy(draft.correct_count,draft.total_questions) }}</strong></div>
            <div><small>答对 / 总题数</small><strong>{{ draft.correct_count }} / {{ draft.total_questions }}</strong></div>
            <div><small>总用时</small><strong>{{ duration(draft.duration_seconds) }}</strong></div>
          </div>
          <p class="gk-report-note">{{ draft.subject_name }} · 答错 {{ draft.total_questions-draft.correct_count-draft.unanswered_count }} 题 · 未答 {{ draft.unanswered_count }} 题<span v-if="draft.score != null"> · 得分 {{ draft.score }} / {{ draft.full_score ?? '—' }}</span></p>
          <label class="gk-report-date">练习日期<input v-model="practiceDate" type="date" required :disabled="status === 'saving' || status === 'done'"></label>
          <p class="gk-report-note">{{ draft.source_updated_at ? '日期来自粉笔历史更新时间，可按实际练习日期校正。' : '未匹配到历史日期，请填写实际练习日期后导入。' }}</p>
          <div class="gk-report-table-heading"><span>模块 / 直属子模块</span><span>答对 / 题数</span><span>正确率</span><span>用时</span></div>
          <details v-for="module in draft.modules" :key="module.module_name" class="gk-report-module">
            <summary><span>{{ module.module_name }}</span><span>{{ module.correct_count }}/{{ module.total_questions }}</span><span>{{ accuracy(module.correct_count,module.total_questions) }}</span><span>{{ duration(module.duration_seconds) }}</span></summary>
            <div v-for="child in module.children" :key="child.module_name" class="gk-report-child"><span>{{ child.module_name }}</span><span>{{ child.correct_count }}/{{ child.total_questions }}</span><span>{{ accuracy(child.correct_count,child.total_questions) }}</span><span>{{ duration(child.duration_seconds) }}</span></div>
            <p v-if="!module.children?.length" class="gk-report-note">本模块没有直属子模块明细。</p>
          </details>
          <p class="gk-report-note">子模块可能覆盖同一道题，各级保留原报告统计。</p>
        </template>
        <p v-if="message" class="gk-report-message" :class="{ 'is-error':status === 'error' }" role="status">{{ message }}</p>
      </div>
      <footer class="gk-report-footer">
        <button type="button" :disabled="status === 'saving'" @click="emit('close')">{{ status === 'done' ? '完成' : '取消' }}</button>
        <button v-if="status === 'error' && !draft" type="button" class="gk-report-primary" @click="emit('retry')">重新读取</button>
        <button v-else-if="status !== 'done'" type="button" class="gk-report-primary" :disabled="!draft || !practiceDate || status === 'saving' || status === 'loading'" @click="save">{{ status === 'saving' ? '正在保存…' : '确认导入' }}</button>
      </footer>
    </section>
  </div>
</template>
