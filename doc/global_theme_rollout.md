# 小程序全局绿色主题统一

## 决策与范围

用户确认使用用户报告页的 `#168060` 为品牌绿。此次统一主题规则，不重排已确认的布局，不修改后端、出题、登录、支付或数据库逻辑，不安装依赖。

- 四个主页面、底部导航、Wot 通用控件采用同一主色和表面层级。
- 报告、题库详情、个人资料、订单及会员流程普通控件改为语义变量。
- 分包中通用文字、卡片、导航及选中态逐步消除旧的蓝紫色覆盖，暗色文字不再由页面各选一套灰度。
- 练习键盘和原生开关、滑块使用品牌绿。
- 保留会员 FREE/VIP/SVIP 标识和玻璃卡片、科目分类、正确/错误/警告、游戏插画、空间几何面色及练习纸张背景；这些不是整页品牌主题。
- 没有对代码库所有十六进制颜色做一刀切替换。图表系列、画布、教材插图等依然需要各自的颜色表达。

## 唯一色板与接入点

1. `D:/100_Work/101_Program/Proj/fba/mini/src/utils/appTheme.ts`：浅色/暗色色板、颜色角色、Wot v2 映射。
2. `D:/100_Work/101_Program/Proj/fba/mini/src/style/app-theme.css`：生成的全局 CSS；不要单独修改。
3. `D:/100_Work/101_Program/Proj/fba/mini/scripts/generate-app-theme.cjs`：默认输出 apply_patch 补丁，`--check` 检测色板和 CSS 是否同步。
4. `D:/100_Work/101_Program/Proj/fba/mini/src/App.ku.vue`：在应用根节点提供明暗变量并传给 Wot ConfigProvider。
5. `D:/100_Work/101_Program/Proj/fba/mini/src/style/theme.css`：只保留科目/会员等例外和尺寸变量，不再覆盖页面主色。
6. `D:/100_Work/101_Program/Proj/fba/mini/src/utils/appSettings.ts`：系统导航和页面底色采用同一色板。

## 使用规则

| 场景 | 变量/类 |
| --- | --- |
| 页面背景 | `--gradient-page` / `--color-bg-page` |
| 卡片、输入 | `--color-bg-card` / `--color-bg-input` |
| 主文字、次要文字、说明 | `--color-text-primary` / `--color-text-secondary` / `--color-text-tertiary` |
| 文字和选中图标 | `--color-primary` |
| 实心主按钮 | `--color-primary-fill` + `--color-on-primary` / `bg-brand text-on-brand` |
| 强调块 | `brand-surface` 或 `--gradient-brand` |
| 浅强调 | `--color-primary-bg` |
| 错误/警告/成功 | 独立语义颜色，并同时提供文字或图标 |

暗色模式的文字强调绿是 `#88d5b2`，不是把所有按钮都变成浅绿；实心按钮保留 `#168060` + 白字，避免亮绿上的白字对比度不足。背景为统一中性深灰，不再逐页深紫、深蓝。

新页面禁止新增 `theme-domain-*` 主色覆盖。会员色只能用于会员身份/权益表达，不应接管整个页面的普通操作按钮。

## 验证与复查

在 `D:/100_Work/101_Program/Proj/fba/mini`：

```powershell
node --test --test-reporter=dot tests/*.test.cjs
node scripts/generate-app-theme.cjs --check
pnpm run type-check
$env:SKIP_OPEN_DEVTOOLS='true'; pnpm run build:mp
node scratch/app-theme-preview.cjs
node scratch/user-report-preview.cjs
```

- 测试覆盖颜色对比度、Wot 实际变量映射、全局别名、导航一致性、会员/科目例外、全应用 Vue 模板编译及既有行为回归。
- 对比度断言针对主/次/说明/强调文字在页面、卡片、输入和浅强调底上的组合，及白字主按钮；不是对全部页面宣称 WCAG 合规。
- 四个主页对照使用实际模板片段和构建后的样式、示例数据、模拟平台控件；不是完整主页面、真实账号或微信真机截图。
- 报告页另测 320/390px、浅/暗色、普通/全零/长数字，共12组，保留日期选择、说明展开、榜单路由与刷新失败的检查。
- 构建中已有部分 Carbon 图标缺失、`pkg/shared/index` 和 `p` 选择器警告；不属于本次主题改动。

## 真机验收清单

1. 在设置中切换浅色、暗色、跟随系统；连续切换学习/规划/能力/我的，核对背景、文字和底部选中绿。
2. 打开登录弹窗、设置开关、规划任务弹窗，确认弹出层也跟随主题，输入文字可读。
3. 进入报告、题库详情、个人资料和我的订单，确认旧布局保留且颜色不跳变。
4. 进入计算练习，检查键盘数字、比较选中态、确认键与正误状态。
5. 检查 FREE/VIP/SVIP 徽标和权益卡片仍保持等级区分，普通按钮保持全局绿色。
6. 如仍有色差，请提供页面路径、明暗模式和截图；尤其画布、第三方原生组件不能仅凭浏览器预览确认。
