# D / E 盘目录与使用规范

本文只保留现行规则；目录树是分类目标，不代表所有目录都已创建或所有旧软件都已迁移。按需建目录，不为外观搬动正常工作的安装程序。

## 1. 基本原则

- **D 盘放运行环境，E 盘放资料、可再生缓存与本地恢复副本。**这不是性能承诺；跨分区副本不等于独立备份。
- **一份数据一个权威实体位置。**项目必需版本、软件内置运行时、正式备份不算无意重复；兼容链接也不占第二份实体空间。
- **路径稳定优先于外观统一。**项目依赖、软件托管数据、系统目录不因编号规则强行搬迁。
- **先判断性质，再选目录。**程序、正式资料、持久用户数据、缓存、临时文件不能混为一类。

### 命名与层级

- 人工分类统一为 `NNN_Name`：三位编号、下划线、英文 PascalCase；编号在同一父目录内唯一。
- 一级用整百（`100_Work`），二级用所属百位内整十（`110_Development`），三级用所属十位内编号（`111_Environments`）；四级以后需要细分时用局部 `010_Name`。
- **分类必须编号，具体软件、仓库、工具内部目录不强制编号。**例如 `210_Office\WPS`、`710_Packages\uv`。
- 通常三层分类足够；仅在权限、生命周期或检索确有差异时增加第四层，不为补齐层级创建空目录。

## 2. D 盘：运行区

```text
D:\
├─ 100_Work
│  └─ 110_Development
│     ├─ 111_Environments
│     │  ├─ 010_Python\uv\         bin / python / tools / tool-bin
│     │  ├─ 020_Node\              nvm / current
│     │  ├─ 030_Java\              按项目需要保留 JDK 版本
│     │  ├─ 040_Rust\              cargo / rustup
│     │  ├─ 050_Mobile\            Android / Flutter
│     │  ├─ 060_VersionControl\Git
│     │  └─ 070_Typesetting\TeXLive
│     ├─ 112_Projects               新项目的目标分类
│     └─ 113_Software               开发软件的目标分类
├─ 200_Apps
│  ├─ 210_Office                    办公、沟通
│  ├─ 220_Creative                  图片、视频、设计
│  └─ 230_Utilities                 需要安装的通用工具
├─ 300_Games
│  ├─ 310_Steam
│  └─ 320_WeGame
├─ 400_Common
│  ├─ 410_Portable                  便携软件，每个软件独立目录
│  └─ 420_Scripts                   自己维护的脚本
└─ 900_Temp
   ├─ 910_Extract                   临时解压
   └─ 920_Build                     明确支持独立输出的一次性构建
```

开发环境基座为 `D:\100_Work\110_Development\111_Environments`。现有代码和开发软件仍可使用 `D:\100_Work\101_Program\Proj`、`Software`；不批量改名或迁移正在使用的仓库。旧 `Env` 不是现行环境入口。

## 3. E 盘：资料与托管数据

```text
E:\
├─ 100_Work
│  ├─ 110_Business                  按具体业务组织文档、素材、交付件
│  └─ 120_Shared                    真正跨业务共用的资料
├─ 200_Study
│  ├─ 210_CivilService
│  ├─ 220_IELTS
│  └─ 230_Notes                     笔记库及附件
├─ 300_Life
│  ├─ 310_Personal                  证件、合同、个人记录
│  ├─ 320_Media                     照片、录屏、音视频
│  └─ 330_AppData                   应用支持迁移的持久用户数据
├─ 500_Archive
│  ├─ 510_Work
│  └─ 520_Study
├─ 600_Downloads
│  ├─ 610_Browser
│  ├─ 620_CloudDrive
│  └─ 630_Incoming                  待分类入口，不是长期仓库
│     ├─ 631_Screenshots             新截图的默认中转位置
│     └─ 632_Recordings              新录屏的默认中转位置
├─ 700_Cache
│  ├─ 710_Packages                  uv / pnpm / pip / gradle
│  ├─ 720_Models\huggingface         可重新获取的模型
│  └─ 730_Browsers\playwright       自动化浏览器，不含个人资料
├─ 800_System
│  ├─ 810_Linux                     WSL / Linux
│  ├─ 820_VirtualMachines
│  └─ 830_Emulators\android-avd      模拟器用户数据，不是普通缓存
└─ 900_Backup
   ├─ 910_Database
   ├─ 920_Config                    配置、恢复资料、维护记录
   └─ 930_Files                     重要文件恢复副本
```

