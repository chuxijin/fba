# 题库解析精编与发布

**功能标识：`question-explanation`**

用途：逐题手写精简解析，校验答案与题型逻辑，安全发布生产解析，并记录默认版本切换与执行结果。

## 下次只找这一个入口

将 [WORKFLOW.md](WORKFLOW.md) 发给AI，并说明本次题库或模考季数即可。

> 请阅读 `skills/fba_work/question-explanation/WORKFLOW.md`，处理生产库最新导入的第XX季模考。按规范处理政治理论和常识判断，新解析设默认，保留原官方解析，完成备份、预演和复核。所有任务文件放在本功能目录的runs下。

> **补充：解析里完整逐字复现原选项，不缩写、概括、换词或改语序；只在原句实际错处加红色删除线并紧跟蓝色正确表述，原错词仍须可见。正确项原文后追加短理由。组合/计数题的原陈述同样保留。核验时去掉新增标记/纠正/解释，还原原文与源一致；题目原选项、题干、答案不改。**

练习库则使用“新增非默认简短版、不改原默认”的策略，详见完整规范。

2026-11-01已将政治/常识“原文保留、原位纠错”要求补入规范及上述交接提示词；历史精简稿中有概括改写，不据此宣称旧稿已满足逐字保真。本轮不追溯改库。

## 逻辑填空简便解析

现行样式：**一词一行括号批注**，不是给整组选项统一打勾叉，也不用“／”把多词挤在同一行。例如：`A 浩浩荡荡（✓：可形容时代浪潮的声势）`换行`交口称赞（✗：此处宜用被称赞的表达）`；选项字母只出现在该选项首词行。

- 仅在明确指定逻辑填空时处理，不自动扩大到全部言语题或历史季次。
- 批注写在解析中，不修改答题选项，避免提前泄露答案。
- 每空每词都写自己的括号，每词独立一行（不使用“／”同行连接）；✓仅表示本空可用，错误组里的可用词仍打✓，不在整组末尾统一补理由。
- 不泛写“不合适”，不为了简短编造搭配禁忌；无法可靠判断的词先暂停核实。
- 首轮先做3—5题打样；样式不改变版本策略，模考仍设默认、原官方内容保留，有冲突先确认。

