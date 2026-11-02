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
                  ? '导出题本将保存到当前账号，可在微信小程序【我的题本】中查看。可用额度以当前账号为准。'
                  : `未登录状态每日可导出 ${dailyLimit} 次标准考场卷。导出后可微信扫码，登录并确认保存到【我的题本】。`
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
              :title="!canExport ? '试题内容尚未就绪，请等待加载' : '微信扫码直达我的题本'"
              @click="handleExport('mobile_sync')"
            >
              📱 导出到手机 (微信扫码)
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

            <div class="gk-progress-label" role="status" aria-live="polite">
              正在准备或处理排版任务，完成后自动交付。处理期间请保持当前题库网页打开。
            </div>
          </div>
        </div>

        <div class="gk-modal-footer">
          <div class="gk-loading-footer-tip">
            题量、图片和导出格式会影响处理时间。此处不显示预估百分比，请勿重复提交。
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
                  {{ reusedExport ? '该内容已排版，已为您找回原结果' : currentExportTarget === 'computer_download' ? (downloadWarning ? '排版已完成，请确认浏览器下载' : '排版已完成，已提交浏览器下载') : '试卷已生成，请用微信扫码打开我的题本' }}
                </div>
                <div class="gk-banner-desc">
                  <template v-if="reusedExport">题目和排版设置相同，直接复用已有文件，不重新排版、不重复扣额度。您可以再次下载，或扫描下方二维码打开题本。</template>
                  <template v-else-if="currentExportTarget === 'computer_download'">
                    《{{ paperTitle }}》{{ downloadStarted ? '已提交浏览器下载。' : '已生成，可重试下载，不会重新排版或扣额度。' }}
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

            <div v-if="downloadWarning" role="alert" class="gk-card-section">
              <p>{{ downloadWarning }}</p>
              <button type="button" :disabled="retryingDownload" @click="retryDownload">
                {{ retryingDownload ? '正在重试…' : '重试下载（不重新排版）' }}
              </button>
            </div>

            <div v-if="deliveryFiles.length" class="gk-card-section">
              <button type="button" class="gk-btn gk-btn-secondary" :disabled="retryingDownload" @click="downloadAgain">
                {{ retryingDownload ? '正在提交下载…' : '再次下载（不重新排版）' }}
              </button>
              <p>已登录的题本也可在同一账号的小程序【我的题本】中查看。</p>
            </div>

            <!-- 2. 使用说明与额度说明 -->
            <div class="gk-card-section">
              <div class="gk-card-section-title">
                <span>📌 使用说明与额度规则</span>
                <span class="gk-quota-pill">{{ quotaHint }}</span>
              </div>
              <div class="gk-card-section-text">
                • <strong>免登录体验</strong>：额度以当前服务端返回的每日限制为准。<br />
                • <strong>账号归属</strong>：插件已登录时保存到原账号；游客导出由手机登录后首位确认领取的账号保存。<br />
                • <strong>下载重试</strong>：排版完成后重试下载使用同一份文件，不重新排版、不重复扣额度。
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
              </div>
            </div>

            <!-- 4. 微信小程序生态引流 -->
            <div class="gk-miniapp-lead">
              <img v-if="qrImage" class="gk-miniapp-lead-img" :src="qrImage" alt="微信扫码打开本次题本" @error="qrImage = ''; qrError = '二维码显示失败，请重试'" />
              <div v-else>
                <p>{{ qrError || '小程序码生成中…' }}</p>
                <button v-if="qrError && qrCodeUrl" type="button" :disabled="qrLoading" @click="loadQrCode">重新加载二维码</button>
              </div>
              <div class="gk-miniapp-lead-info">
                <div class="gk-miniapp-lead-title">📱 微信扫码 · 打开【我的题本】</div>
                <ul class="gk-miniapp-lead-list">
                  <li>微信扫码直接进入“我的题本”，登录后保存本次试卷</li>
                  <li>插件已登录时，请使用同一账号；游客题本由首位确认领取的账号保存</li>
                  <li>领取码24小时内有效；查看题本不会授权电脑登录，也不会自动下单</li>
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
            <div class="gk-error-title">{{ errorKind === 'failed' ? '本次排版未成功' : errorKind === 'unknown' ? '暂时未能确认排版结果' : '暂时无法导出' }}</div>
            <div class="gk-error-desc">{{ errorMessage || '服务暂时无法连接，请检查网络或稍后重试。' }}</div>
            <div class="gk-error-hint">通信中断不代表排版失败。24小时交付有效期内，继续获取会优先查找原任务，不因结果未知重复排版；已登录用户也可先查看同一账号的“我的题本”和浏览器下载列表。</div>
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
              {{ errorKind === 'failed' ? '重新排版' : errorKind === 'unknown' ? '继续获取结果' : '重试连接' }}
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
import type { DeliveryView, ExportFile } from '../../utils/export-delivery'
import { exportMessage, requestFileDownloads } from '../../utils/export-flow'

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
  : isLoggedIn.value ? '已登录 · 导出文件可在当前账号的我的题本中查看'
  : `当前未登录 · 每日 ${dailyLimit.value} 次，导出后可扫码保存题本`)
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

