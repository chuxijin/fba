<template>
  <div v-if="modelValue" class="gk-modal-overlay" @click.self="close">
    <div class="gk-modal-container">
      <!-- 头部 -->
      <div class="gk-modal-header">
        <div class="gk-modal-title">
          <img v-if="logoUrl" :src="logoUrl" class="gk-modal-logo" alt="Logo" />
          <span>公考内容排版</span>
        </div>
        <button class="gk-modal-close" aria-label="关闭" title="关闭 (Esc)" @click="close">&times;</button>
      </div>

      <!-- 视图 1: 主排版设置 -->
      <template v-if="viewMode === 'setting'">
        <div class="gk-modal-body">
          <!-- 1. 试卷标题与情境自适应徽章 -->
          <div class="gk-paper-badge">
            <div class="gk-badge-header-row">
              <span class="gk-paper-name" :title="paperTitle">📋 {{ paperTitle }}</span>
              <span class="gk-scene-tag" :class="sceneTagInfo.class">
                {{ sceneTagInfo.icon }} {{ sceneTagInfo.name }}
              </span>
            </div>
            <div class="gk-badge-sub-row">
              <span class="gk-paper-count">
                {{ currentCountDescription }}
              </span>
            </div>
          </div>

          <!-- 1.4 模考大赛专属情境卡片：导出范围自主选择 (仅错题 vs 全卷) -->
          <div v-if="isMockExam" class="gk-mock-scope-card">
            <div class="gk-control-header">
              <span class="gk-control-title">🎯 导出范围选择 (自适应)</span>
              <span class="gk-control-subtitle">
                {{ detectedWrongCount > 0 ? `已为您自动识别出 ${detectedWrongCount} 道模考错题` : '按需选择考后订正或整卷重做' }}
              </span>
            </div>

            <div class="gk-mock-scope-grid">
              <!-- 模式 A: 仅导出模考错题 -->
              <div
                class="gk-scope-item"
                :class="{ active: mockExportScope === 'mistake_only' }"
                @click="mockExportScope = 'mistake_only'"
              >
                <div class="gk-scope-radio">
                  <input type="radio" name="mockScope" :checked="mockExportScope === 'mistake_only'" />
                </div>
                <div class="gk-scope-content">
                  <div class="gk-scope-title-row">
                    <span class="gk-scope-main-title">🎯 仅导出模考错题</span>
                    <span v-if="detectedWrongCount > 0" class="gk-scope-count-badge">{{ detectedWrongCount }} 题</span>
                  </div>
                  <div class="gk-scope-desc">
                    【推荐】精准提取本次模考中答错的题目与深度解析，生成考后专属订正集，免去打印整卷多余页面的浪费。
                  </div>
                </div>
              </div>

              <!-- 模式 B: 导出模考全真试卷 -->
              <div
                class="gk-scope-item"
                :class="{ active: mockExportScope === 'all' }"
                @click="mockExportScope = 'all'"
              >
                <div class="gk-scope-radio">
                  <input type="radio" name="mockScope" :checked="mockExportScope === 'all'" />
                </div>
                <div class="gk-scope-content">
                  <div class="gk-scope-title-row">
                    <span class="gk-scope-main-title">📑 导出模考全真试卷</span>
                    <span class="gk-scope-count-badge neutral">{{ totalQuestions }} 题</span>
                  </div>
                  <div class="gk-scope-desc">
                    完整还原考场 1:1 标准全卷（共 {{ totalQuestions }} 题与完整材料），支持计时全卷重做或考前押题模拟。
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 1.5 知识点错题集训专属卡片 (知识点专属突破) -->
          <div v-else-if="isMistakeBook" class="gk-mistake-count-card">
            <div class="gk-control-header">
              <span class="gk-control-title">🎯 错题导出题量</span>
              <span class="gk-control-subtitle">当前考点共 {{ mistakeTotal }} 道错题</span>
            </div>

            <!-- 快捷推荐胶囊 -->
            <div class="gk-count-pills">
              <button
                type="button"
                class="gk-count-pill"
                :class="{ active: selectedCount === 10 }"
                @click="setCount(10)"
              >
                10 题 <span class="gk-pill-tip">当前页</span>
              </button>
              <button
                v-if="mistakeTotal >= 20"
                type="button"
                class="gk-count-pill"
                :class="{ active: selectedCount === 20 }"
                @click="setCount(20)"
              >
                20 题 <span class="gk-pill-tip">小测</span>
              </button>
              <button
                v-if="mistakeTotal >= 30"
                type="button"
                class="gk-count-pill"
                :class="{ active: selectedCount === 30 }"
                @click="setCount(30)"
              >
                30 题 <span class="gk-pill-tip">突破</span>
              </button>
              <button
                v-if="mistakeTotal >= 50"
                type="button"
                class="gk-count-pill"
                :class="{ active: selectedCount === 50 }"
                @click="setCount(50)"
              >
                50 题 <span class="gk-pill-tip">模测</span>
              </button>
              <button
                type="button"
                class="gk-count-pill"
                :class="{ active: selectedCount === mistakeTotal }"
                @click="setCount(mistakeTotal)"
              >
                全部 {{ mistakeTotal }} 题
              </button>
            </div>

            <!-- 自定义数量输入框 -->
            <div class="gk-custom-count-row">
              <span class="gk-custom-label">自定义题量：</span>
              <div class="gk-input-number-wrap">
                <span>抽取前</span>
                <input
                  v-model.number="selectedCount"
                  type="number"
                  min="1"
                  :max="mistakeTotal"
                  class="gk-input-number"
                  @change="handleCustomCountChange"
                />
                <span>道错题 (1 ~ {{ mistakeTotal }})</span>
              </div>
            </div>
          </div>

          <!-- 1.8 导出前【试题健康度与内容现场抽检】卡片 (所见即所得，彻底打消疑虑) -->
          <div class="gk-preview-card">
            <div class="gk-preview-header">
              <div class="gk-preview-title-wrap">
                <span class="gk-preview-title">📋 试题内容抽检与核对</span>
                <span class="gk-health-pill" :class="stemHealthStatus.class">
                  <span class="gk-status-dot" :class="stemHealthStatus.dotClass"></span>
                  {{ stemHealthStatus.text }}
                </span>
              </div>
              <button
                v-if="displayQuestions.length > 1"
                type="button"
                class="gk-preview-drawer-btn"
                @click="showAllQuestions = !showAllQuestions"
              >
                {{ showAllQuestions ? '收起题目清单 ▴' : `查看全部 ${displayQuestions.length} 题清单 ▾` }}
              </button>
            </div>

            <!-- 第一题现场抽样核验卡片 -->
            <div v-if="sampleQuestion" class="gk-sample-box">
              <div class="gk-sample-meta-row">
                <span class="gk-sample-num-tag">
                  {{ isMockExam && mockExportScope === 'mistake_only' ? `错题抽样 (原卷第 ${sampleQuestion.order_num || 1} 题)` : '第 1 题抽样' }}
                </span>
                <span v-if="sampleQuestion.is_wrong" class="gk-sample-wrong-tag">❌ 本题做错</span>
                <span
                  v-if="sampleQuestionSourceTag"
                  class="gk-sample-source-tag"
                  :title="sampleQuestion?.source || sampleQuestionSourceTag"
                >
                  {{ sampleQuestionSourceTag }}
                </span>
                <span v-if="sampleQuestion.user_answer" class="gk-sample-userans-tag">您的选择: {{ sampleQuestion.user_answer }}</span>
                <span v-if="sampleQuestion.answer" class="gk-sample-answer-tag">参考答案: {{ sampleQuestion.answer }}</span>
              </div>
              <div class="gk-sample-stem-text">
                {{ cleanText(sampleQuestion.stem) || '(题干正在智能解析中...)' }}
              </div>
              <div
                v-if="sampleQuestionOptions.length > 0"
                class="gk-sample-opt-grid"
                :class="{ 'is-single-col': isLongOptions }"
              >
                <div
                  v-for="(opt, oIdx) in sampleQuestionOptions"
                  :key="oIdx"
                  class="gk-sample-opt-item"
                >
                  <span class="gk-sample-opt-key">{{ getOptionLetter(oIdx) }}.</span>
                  <span class="gk-sample-opt-val">{{ cleanText(opt) }}</span>
                </div>
              </div>
            </div>
            <div v-else class="gk-sample-empty">
              <span v-if="isMockExam && mockExportScope === 'mistake_only'">
                🎯 当前暂未匹配到做错题目（可能全对或答题卡尚未载入）。您可以点击上方切换至【导出模考全真试卷】直接导出全卷。
              </span>
              <span v-else>
                ⏳ 正在捕获当前页面试题数据，请稍候...
              </span>
            </div>

            <!-- 全部题目折叠清单抽屉 (随错题/全卷联动) -->
            <div v-if="showAllQuestions && displayQuestions.length > 0" class="gk-all-questions-drawer">
              <div
                v-for="(q, idx) in displayQuestions"
                :key="idx"
                class="gk-drawer-q-row"
                :class="{ 'is-wrong-row': q.is_wrong }"
              >
                <span class="gk-drawer-q-idx">No.{{ idx + 1 }}</span>
                <span v-if="q.is_wrong" class="gk-drawer-wrong-pill">错题</span>
                <span class="gk-drawer-q-stem">{{ cleanText(q.stem).slice(0, 42) }}{{ cleanText(q.stem).length > 42 ? '...' : '' }}</span>
                <span v-if="q.user_answer" class="gk-drawer-q-userans">作答: {{ q.user_answer }}</span>
                <span v-if="q.answer" class="gk-drawer-q-ans">答案: {{ q.answer }}</span>
                <span v-if="formatQuestionSource(q)" class="gk-drawer-q-src">{{ formatQuestionSource(q) }}</span>
              </div>
            </div>
          </div>

          <!-- 2. 答案与解析排布设置 -->
          <div v-if="hasAnswers" class="gk-control-card">
            <div class="gk-control-header">
              <span class="gk-control-title">📖 答案与解析排布</span>
              <span class="gk-control-subtitle">全真考场答题卷面</span>
            </div>

            <div class="gk-answer-mode-group">
              <div
                class="gk-answer-mode-item"
                :class="{ active: settings.answerPlacement === 'merged' }"
                @click="setAnswerMode('merged')"
              >
                <div class="gk-mode-radio">
                  <input type="radio" name="answerPlacement" :checked="settings.answerPlacement === 'merged'" />
                </div>
                <div class="gk-mode-content">
                  <div class="gk-mode-title">合在一本卷末 (推荐)</div>
                  <div class="gk-mode-desc">题目在前、答案与深度解析附于卷尾，考完立刻翻到末尾复盘对照。</div>
                </div>
              </div>

              <div
                class="gk-answer-mode-item"
                :class="{ active: settings.answerPlacement === 'separate' }"
                @click="setAnswerMode('separate')"
              >
                <div class="gk-mode-radio">
                  <input type="radio" name="answerPlacement" :checked="settings.answerPlacement === 'separate'" />
                </div>
                <div class="gk-mode-content">
                  <div class="gk-mode-title">分为另外一个独立 PDF</div>
                  <div class="gk-mode-desc">一份纯试卷用于全真模考计时，一份独立答案册供老师讲解或考后精批。</div>
                </div>
              </div>

              <div
                class="gk-answer-mode-item"
                :class="{ active: settings.answerPlacement === 'none' }"
                @click="setAnswerMode('none')"
              >
                <div class="gk-mode-radio">
                  <input type="radio" name="answerPlacement" :checked="settings.answerPlacement === 'none'" />
                </div>
                <div class="gk-mode-content">
                  <div class="gk-mode-title">不含答案与解析 (仅题本)</div>
                  <div class="gk-mode-desc">完全不导出答案，极致节省打印纸张，适合脱敏模拟测试。</div>
                </div>
              </div>
            </div>
          </div>

          <!-- 3. 国考标准排版规范微型卡片 -->
          <div class="gk-specs-card">
            <div class="gk-specs-header">
              <span class="gk-specs-title">🏛️ 国考 1:1 官方考场排版规范</span>
              <span class="gk-badge-auto">系统自适应保证</span>
            </div>
            <div class="gk-specs-grid">
              <div class="gk-spec-item">
                <span class="gk-spec-label">纸张版面</span>
                <span class="gk-spec-val">标准 B5 双面道林纸</span>
              </div>
              <div class="gk-spec-item">
                <span class="gk-spec-label">官方标准字系</span>
                <span class="gk-spec-val">标宋标题 + 仿宋正文</span>
              </div>
              <div class="gk-spec-item">
                <span class="gk-spec-label">防断页保护</span>
                <span class="gk-spec-val">题目与材料智能防跨页</span>
              </div>
              <div class="gk-spec-item">
                <span class="gk-spec-label">设问陷阱加粗</span>
                <span class="gk-spec-val">“不属于/不能推出”智能突出</span>
              </div>
            </div>
          </div>

          <!-- 4. 账户状态与免登录体验说明 -->
          <div class="gk-account-status-card" aria-live="polite" :aria-busy="accountState.status === 'loading' || (accountState.status === 'ready' && accountState.refreshing)">
            <template v-if="accountState.status !== 'ready'">
              <div class="gk-status-header">
                <span class="gk-status-tag">{{ accountState.status === 'loading' ? '正在确认账户…' : '暂时无法确认账户' }}</span>
                <button v-if="accountState.status === 'error'" type="button" class="gk-count-pill" @click="accountStore.refresh()">重试</button>
              </div>
              <div class="gk-status-desc">{{ accountState.status === 'loading' ? '正在获取今日额度' : accountState.message }}</div>
            </template>
            <template v-else>
              <div v-if="isLoggedIn" class="gk-status-header">
                <span class="gk-status-tag logged">👤 已登录：{{ userName || '题本学员' }}</span>
                <span class="gk-quota-pill logged">{{ quotaHint }}</span>
                <button v-if="accountState.refreshError" type="button" class="gk-count-pill" :title="accountState.refreshError" @click="accountStore.refresh()">重试</button>
              </div>
              <div v-else class="gk-status-header">
                <span class="gk-status-tag unlogged">⚠️ 当前未登录</span>
                <span class="gk-quota-pill unlogged">{{ quotaHint }}</span>
                <button v-if="accountState.refreshError" type="button" class="gk-count-pill" :title="accountState.refreshError" @click="accountStore.refresh()">重试</button>
              </div>
              <div class="gk-status-desc">
                {{ isLoggedIn
                  ? '已关联微信小程序【我的题本】，尊享高频模考导出额度与 5分钱/张 考场双面打印特权。'
                  : `未登录状态每日可导出 ${dailyLimit} 次标准考场卷。手机扫码登录微信小程序【我的题本】，立享更充裕的高额基础额度，并享 5分钱/张 考场专用纸双面打印。`
                }}
              </div>
            </template>
          </div>

          <!-- 底注特性 -->
          <div class="gk-feature-pills">
            <div class="gk-feature-badge">✅ 标准 B5 纸考场版面</div>
            <div class="gk-feature-badge">✅ 官方仿宋与标宋字系</div>
            <div class="gk-feature-badge">✅ 大题过渡与防断页保护</div>
          </div>
        </div>

        <div class="gk-modal-footer">
          <div class="gk-btn-group">
            <button type="button" class="gk-btn gk-btn-cancel" @click="close">
              取消
            </button>
            <button
              type="button"
              class="gk-btn gk-btn-secondary"
              :disabled="!canExport"
              :title="!canExport ? '试题内容尚未就绪，请等待加载' : '导出考场标准 PDF'"
              @click="handleExport('computer_download')"
            >
              {{ exportButtonLabel }}
            </button>
            <button
              type="button"
              class="gk-btn gk-btn-primary"
              :disabled="!canExport"
              :title="!canExport ? '试题内容尚未就绪，请等待加载' : '手机扫码直达小程序打印'"
              @click="handleExport('mobile_sync')"
            >
              📱 快速打印 (手机扫码)
            </button>
          </div>
          <div class="gk-footer-hint">
            {{ accountHint }}
          </div>
        </div>
      </template>

      <!-- 视图 2: 加载中视图 (平滑进度条) -->
      <template v-else-if="viewMode === 'loading'">
        <div class="gk-modal-body">
          <div class="gk-loading-box">
            <div class="gk-loading-spinner-wrap">
              <div class="gk-loading-spinner"></div>
              <span class="gk-spinner-center-icon">📑</span>
            </div>

            <div class="gk-loading-title">
              正在为您智能排版考场试卷
            </div>
            <div class="gk-loading-subtitle">
              《{{ paperTitle }}》({{ totalQuestions }} 道题 · B5考场版)
            </div>

            <!-- 智能进度条 -->
            <div class="gk-progress-container">
              <div class="gk-progress-track">
                <div class="gk-progress-bar" :style="{ width: `${loadingPercent}%` }"></div>
              </div>
              <div class="gk-progress-label">
                <span>{{ loadingStepText }}</span>
                <span>{{ loadingPercent }}%</span>
              </div>
            </div>

            <!-- 三阶段步骤清单 -->
            <div class="gk-loading-steps">
              <div class="gk-step-item" :class="getStepClass(1)">
                <span class="gk-step-dot">1</span>
                <div class="gk-step-info">
                  <span class="gk-step-name">解析题干结构与材料上下文</span>
                  <span class="gk-step-status">{{ getStepStatus(1) }}</span>
                </div>
              </div>
              <div class="gk-step-item" :class="getStepClass(2)">
                <span class="gk-step-dot">2</span>
                <div class="gk-step-info">
                  <span class="gk-step-name">注入国考六大模块规范与 B5 双面版式</span>
                  <span class="gk-step-status">{{ getStepStatus(2) }}</span>
                </div>
              </div>
              <div class="gk-step-item" :class="getStepClass(3)">
                <span class="gk-step-dot">3</span>
                <div class="gk-step-info">
                  <span class="gk-step-name">{{ currentExportTarget === 'computer_download' ? '矢量公式转译与考场 PDF 输出' : '生成云端打印任务与专属小程序码' }}</span>
                  <span class="gk-step-status">{{ getStepStatus(3) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="gk-modal-footer">
          <div class="gk-loading-footer-tip">
            ⚡ 正在调用本地 1:1 矢量排版引擎进行智能去空行与防断页计算，通常需 8~12 秒，请稍候...
          </div>
        </div>
      </template>

      <!-- 视图 3: 排版完成交付与微信扫码视图 -->
      <template v-else-if="viewMode === 'delivery'">
        <div class="gk-modal-body">
          <div class="gk-delivery-box">
            <!-- 1. 顶部成功提示 -->
            <div class="gk-delivery-banner">
              <span class="gk-banner-icon">🎉</span>
              <div>
                <div class="gk-banner-title">
                  {{ currentExportTarget === 'computer_download' ? '考场标准试卷已排版就绪并开始下载！' : '试卷已生成完毕，请手机微信扫码！' }}
                </div>
                <div class="gk-banner-desc">
                  <template v-if="currentExportTarget === 'computer_download'">
                    《{{ paperTitle }}》已提交浏览器下载。
                    <template v-if="savedPath">
                      保存位置：<code style="display:inline-block;max-width:100%;overflow-wrap:anywhere;background:#f1f5f9;border-radius:4px;padding:1px 5px;font-size:12px;color:#334155;">{{ savedPath }}</code>
                    </template>
                    <template v-else>
                      若在下载目录里找不到文件，请检查浏览器是否弹出了「保存位置」对话框，或已开启「下载前询问每个文件的保存位置」。
                    </template>
                  </template>
                  <template v-else>《{{ paperTitle }}》</template>
                </div>
              </div>
            </div>

            <!-- 2. 使用说明与额度说明 -->
            <div class="gk-card-section">
              <div class="gk-card-section-title">
                <span>📌 使用说明与额度规则</span>
                <span class="gk-quota-pill">{{ quotaHint }}</span>
              </div>
              <div class="gk-card-section-text">
                • <strong>免登录体验</strong>：未登录状态每日仅可导出 5 次标准考场卷。<br />
                • <strong>登录享更多额度</strong>：手机扫码登录微信小程序【我的题本】后，不同用户可获得<strong>更充裕的高额基础导出额度</strong>（远多于免登录试用），满足日常高频模考与刷题需求。<br />
                • <strong>考场双面打印</strong>：一键直连数码快印，享 <strong>5 分钱/张</strong> 考场专用 B5 道林纸双面胶装送货上门。
              </div>
            </div>

            <!-- 3. 支持的题库网站 -->
            <div class="gk-card-section">
              <div class="gk-card-section-title">
                <span>🌐 支持的题库网站</span>
              </div>
              <div class="gk-site-tags">
                <span class="gk-site-tag active">✅ 粉笔题库 (真题/模考/练习)</span>
                <span class="gk-site-tag active">✅ 华图在线 (题库/历年真题)</span>
                <span class="gk-site-tag active">✅ 事考帮 (职测/真题/智能练习)</span>
                <span class="gk-site-tag pending">⏳ 中公教育 (适配中)</span>
                <span class="gk-site-tag pending">⏳ 公考通 (适配中)</span>
              </div>
            </div>

            <!-- 4. 微信小程序生态引流 -->
            <div class="gk-miniapp-lead">
              <img class="gk-miniapp-lead-img" :src="qrCodeUrl || `${BACKEND_BASE}/api/v1/render-books/public/minicode/demo`" alt="小程序码" />
              <div class="gk-miniapp-lead-info">
                <div class="gk-miniapp-lead-title">📱 微信扫码 · 登录【我的题本】</div>
                <ul class="gk-miniapp-lead-list">
                  <li>扫码登录后<strong>享有更高导出额度</strong>，并可在小程序找回本次导出的试卷</li>
                  <li>一键直连合作打印商：<strong>5 分钱/张</strong>、全真考场专用纸双面胶装</li>
                  <li>手机端随时刷题、背题与复盘错题</li>
                </ul>
              </div>
            </div>
          </div>
        </div>

        <div class="gk-modal-footer">
          <div class="gk-btn-group" style="width: 100%;">
            <button type="button" class="gk-btn gk-btn-secondary" style="flex: 1;" @click="viewMode = 'setting'">
              返回排版
            </button>
            <button type="button" class="gk-btn gk-btn-primary" style="flex: 1.5;" @click="close">
              已完成并关闭
            </button>
          </div>
        </div>
      </template>

      <!-- 视图 4: 异常报错重试视图 -->
      <template v-else-if="viewMode === 'error'">
        <div class="gk-modal-body">
          <div class="gk-error-box">
            <div class="gk-error-icon">⚠️</div>
            <div class="gk-error-title">排版任务未完成</div>
            <div class="gk-error-desc">{{ errorMessage || '服务暂时无法连接，请确认本地后端服务已启动。' }}</div>
            <div class="gk-error-hint">💡 建议检查本地 8000 端口服务或刷新当前页面后再试</div>
          </div>
        </div>

        <div class="gk-modal-footer">
          <div class="gk-btn-group" style="width: 100%;">
            <button type="button" class="gk-btn gk-btn-cancel" style="flex: 0.8;" @click="close">
              关闭
            </button>
            <button type="button" class="gk-btn gk-btn-secondary" style="flex: 1;" @click="viewMode = 'setting'">
              返回设置
            </button>
            <button type="button" class="gk-btn gk-btn-primary" style="flex: 1.2;" @click="handleRetry">
              重试排版
            </button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { RenderTypographySettings, DEFAULT_TYPOGRAPHY_SETTINGS, UnifiedPaper, MistakePageMeta } from '../../adapters'
import { accountStore, AccountState } from '../../utils/account-state'
import { BACKEND_BASE } from '../../utils/auth-protocol'

const props = defineProps<{
  modelValue: boolean
  paper: UnifiedPaper | null
  mistakeMeta: MistakePageMeta | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', val: boolean): void
  (e: 'export', settings: RenderTypographySettings, target: 'computer_download' | 'mobile_sync'): void
}>()

const logoUrl = typeof chrome !== 'undefined' && chrome.runtime?.getURL ? chrome.runtime.getURL('icons/icon48.png') : ''

// 视图模式: setting (主设置), loading (排版中), delivery (扫码交付), error (异常重试)
const viewMode = ref<'setting' | 'loading' | 'delivery' | 'error'>('setting')

// 账户与额度状态
const accountState = ref<AccountState>({ status: 'loading' })
const isLoggedIn = computed(() => accountState.value.status === 'ready' && accountState.value.quota.is_logged_in)
const userName = computed(() => accountState.value.status === 'ready'
  ? accountState.value.quota.user?.nickname || accountState.value.quota.user?.username || '题本学员' : '')
const remainingQuota = computed(() => accountState.value.status === 'ready' ? accountState.value.quota.remaining_quota : null)
const dailyLimit = computed(() => accountState.value.status === 'ready' ? accountState.value.quota.daily_limit : null)
const quotaHint = computed(() => accountState.value.status === 'loading' ? '正在确认账户…'
  : accountState.value.status === 'error' ? '账户与额度暂时不可用'
  : accountState.value.refreshing ? '额度更新中…'
  : accountState.value.refreshError ? '额度更新失败，请重试'
  : `今日${isLoggedIn.value ? '' : '免登录'}剩余 ${remainingQuota.value} / ${dailyLimit.value} 次`)
const accountHint = computed(() => accountState.value.status !== 'ready' ? quotaHint.value
  : isLoggedIn.value ? '已登录 · 国考 1:1 标准考场版，支持 5分钱/张 快速双面打印'
  : `当前未登录 · 每日 ${dailyLimit.value} 次，登录微信小程序立享更多额度`)
let unsubscribeAccount: (() => void) | null = null

// 基础排版设置
const settings = reactive<RenderTypographySettings>({
  ...DEFAULT_TYPOGRAPHY_SETTINGS,
  includeAnswer: true,
  answerPlacement: 'merged',
  outputFormat: 'pdf',
  exportScope: 'all',
})

// 错题抽题数量
const selectedCount = ref(10)

// 加载状态与进度条
const currentExportTarget = ref<'computer_download' | 'mobile_sync'>('computer_download')
const loadingPercent = ref(15)
const loadingStepText = ref('智能解析题干与材料中...')
let progressTimer: any = null

// 交付与异常参数
const qrCodeUrl = ref('')
const savedPath = ref('')
const errorMessage = ref('')

// 计算属性：当前试卷基础信息
const paperTitle = computed(() => props.paper?.title || '已捕获真题/模考试卷')
const totalQuestions = computed(() => props.paper?.total_questions || 0)
const mistakeTotal = computed(() => props.mistakeMeta?.total || 0)

// 1. 核心情境感知判定 (第一性原理：区分模考大赛、知识点错题集训、常规真题)
const isMockExam = computed(() => {
  if (props.paper?.metadata?.isMockExam) return true
  const title = (props.paper?.title || '').toLowerCase()
  if (title.includes('模考') || title.includes('大赛')) return true
  if (typeof location !== 'undefined') {
    const href = location.href.toLowerCase()
    if (href.includes('/report') || href.includes('jam/solution') || href.includes('/mock/')) return true
  }
  return false
})

const isMistakeBook = computed(() => {
  return !isMockExam.value && Boolean(props.mistakeMeta && props.mistakeMeta.total > 10)
})

const isStandardPaper = computed(() => {
  return !isMockExam.value && !isMistakeBook.value
})

const sceneTagInfo = computed(() => {
  if (isMockExam.value) {
    return { name: '模考大赛 · 成绩解析', icon: '🎯', class: 'tag-mock' }
  }
  if (isMistakeBook.value) {
    return { name: '错题专项突破', icon: '⚡', class: 'tag-mistake' }
  }
  return { name: '历年真题 · 考场标准版', icon: '🏛️', class: 'tag-standard' }
})

// 2. 试卷题目池与错题提取
const rawAllQuestions = computed(() => {
  if (!props.paper?.sections) return []
  return props.paper.sections.flatMap((s) => s.questions || [])
})

// 错题过滤列表
const wrongQuestionsList = computed(() => {
  const list = rawAllQuestions.value.filter((q) => q && (q.is_wrong || q.isWrong))
  if (list.length > 0) return list
  const wrongIds = new Set<number>((props.paper?.metadata?.wrongQuestionIds || []).map(Number))
  const wrongKeys = new Set<string>((props.paper?.metadata?.wrongQuestionKeys || []).map(String))
  const wrongOrders = new Set<number>((props.paper?.metadata?.wrongQuestionOrders || []).map(Number))
  if (wrongIds.size > 0 || wrongKeys.size > 0 || wrongOrders.size > 0) {
    return rawAllQuestions.value.filter((q) => {
      const qid = Number(q.question_id || q.id)
      const qKey = String(q.key || (q as any).globalId || q.id || '')
      return (
        (qid && !isNaN(qid) && wrongIds.has(qid)) ||
        (qKey && wrongKeys.has(qKey)) ||
        (q.order_num && wrongOrders.has(q.order_num))
      )
    })
  }
  return []
})

const detectedWrongCount = computed(() => {
  return wrongQuestionsList.value.length || props.paper?.metadata?.totalWrong || 0
})

// 模考专属导出范围模式: 'mistake_only' (仅错题) | 'all' (全卷)
const mockExportScope = ref<'mistake_only' | 'all'>('mistake_only')

// 监听模考状态自适应默认选择
watch(
  () => [isMockExam.value, detectedWrongCount.value],
  ([isMock, wrongCnt]) => {
    if (isMock) {
      mockExportScope.value = Number(wrongCnt) > 0 ? 'mistake_only' : 'all'
    }
  },
  { immediate: true }
)

// 当前真正用于抽检和导出的题目数组
const displayQuestions = computed(() => {
  if (isMockExam.value && mockExportScope.value === 'mistake_only') {
    return wrongQuestionsList.value
  }
  return rawAllQuestions.value
})

const displayTotalQuestions = computed(() => {
  return displayQuestions.value.length
})

const currentCountDescription = computed(() => {
  if (isMockExam.value) {
    if (mockExportScope.value === 'mistake_only') {
      return detectedWrongCount.value > 0
        ? `已选做错题目 (${displayTotalQuestions.value} 题) · 原卷共 ${totalQuestions.value} 题`
        : `本次模考全对 (0 道错题) · 可选全卷导出`
    }
    return `全卷共 ${displayTotalQuestions.value} 道题 · B5考场全真卷`
  }
  if (isMistakeBook.value) {
    return `选定前 ${selectedCount.value} 题 (考点共 ${mistakeTotal.value} 题)`
  }
  return `${totalQuestions.value} 道题 · B5考场双面`
})

const exportButtonLabel = computed(() => {
  if (isMockExam.value) {
    return mockExportScope.value === 'mistake_only' ? '💻 导出模考错题卷 (PDF)' : '💻 导出模考全真卷 (PDF)'
  }
  if (isMistakeBook.value) {
    return '💻 导出错题突破集 (PDF)'
  }
  return '💻 下载考场试卷 (PDF)'
})

const hasAnswers = computed(() => {
  if (!props.paper) return false
  if (props.mistakeMeta) return true
  const meta = props.paper.metadata
  if (meta?.hasAnswers === true || meta?.scene === 'mistake' || meta?.scene === 'mock_exam') return true
  const title = props.paper.title || ''
  if (title.includes('错题') || title.includes('解析') || title.includes('复盘') || title.includes('模考')) return true
  if (props.paper.sections) {
    for (const sec of props.paper.sections) {
      if (sec.questions) {
        for (const q of sec.questions) {
          if ((q.answer && q.answer.trim()) || (q.analysis && q.analysis.trim())) return true
        }
      }
    }
  }
  return false
})

// 试题抽检与健康度核对状态
const showAllQuestions = ref(false)

const validStemCount = computed(() => {
  return displayQuestions.value.filter((q) => q && q.stem && cleanText(q.stem).length >= 4).length
})

const stemHealthStatus = computed(() => {
  const total = displayQuestions.value.length
  const valid = validStemCount.value
  if (total === 0) {
    if (isMockExam.value && mockExportScope.value === 'mistake_only') {
      return { class: 'warning', dotClass: 'orange', text: '本次模考未检测到错题 (全对或解析中)' }
    }
    return { class: 'error', dotClass: 'red', text: '未检测到试题' }
  }
  if (valid === total) {
    return { class: 'success', dotClass: 'green', text: `完整就绪 (${total} 题题干选项齐备)` }
  }
  if (valid > 0) {
    return { class: 'warning', dotClass: 'orange', text: `部分题干就绪 (${valid}/${total})` }
  }
  return { class: 'error', dotClass: 'red', text: '试题题干缺失，请等待加载' }
})

const canExport = computed(() => {
  return displayQuestions.value.length > 0 && validStemCount.value > 0
})

const sampleQuestion = computed(() => {
  return displayQuestions.value[0] || null
})

const sampleQuestionOptions = computed<string[]>(() => {
  const q = sampleQuestion.value
  if (!q || !Array.isArray(q.options)) return []
  return q.options.map((opt: any) => (typeof opt === 'string' ? opt : opt?.value || opt?.content || ''))
})

const isLongOptions = computed(() => {
  return sampleQuestionOptions.value.some((opt) => cleanText(opt).length > 12)
})

const sampleQuestionSourceTag = computed(() => {
  const q = sampleQuestion.value
  if (!q) return ''
  return formatQuestionSource(q)
})

function formatQuestionSource(q: any): string {
  const raw = q?.source || ''
  if (!raw) return ''
  if (raw.startsWith('【') && raw.endsWith('】')) return raw
  return `【${raw}】`
}

function cleanText(htmlOrText?: string): string {
  if (!htmlOrText) return ''
  return htmlOrText
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function getOptionLetter(idx: number): string {
  return ['A', 'B', 'C', 'D', 'E', 'F'][idx] || String(idx + 1)
}

// 监听试卷变化初始化题量与答案模式
watch(
  () => props.paper,
  (newPaper) => {
    if (newPaper) {
      if (props.mistakeMeta && props.mistakeMeta.total > 0) {
        selectedCount.value = Math.min(10, props.mistakeMeta.total)
      } else {
        selectedCount.value = newPaper.total_questions || 10
      }
      settings.questionLimit = selectedCount.value

      if (!hasAnswers.value) {
        settings.answerPlacement = 'none'
        settings.includeAnswer = false
      } else {
        if (settings.answerPlacement === 'none') {
          settings.answerPlacement = 'merged'
        }
        settings.includeAnswer = true
      }
    }
  },
  { immediate: true }
)

// 设置题量
function setCount(cnt: number) {
  const max = mistakeTotal.value || 100
  selectedCount.value = Math.max(1, Math.min(cnt, max))
  settings.questionLimit = selectedCount.value
}

function handleCustomCountChange() {
  const max = mistakeTotal.value || 100
  if (isNaN(selectedCount.value) || selectedCount.value < 1) selectedCount.value = 10
  if (selectedCount.value > max) selectedCount.value = max
  settings.questionLimit = selectedCount.value
}

// 设置答案排布模式
function setAnswerMode(mode: 'merged' | 'separate' | 'none') {
  settings.answerPlacement = mode
  settings.includeAnswer = mode !== 'none'
}

// 关闭弹窗 (核心：直接置为 false，Vue 自动完成所有销毁清理)
function close() {
  stopProgress()
  emit('update:modelValue', false)
  viewMode.value = 'setting'
}

// 触发导出
function handleExport(target: 'computer_download' | 'mobile_sync') {
  currentExportTarget.value = target
  settings.questionLimit = selectedCount.value
  settings.exportScope = isMockExam.value ? mockExportScope.value : 'all'
  emit('export', { ...settings }, target)
}

function handleRetry() {
  handleExport(currentExportTarget.value)
}

// 暴露给外部调用的视图控制接口
function showLoading(target: 'computer_download' | 'mobile_sync') {
  currentExportTarget.value = target
  viewMode.value = 'loading'
  loadingPercent.value = 15
  loadingStepText.value = '智能解析题干与材料中...'
  startProgress()
}

function showDelivery(options: { qrCodeUrl?: string; savedPath?: string; remainingQuota?: number }) {
  stopProgress()
  if (options.qrCodeUrl) qrCodeUrl.value = options.qrCodeUrl
  savedPath.value = options.savedPath || ''
  viewMode.value = 'delivery'
}

function showError(msg: string) {
  stopProgress()
  errorMessage.value = msg || '排版失败，请重试'
  viewMode.value = 'error'
}

// 进度条控制
function startProgress() {
  stopProgress()
  const startTime = Date.now()
  progressTimer = setInterval(() => {
    const elapsed = Date.now() - startTime
    if (elapsed > 1800 && elapsed <= 5500) {
      loadingStepText.value = '注入考场模块规范与版式...'
    } else if (elapsed > 5500) {
      loadingStepText.value =
        currentExportTarget.value === 'computer_download'
          ? '高清矢量编译与 PDF 导出中...'
          : '生成手机同步与小程序码...'
    }
    if (loadingPercent.value < 92) {
      const inc = elapsed < 5500 ? 3 : 1
      loadingPercent.value = Math.min(92, loadingPercent.value + inc)
    }
  }, 400)
}

function stopProgress() {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
}

function getStepClass(step: number) {
  if (step === 1) return loadingPercent.value > 25 ? 'done' : 'active'
  if (step === 2) {
    if (loadingPercent.value > 65) return 'done'
    if (loadingPercent.value > 25) return 'active'
    return ''
  }
  if (step === 3) {
    if (loadingPercent.value >= 90) return 'active'
    return ''
  }
  return ''
}

function getStepStatus(step: number) {
  if (step === 1) return loadingPercent.value > 25 ? '已完成' : '正在处理'
  if (step === 2) {
    if (loadingPercent.value > 65) return '已完成'
    if (loadingPercent.value > 25) return '正在注入'
    return '排队中'
  }
  if (step === 3) {
    if (loadingPercent.value >= 90) return '正在渲染'
    return '排队中'
  }
  return '排队中'
}

// 只在弹窗可见时订阅并请求，避免挂载和打开重复拉取。
watch(
  () => props.modelValue,
  (val) => {
    unsubscribeAccount?.()
    unsubscribeAccount = null
    if (val) {
      unsubscribeAccount = accountStore.subscribe((state) => { accountState.value = state })
      void accountStore.refresh()
    }
  },
  { immediate: true }
)

// 全局 Esc 键监听
function onKeyDown(e: KeyboardEvent) {
  if (e.key === 'Escape' || e.key === 'Esc' || e.code === 'Escape' || e.keyCode === 27) {
    if (props.modelValue) {
      e.preventDefault()
      e.stopPropagation()
      close()
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeyDown, true)
  document.addEventListener('keydown', onKeyDown, true)
})

onUnmounted(() => {
  stopProgress()
  window.removeEventListener('keydown', onKeyDown, true)
  document.removeEventListener('keydown', onKeyDown, true)
  unsubscribeAccount?.()
})

defineExpose({
  showLoading,
  showDelivery,
  showError,
  close,
})
</script>