完整规则与HTML示例只在 [WORKFLOW.md 第5.3节](WORKFLOW.md#53-逻辑填空选项旁批注式简便解析) 维护。第41季已另建[3题打样任务](runs/20261101-season41-logic-sample/README.md)，仅本地手写预览，未写库。

## 目录

```text
question-explanation/
  README.md
  WORKFLOW.md                        # 唯一现行规范
  scripts/
    new_run.py                       # 创建任务目录、状态说明和临时目录
  runs/
    20261101-season41/                # 已完成：政治11+常识7，18题设为默认
      README.md                      # 本轮完成状态和备份信息
      source.json                    # 入库前只读快照
      final.json                     # 最终手写解析
      validate_and_build.py          # 本轮校验和SQL生成脚本，固定18题，不可直接用于下一季
      sync.sql                       # 已执行SQL，仅审计，禁止重复提交
      validation.json
      verify.json
      q104096_option_d.png            # 公式图片核验依据
  archive/
    legacy-20261026/                  # 早期520题流程和旧脚本，停用参考
    legacy-20261027-31/               # 原scratch/season7完整历史资料
```

## 开始新一轮

从仓库根目录执行，例如：

```powershell
uv run python skills/fba_work/question-explanation/scripts/new_run.py 20261108-season42 --title '第42季模考解析'
```

脚本只创建本地目录和状态说明，不读取数据库、不生成解析、不执行SQL。已有目录会拒绝覆盖。
任务仍必须先重新查询生产范围，不能直接复制上一季SQL或题量。

## 已完成任务

- [省考最新三季模考（第三十四季/第一季/第二季）政治、常识与逻辑填空](runs/20261109-shengkao-3seasons/README.md)：2026-11-09生产提交20题（政治3、常识13、逻辑填空4/32词），default设默认、official原文保留；三来源合并66题守卫通过，原文保真及逐词校验通过，发布后144/144独立核验通过，新增20条default ID131669—131688。新增「任意N项陈述」分支（104681为5项组合题，②④⑤）。备份表 `qbank_v2_question_explanation_bak_20261109_shengkao` 独立COMMIT。
- [第14季政治、常识与逻辑填空](runs/20261105-season14/README.md)：2026-11-05生产提交20题（政治9、常识9、逻辑填空2/20词），default设默认、official原文保留；原文保真及逐词校验通过，发布后144/144独立核验通过，新增20条default ID131422—131441。新增「排序题（按时间先后排序）」分支（104535、104536）。备份表 `qbank_v2_question_explanation_bak_20261105_s14` 独立COMMIT。
- [第13季政治、常识与逻辑填空](runs/20261103-season13/README.md)：2026-11-03生产提交23题（政治10、常识9、逻辑填空4/40词），default设默认、official原文保留；原文保真及逐词校验通过，发布后165/165独立核验通过，新增23条default ID131249—131271。备份表 `qbank_v2_question_explanation_bak_20261103_s13` 独立COMMIT。
- [第12季政治、常识与逻辑填空](runs/20261102-season12/README.md)：2026-11-02生产提交20题（政治9、常识3、逻辑填空8/72词），default设默认、official原文保留；原文保真及逐词校验通过，发布后232/232独立核验通过。整季37题原题/答案/学习记录与17道非目标解析未改。
- [第12季逻辑填空一词一行改版（Batch 1）](runs/20261102-season12-logic-reformat/README.md)：2026-11-02晚将第12季8道逻辑填空重发为“一词一行”新格式，备份独立COMMIT，发布后独立复核PASS（8/8逐字）。
- [无 module_path 模考逻辑填空改版（Batch 2）](runs/20261102-nomodule-logic-fill/README.md)：2026-11-02将第7/8/9/10/41季共22道无 module_path 模考逻辑填空重发为“一词一行”新格式（第41季3题复用打样成品转正），备份独立COMMIT，发布后独立复核161/161 PASS，新增22条default ID130807—130828。
- 带 module_path 模考逻辑填空改版（Batch 3）按 28 来源 / 127 题拆 10 个子批推进（计划见 `runs/20261102-nomodule-logic-fill/work/plan_batch3.md`）：
  - [Batch 3-1](runs/20261102-b3-1-logic-fill/README.md)：2026-11-02发布，第一季（地市级）8题+第二季（行政执法类）4题=12题，备份表 `qbank_v2_question_explanation_bak_20261102_b3_1` 独立COMMIT，dry-run ROLLBACK、发布COMMIT，独立SQL核验 12/12/0、MCP核验 91/91 PASS，新增12条default ID130841—130852。
  - [Batch 3-2](runs/20261102-b3-2-logic-fill/README.md)：2026-11-02发布，第三季（地市级）5题+第四季（地市级）7题=12题，备份表 `qbank_v2_question_explanation_bak_20261102_b3_2` 独立COMMIT，dry-run ROLLBACK、发布COMMIT，独立SQL核验 12/12/0、MCP核验 91/91 PASS，新增12条default ID130865—130876。
  - [Batch 3-3](runs/20261102-b3-3-logic-fill/README.md)：2026-11-02发布，第五季（地市级）4题+第十七季（地市级）3题+第十八季（地市级）5题=12题，备份表 `qbank_v2_question_explanation_bak_20261102_b3_3` 独立COMMIT，dry-run ROLLBACK、发布COMMIT，独立SQL核验 12/12/0、MCP核验 91/91 PASS，新增12条default ID130889—130900。
  - [Batch 3-4](runs/20261102-b3-4-logic-fill/README.md)：2026-11-02发布，第十九季（地市级）6题+第二十季（地市级）6题=12题，备份表 `qbank_v2_question_explanation_bak_20261102_b3_4` 独立COMMIT，dry-run ROLLBACK、发布COMMIT，独立SQL核验 12/12/0、MCP核验 91/91 PASS，新增12条default ID130913—130924。
  - [Batch 3-5](runs/20261102-b3-5-logic-fill/README.md)：2026-11-02发布，第二十一季（地市级）5题+第二十二季（地市级）2题+第二十三季（地市级）5题=12题，备份表 `qbank_v2_question_explanation_bak_20261102_b3_5` 独立COMMIT，dry-run ROLLBACK、发布COMMIT，独立SQL核验 12/12/0、MCP核验 91/91 PASS，新增12条default ID130937—130948。
  - [Batch 3-6](runs/20261102-b3-6-logic-fill/README.md)：2026-11-02发布，第二十四季（地市级）5题+第二十五季（地市级）3题+第二十六季（地市级）5题=13题，备份表 `qbank_v2_question_explanation_bak_20261102_b3_6` 独立COMMIT，dry-run ROLLBACK、发布COMMIT，本批起采用精简流程：MCP after 与锁内快照逐字段比对 98/98 PASS（独立只读SQL旁路改为每3—5批抽查一次），新增13条default ID130975—130987。
  - [Batch 3-7](runs/20261102-b3-7-logic-fill/README.md)：2026-11-02发布，第二十七季（地市级）8题+第二十八季（地市级）3题+第二十九季（地市级）6题=17题，备份表 `qbank_v2_question_explanation_bak_20261102_b3_7` 独立COMMIT，dry-run ROLLBACK、发布COMMIT，MCP after 与锁内快照逐字段比对 126/126 PASS，新增17条default ID131005—131021。
  - [Batch 3-8](runs/20261102-b3-8-logic-fill/README.md)：2026-11-02发布，第三十季（地市级）2题+第三十一季（地市级）5题+第三十二季（地市级）5题=12题，备份表 `qbank_v2_question_explanation_bak_20261102_b3_8` 独立COMMIT，dry-run ROLLBACK、发布COMMIT，MCP after 与锁内快照逐字段比对 91/91 PASS，新增12条default ID131034—131045。
  - [Batch 3-9](runs/20261102-b3-9-logic-fill/README.md)：2026-11-02发布，第三十三季（地市级）2题+第三十四季（地市级）6题+第三十五季（行政执法类）4题=12题，备份表 `qbank_v2_question_explanation_bak_20261102_b3_9` 独立COMMIT，dry-run ROLLBACK、发布COMMIT，MCP after 与锁内快照逐字段比对 91/91 PASS，新增12条default ID131058—131069。
  - [Batch 3-10](runs/20261102-b3-10-logic-fill/README.md)：2026-11-02发布（**Batch 3 最后一批，Batch 3 十批全部完成**），第三十六季（地市级）4题+第三十七季（地市级）5题+第三十九季（地市级）3题+第四十季（地市级）1题=13题，备份表 `qbank_v2_question_explanation_bak_20261102_b3_10` 独立COMMIT，dry-run ROLLBACK、发布COMMIT，MCP after 与锁内快照逐字段比对 98/98 PASS，新增13条default ID131083—131095。

| 归档 | 状态 |
|---|---|
| [省考最新三季](runs/20261109-shengkao-3seasons/README.md) | 2026-11-09已提交：第三十四季/第一季/第二季政治3+常识13+逻辑填空4共20题；20条新default、20条official保留非默认；144/144独立核验通过；新增任意N项陈述分支（5项组合题） |
| [第14季](runs/20261105-season14/README.md) | 2026-11-05已提交：政治9+常识9+逻辑填空2共20题；20条新default、20条official保留非默认；144/144独立核验通过；新增排序题分支 |
| [第13季](runs/20261103-season13/README.md) | 2026-11-03已提交：政治10+常识9+逻辑填空4共23题；23条新default、23条official保留非默认；165/165独立核验通过 |
| [第41季](runs/20261101-season41/README.md) | 2026-11-01已提交：18条新default、18条official保留非默认；独立核验通过 |
| [第41季逻辑填空打样](runs/20261101-season41-logic-sample/README.md) | 已导入范围内单空/双空/三空各1题，本地打样；其中104100/104101/104102已于Batch 2转正发布，打样目录仍保留原始验收产物 |
| `archive/legacy-20261027-31/` | 旧模考、米6套卷198题、肖193题193题、米李720题785题；完整保留原文件布局，仅供查证 |

## 清理与保留规则

**必须长期保留**：README状态、source源快照、final成品、核验结果、备份表名称、必要的图片事实依据。生产备份表不能作为临时文件清理。

**按任务保留**：已执行SQL、能重建SQL的本轮脚本、校验报告。本轮已执行SQL留作审计，禁止重放。

**可及时清理**：本轮`work/`中已被最终文件完整覆盖的分片、重复导出、调试日志、临时预览。只有确认任务完成、无待处理题、成品及校验记录齐全时才清理；不能只按扩展名或文件年龄批量删除。

**历史归档**：不默认阅读、不自动执行。旧脚本可能有固定ID、相对路径或已失效的会话缓存路径，不属于可复用工具。不要因为归档迁移而重新执行数据库写入。

本次只迁移已知解析任务文件，不顺带清理不明归属的scratch数据、其他业务文件或用户改动。