// 交付与异常参数
const qrCodeUrl = ref('')
const savedPath = ref('')
const errorMessage = ref('')
const errorKind = ref<'request' | 'unknown' | 'failed'>('request')
const reusedExport = ref(false)
const deliveryFiles = ref<ExportFile[]>([])
const downloadWarning = ref('')
const downloadStarted = ref(false)
const failedFiles = ref<ExportFile[]>([])
const retryingDownload = ref(false)
const qrImage = ref('')
const qrError = ref('')
const qrLoading = ref(false)
let deliveryVersion = 0

async function loadQrCode() {
  if (!qrCodeUrl.value || qrLoading.value) return
  const version = deliveryVersion
  qrLoading.value = true
  qrError.value = ''
  try {
    const result = await exportMessage('GET_RENDER_QR', { url: qrCodeUrl.value })
    if (version === deliveryVersion) qrImage.value = result.image
  } catch (error: any) {
    if (version === deliveryVersion) qrError.value = error?.message || '小程序码生成失败，请重试'
  } finally { if (version === deliveryVersion) qrLoading.value = false }
}

async function retryDownload() {
  if (retryingDownload.value || !failedFiles.value.length) return
  const version = deliveryVersion
  retryingDownload.value = true
  const result = await requestFileDownloads(failedFiles.value)
  if (version !== deliveryVersion) return
  failedFiles.value = result.failedFiles || []
  downloadWarning.value = result.downloadWarning || ''
  downloadStarted.value ||= Boolean(result.downloadStarted)
  savedPath.value ||= result.savedPath || ''
  retryingDownload.value = false
}

async function downloadAgain() {
  if (retryingDownload.value || !deliveryFiles.value.length) return
  const version = deliveryVersion
  retryingDownload.value = true
  const result = await requestFileDownloads(deliveryFiles.value)
  if (version !== deliveryVersion) return
  failedFiles.value = result.failedFiles || []
  downloadWarning.value = result.downloadWarning || ''
  downloadStarted.value ||= Boolean(result.downloadStarted)
  savedPath.value ||= result.savedPath || ''
  retryingDownload.value = false
}

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
  deliveryVersion++
  qrCodeUrl.value = ''
  qrImage.value = ''
  qrError.value = ''
  qrLoading.value = false
  failedFiles.value = []
  deliveryFiles.value = []
  reusedExport.value = false
  downloadWarning.value = ''
  downloadStarted.value = false
  retryingDownload.value = false
  currentExportTarget.value = target
  viewMode.value = 'loading'
}

function showDelivery(options: DeliveryView) {
  deliveryFiles.value = options.files || []
  reusedExport.value = Boolean(options.reused)
  qrCodeUrl.value = options.qrCodeUrl || ''
  savedPath.value = options.savedPath || ''
  failedFiles.value = options.failedFiles || []
  downloadWarning.value = options.downloadWarning || ''
  downloadStarted.value = Boolean(options.downloadStarted)
  viewMode.value = 'delivery'
  void loadQrCode()
}

function showError(msg: string, kind: 'request' | 'unknown' | 'failed' = 'request') {
  errorKind.value = kind
  errorMessage.value = msg || '暂时无法确认排版结果，请稍后继续获取'
  viewMode.value = 'error'
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
  deliveryVersion++
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
