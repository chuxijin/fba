# 意见反馈表单优化（2026-10-10）

## 改动范围

- `mini/src/components/feedback/FeedbackPanel.vue`：独立页面与快速反馈弹窗共用的表单。
- `mini/src/components/feedback/FeedbackPopup.vue`：统一外观、明确滚动区域，处理中的关闭/跳转防护。
- `mini/src/pkg/mine/feedback/index.vue`：移除旧紫色装饰，使用自然页面滚动；离开页面清除成功返回定时器。
- `mini/src/components/form/ImageUploadGrid.vue`：维持现有尺寸、localOnly、上传路径和事件契约，增加禁用与失败重试能力。
- `mini/src/utils/feedback.ts`：补充分类输入提示、校验来自路由的反馈类型；接口、字段和六个类型值不变。
- 未调整反馈记录页的数据加载或布局，未修改后端/数据库，未安装依赖，也未发布。

## 修复和视觉规范

原表单使用 `wd-select-picker` 的旧默认插槽触发器；已安装的 Wot v2 选择器仅提供弹层，不渲染该插槽，因此类型区域空白。

现改用已安装的 Wot RadioGroup/Radio 按钮形态，3列×2行，当前类型有主题绿底色、边框和勾选。六种类型不再使用六套颜色；从题目入口进入会保留预选类型和关联信息。

移除光斑、毛玻璃和紫色渐变。反馈记录改为表单上方文字入口。描述使用动态短提示与 `已输入 / 500` 计数；输入高度144px，附带适当内边距。截图为选填、最多3张，登录提示按当前状态展示。提交按钮紧跟表单，不占固定底栏。长关联内容可展开/收起，提交载荷仍包含完整文本。

## 行为保护

- 提交中禁用类型和附件修改、防重复提交；成功到页面退出之间也不能重复发送。
- 失败保留描述和附件，展示可重试提示；输入空白或超过500字不提交。
- 原有文字反馈的提交鉴权交给原接口处理，没有新增前端强制登录门槛；截图仍需登录。
- 图片选择前即锁定批次，避免快速点击重复打开相册；选图取消不报失败。
- 多张图片部分失败时保留成功结果，失败项可重试或放弃；反馈表单要求处理失败项后再提交，避免悄悄漏掉附件。
- 上传、重试、提交的迟到结果受到卸载/会话校验保护；账号变更后不会写入旧上传结果，也不会继续上传同一批剩余文件。
- 共享上传组件保留 `sm/md/lg`（72/88/144px）、本地选图和最大数量限制。

## 验证

- 新增 `mini/tests/feedback-form.test.cjs`：19项，覆盖实际脚本的类型预选、载荷、限制、失败重试、上传批次、会话与卸载、弹窗关闭。
- 全量前端220项测试、全量类型检查、改动文件ESLint、微信构建通过。
- `mini/scratch/feedback-preview.cjs`：使用实际页面/表单/上传组件和安装版本的Wot单选框脚本、模板、样式，模拟平台API、按钮/弹层外壳及服务响应。
- 检查320/390px × 浅/深色 × 独立页/弹窗，六个选项可见且不截字，每项至少44px；验证上传部分失败重试、删除、登录提示、500字限制和失败后重提。
- 补充320×568短屏弹窗滚动和长关联内容展开检查。
- 未实际提交任何反馈或上传用户图片，未做微信真机测试。构建保留原有Carbon图标、`pkg/shared/index`及`p`选择器警告。

## 真机验收

1. 重新编译后打开「我的 → 意见反馈」，确认六种类型均可选择、选中态正确。
2. 试切类型、输入、退出输入法；检查原生键盘弹起时不遮挡正在输入的内容。
3. 从题目纠错打开快速反馈，确认关联题目、预选类型、弹窗滚动和取消正常。
4. 上传1～3张不含隐私信息的测试截图，检查预览/删除，弱网失败可重试或放弃。
5. 如要验证真实提交，请明确填写测试反馈，避免误当业务问题；纯视觉验收不需要发送。

执行目录 `mini`：

```powershell
node --test --test-reporter=dot tests/*.test.cjs
pnpm exec eslint src/components/feedback/FeedbackPanel.vue src/components/feedback/FeedbackPopup.vue src/components/form/ImageUploadGrid.vue src/pkg/mine/feedback/index.vue src/utils/feedback.ts
pnpm run type-check
$env:SKIP_OPEN_DEVTOOLS='true'; pnpm run build:mp
node scratch/feedback-preview.cjs
```