归档是保留历史，备份是用于恢复，不能互相代替。自训权重、唯一数据集、聊天数据库、模拟器存档不能按可再生缓存清理。

### 新文件的默认入口

| 来源 | 约定位置 | 边界 |
| --- | --- | --- |
| 浏览器下载 | `E:\600_Downloads\610_Browser` | 各浏览器分别设置；保留用户原有“下载前询问”习惯 |
| 网盘下载 | `E:\600_Downloads\620_CloudDrive\软件名` | 夸克用 QuarkCloudDrive，百度用 BaiduNetdisk；只管下载，不改变同步或备份根 |
| 截图 | `E:\600_Downloads\630_Incoming\631_Screenshots` | Windows 标准 Screenshots 入口；工具有独立自定义设置时需在工具内同步选择 |
| 录屏 | `E:\600_Downloads\630_Incoming\632_Recordings` | Windows Game Bar Captures 入口；不启用原本关闭的录屏功能，不代表截图工具等所有应用已跟随 |

这些是新文件的中转入口，不自动删除内容；正式工作、学习或个人资料仍按用途归档。只设置新入口不搬旧文件，也不重定向整个 Downloads、Pictures 或 Videos。Chrome、夸克浏览器与夸克网盘的离线配置已设置；Edge 仍需在下载设置内选择，百度网盘与截图工具的独立设置需通过各自界面确认。

## 4. 环境与缓存入口

| 类别 | 主管理方式 / 当前实体位置 | 使用规则 |
| --- | --- | --- |
| Python | uv；环境基座下 `010_Python\uv` | 项目用 `uv run/sync/venv`；持久工具用 `uv tool`；临时工具用 `uvx`；保留项目必需的解释器版本，不再引入 pyenv |
| Node | nvm；`020_Node\nvm` 与 `current` | nvm 管 Node，npm/pnpm 按项目锁文件选择；不把包管理器和版本管理器当重复软件 |
| Java | `030_Java` 下的 JDK | JAVA_HOME 与 IDE/Gradle 所选 JDK 应一致或有明确项目例外 |
| Rust | `040_Rust\cargo`、`rustup` | CARGO_HOME / RUSTUP_HOME 指向此处；配置、工具、下载缓存由工具一起管理，不机械拆散 |
| Android / Flutter | `050_Mobile\Android`、`Flutter` | Android SDK 管组件；Flutter 自带 Dart，不另装重复全局 Dart |
| uv 缓存 | `E:\700_Cache\710_Packages\uv` | UV_CACHE_DIR |
| pnpm store | `E:\700_Cache\710_Packages\pnpm\store` | 用户 pnpm store-dir；版本内部可有 v10/v11，不能按目录版本号擅删 |
| pip 缓存 | `E:\700_Cache\710_Packages\pip\cache` | PIP_CACHE_DIR；不是项目依赖安装位置 |
| Gradle 用户根 | `E:\700_Cache\710_Packages\gradle` | GRADLE_USER_HOME；混有下载的 JDK 等内容，不整根视为垃圾 |
| Hugging Face | `E:\700_Cache\720_Models\huggingface` | HF_HOME；维护 blobs/refs/snapshots 的关系，不能只拷快照 |
| Playwright | `E:\700_Cache\730_Browsers\playwright` | PLAYWRIGHT_BROWSERS_PATH |
| Android AVD | `E:\800_System\830_Emulators\android-avd` | ANDROID_AVD_HOME；保护磁盘镜像、用户数据和快照 |

### 项目内构建与依赖

