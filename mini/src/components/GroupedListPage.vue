<script lang="ts" setup>
import MembershipModal from '@/components/MembershipModal.vue'
import PracticeNode from '@/components/PracticeNode.vue'
import RenderBookExportPopup from '@/components/RenderBookExportPopup.vue'
import type { UseGroupedListPageReturn } from '@/hooks/useGroupedListPage'

const props = defineProps<{
  ctx: UseGroupedListPageReturn
}>()

const {
  config,
  statusBarHeight,
  groupMode,
  activeModeIndex,
  showMembershipModal,
  showExportPopup,
  exportTarget,
  loadingMap,
  groupModes,
  switchGroupMode,
  onModeSwiperChange,
  goBack,
  onGroupClick,
  startPractice,
  isExportingNode,
  exportQuestions,
  submitExport,
  handleExportPopupChange,
  getFlatGroups,
  getTreeGroups,
  handleGroupTap,
  displayStatistics,
  getModeTotalCount,
  currentDomainLabel,
  exportMode,
  selectedExportKeys,
  toggleExportMode,
  cancelExportMode,
  onExportSelectChange,
  confirmBatchExport,
} = props.ctx
</script>

<template>
  <view
    class="relative min-h-screen text-[#334155]"
    :style="{ background: `linear-gradient(to bottom, ${config.gradientFrom}, ${config.gradientVia}, #FAFAFA)` }"
  >
    <!-- 自定义导航栏 -->
    <view class="relative z-10 w-full" :style="{ paddingTop: `${statusBarHeight}px` }">
      <view class="relative h-11 flex items-center justify-center px-4">
        <view class="absolute left-4 h-8 w-8 flex items-center justify-center active:opacity-60" @click="goBack">
          <view class="i-carbon-chevron-left text-2xl text-[#1E293B]" />
        </view>
        <text class="text-lg text-[#1E293B] font-bold tracking-widest">{{ config.pageTitle }}</text>
      </view>
    </view>

    <view class="mt-4 px-4" :class="exportMode ? 'pb-40' : 'pb-24'">
      <!-- 统计卡片 -->
      <view class="mb-5 border border-white/60 rounded-2xl bg-white/85 p-5 shadow-[0_4px_24px_-10px_rgba(0,0,0,0.06)] backdrop-blur-md">
        <view class="mb-3 flex items-center justify-between">
          <view class="rounded-full bg-[#F8FAFC] px-3 py-1 text-[11px] text-[#475569] font-semibold">
            当前领域：{{ currentDomainLabel }}
          </view>
          <view class="text-[11px] text-[#94A3B8]">
            列表与导出按当前领域筛选
          </view>
        </view>
        <slot name="stats" :statistics="displayStatistics" />
      </view>

      <!-- 分组模式切换 -->
      <view class="mb-3">
        <view
          class="relative flex w-full items-center rounded-[18px] bg-white/78 p-1.5 shadow-[0_10px_28px_-18px_rgba(15,23,42,0.35)]"
        >
          <view
            class="absolute bottom-1.5 top-1.5 rounded-[14px] shadow-sm transition-all duration-300"
            :style="{
              backgroundColor: config.primaryColor,
              width: 'calc(50% - 6px)',
              left: activeModeIndex === 0 ? '6px' : 'calc(50% + 0px)',
            }"
          />
          <view
            v-for="m in groupModes"
            :key="m.key"
            class="relative z-10 flex-1 text-center rounded-[14px] px-4 py-2 text-[13px] transition-all duration-200"
            :class="groupMode === m.key ? 'text-white font-bold' : 'text-[#64748B]'"
            @tap="switchGroupMode(m.key)"
          >
            {{ m.label }}
          </view>
        </view>
      </view>

      <swiper
        class="mode-swiper"
        :current="activeModeIndex"
        :duration="280"
        :disable-touch="exportMode"
        @change="onModeSwiperChange"
      >
        <swiper-item v-for="modeItem in groupModes" :key="modeItem.key">
          <view class="mode-panel">
            <view class="mb-3 flex items-center justify-between pl-1">
              <text class="text-[13px] text-[#475569] font-bold">{{ config.listTitle }}</text>
              <view class="flex items-center gap-2">
                <text class="text-[11px] text-[#94A3B8]">共 {{ getModeTotalCount(modeItem.key) }} 题</text>
                <view
                  class="rounded-full border px-2.5 py-1 text-[11px] font-semibold active:opacity-70"
                  :style="{
                    borderColor: exportMode ? '#DC2626' : config.exportBorderColor,
                    color: exportMode ? '#DC2626' : config.primaryColor,
                  }"
                  @tap="toggleExportMode"
                >
                  {{ exportMode ? '取消' : '导出' }}
                </view>
              </view>
            </view>

            <view
              v-if="loadingMap[modeItem.key] && getFlatGroups(modeItem.key).length === 0"
              class="py-18 text-center text-[13px] text-[#94A3B8]"
            >
              {{ config.loadingText }}
            </view>

            <view
              v-else-if="getFlatGroups(modeItem.key).length > 0"
              class="flex flex-col gap-2"
            >
              <PracticeNode
                v-for="node in getTreeGroups(modeItem.key)"
                :key="`${modeItem.key}-${node.id}-${node.name}`"
                :node="node"
                :depth="0"
                :parent-show-progress="false"
                :parent-show-continue="false"
                :select-mode="exportMode"
                :selected-keys="selectedExportKeys"
                :on-select-change="onExportSelectChange"
                :primary-color="config.primaryColor"
                :on-toggle-tap="n => handleGroupTap(n, modeItem.key)"
                :on-group-tap="n => handleGroupTap(n, modeItem.key)"
                :on-leaf-tap="n => onGroupClick(n, modeItem.key)"
              >
                <template #right="{ node: slotNode, hasChildren }">
                  <view v-if="hasChildren" class="i-carbon-chevron-right text-lg text-[#D1D5DB]" />
                  <view v-else class="flex flex-nowrap items-center gap-2">
                    <text class="shrink-0 whitespace-nowrap text-[12px] text-[#94A3B8] font-bold">共 {{ slotNode.count }} 题</text>
                    <view
                      class="shrink-0 whitespace-nowrap rounded-full border px-3 py-1 text-[11px] font-semibold"
                      :style="{
                        borderColor: config.exportBorderColor,
                        color: config.primaryColor,
                        backgroundColor: isExportingNode(slotNode, modeItem.key) ? config.exportActiveBg : 'white',
                        opacity: isExportingNode(slotNode, modeItem.key) ? 0.7 : 1,
                      }"
                      @click.stop="exportQuestions(slotNode, modeItem.key)"
                    >
                      {{ isExportingNode(slotNode, modeItem.key) ? '导出中' : '导出' }}
                    </view>
                    <view
                      class="shrink-0 whitespace-nowrap rounded-full px-3 py-1 text-[11px] text-white font-semibold"
                      :style="{ backgroundColor: config.primaryColor }"
                      @click.stop="startPractice(slotNode, modeItem.key)"
                    >
                      刷题
                    </view>
                  </view>
                </template>
              </PracticeNode>
            </view>

            <view v-else class="flex flex-col items-center justify-center py-20">
              <view :class="config.emptyIcon" class="mb-4 text-6xl text-[#CBD5E1]" />
              <text class="text-[14px] text-[#94A3B8]">{{ config.emptyText }}</text>
            </view>
          </view>
        </swiper-item>
      </swiper>

      <MembershipModal v-model="showMembershipModal" />
      <RenderBookExportPopup
        :model-value="showExportPopup"
        :template-key="exportTarget?.templateKey || 'wrong_question'"
        :title="exportTarget?.scope.title || '导出题本'"
        :total-question-count="exportTarget?.totalQuestionCount || 0"
        @update:model-value="handleExportPopupChange"
        @confirm="submitExport"
      />
    </view>

    <!-- 导出模式底部操作栏 -->
    <view
      v-if="exportMode"
      class="fixed bottom-0 left-0 right-0 z-50 border-t border-[#E2E8F0] bg-white/95 backdrop-blur-md"
      :style="{ paddingBottom: 'env(safe-area-inset-bottom, 20px)' }"
    >
      <view class="flex items-center justify-between px-5 py-3">
        <text class="text-[13px] text-[#64748B]">
          已选 <text class="font-bold" :style="{ color: config.primaryColor }">{{ selectedExportKeys.size }}</text> 项
        </text>
        <view class="flex items-center gap-3">
          <view
            class="rounded-full border border-[#E2E8F0] px-5 py-2 text-[13px] text-[#64748B] font-semibold active:opacity-70"
            @tap="cancelExportMode"
          >
            取消
          </view>
          <view
            class="rounded-full px-5 py-2 text-[13px] text-white font-semibold active:opacity-80"
            :style="{
              backgroundColor: selectedExportKeys.size > 0 ? config.primaryColor : '#CBD5E1',
            }"
            @tap="confirmBatchExport"
          >
            确认导出
          </view>
        </view>
      </view>
    </view>
  </view>
</template>

<style scoped>
.mode-swiper {
  width: 100%;
  min-height: 520px;
}

.mode-panel {
  min-height: 520px;
}
</style>