`.venv`、`node_modules`、`.gradle`、`target`、`build`、`dist`、`bin`、`obj` 默认由各项目维护，不强行搬至共享根，也不设所有项目共用的 CARGO_TARGET_DIR。一次性构建需要外置输出时，才在 `D:\900_Temp\920_Build` 下按项目/任务隔离。

## 5. 正式保留的例外

| 对象 | 处置与理由 |
| --- | --- |
| npm：`E:\700_Cache\npm-cache` | 唯一活动实体，用户 .npmrc 明确指向它；运行中的 npx/MCP 依赖此路径。保留稳定入口，不为层级外观强搬；以后维护时可再评估归入 710_Packages |
| Pub：`%LOCALAPPDATA%\Pub\Cache` | 保留默认。含全局 CLI、启动器、快照及绝对路径引用，不单改 PUB_CACHE |
| NuGet：`%USERPROFILE%\.nuget\packages`、`%LOCALAPPDATA%\NuGet\v3-cache` | 保留默认。全局包与 HTTP 缓存职责不同；不因补丁版本旧就删项目可能锁定的包 |
| ModelScope | 默认模型缓存目前无模型实体，无迁移收益；`.modelscope` 中的凭据留在用户目录，不混入共享缓存 |
| 应用自带运行时、Flutter SDK 内部缓存、Shorebird | 软件托管；不是可直接删除的重复全局环境 |
| Windows TEMP/TMP、系统/安装器/游戏平台目录 | 保留工具约定；不统一重定向，不为编号改权限或直接拖动安装数据 |
| 兼容 Junction | 只提供同一实体的旧路径入口。旧 C 盘 Rust/HF、旧包缓存入口及旧 E 盘缓存入口可保留；不要当作重复实体递归删除 |
| VS Build Tools | 实体已迁至 `D:\100_Work\110_Development\113_Software\VS\18\BuildTools`；共享组件在同级 `VS\Shared`，旧 `E:\100_Work\101_Program\VS\Shared` 保留为 Junction。今后通过官方安装器更新，不手工搬迁 |

**保留默认是正式结论，不是无限期待办。**只有收益明确、工具支持且能核对引用时才安排迁移。新应用不自动继承这些工具的配置，应优先用其官方设置选位置。

## 6. 属性与日常维护

| 属性 | 管理要求 |
| --- | --- |
| 重要数据 / 持久用户数据 | 先备份；数据库、聊天、虚拟机、模拟器通过对应工具迁移 |
| 路径敏感 / 软件托管 | 核对环境变量、配置、快捷方式与活动进程；使用官方维护方式 |
| 可再生缓存 | 确认来源和无唯一内容后清理；优先工具自身功能，允许重新下载 |
| 临时中转 | 定期分类；重要结果转正式位置后再删 |
| 低频归档 | 按业务/年份组织，不无意义地重复复制 |
| 恢复副本 | 记录来源、时间及恢复方法；敏感配置不上传公共仓库 |

- 新文件先按性质归类：业务资料随业务、学习产出随主题，不单凭扩展名分类。
- 每周整理下载入口，每月检查空间；保留合理余量，不设置未经确认的自动删除规则。
- 迁移前保存配置；核对内容后更新引用，再处理旧实体。遇到未知文件、占用或权限错误即停止对应项，不强停进程、不批量改权限。
- 用户环境变量更新后，现有应用可能仍持旧值；保存工作后重开应用，必要时注销登录。兼容链接用于过渡，不要提前删除。
- JDK 当前旧版 MSI 安装状态未正式重建。下次更新使用官方安装器，并核对 JAVA_HOME、IDE/Gradle 与项目兼容性；不承诺旧版原位升级/卸载必然成功。
- 历史 Pixel AVD 数据缺少根级设备登记；原数据保留，不自动注册或删除。需要启用时通过 Device Manager 核查。快照中的历史路径不做盲目全文替换。

执行历史和维护证据已移至 [本地配置归档](<E:/900_Backup/920_Config/EntropyCleanup/20261103/README-磁盘目录规划.md>)；日常使用以本文为准。本规范不是病毒检测报告，也不保证所有软件或历史项目没有自定义路径。
