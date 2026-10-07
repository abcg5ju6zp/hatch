# 环境重建失败时保留最后可用环境

> **Workspace:** /Users/ding/Documents/swe/0910061/project-10

---

**User**

切换 Hatch 环境矩阵或更新环境变量时，新环境创建可能先删除旧环境目录，随后解释器发现、依赖安装或命令启动失败，项目失去最后可用的运行环境。请在隔离目录完成解释器、插件、依赖和脚本检查，全部成功后才替换活动环境；创建失败、取消、并行重建和进程中止都保留上一环境，重启后识别并清理未完成目录。环境变量、矩阵选择、shell 命令和已存在环境的复用规则继续保持原有行为。

**Assistant**

toolName: view_folder

status: success

/Users/ding/Documents/swe/0910061/project-10

这是 Hatch 代码库。让我先了解虚拟环境创建的核心代码。

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/env/virtual.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py

现在查看环境接口中环境准备的流程：

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/env/plugin/interface.py

现在查看项目核心中环境准备的生命周期：

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/project/core.py

让我查找环境变量/矩阵变化导致环境重建的逻辑：

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/cli/application.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/project/env.py

toolName: search_by_regex

status: success

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/utils.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/utils/fs.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/env/system.py

toolName: file_search

status: success

toolName: search_by_regex

status: success

toolName: Shell

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/venv/test_core.py

让我查看 env 相关 CLI 命令的行为：

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/cli/env/create.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/cli/env/remove.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/cli/env/prune.py

toolName: search_by_regex

status: success

toolName: search_by_regex

status: success

toolName: search_by_regex

status: success

toolName: search_by_regex

status: success

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/env/internal/build.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/conftest.py

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/cli/shell/__init__.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/cli/env/test_create.py

让我实证测试一下虚拟环境目录移动后的行为（shebang 是否硬编码路径），这决定了安全的原子替换方案：

toolName: Shell

status: success

toolName: Shell

status: success

让我查看 KEEP_ENV 的语义和文档说明：

toolName: search_by_regex

status: success

让我确认 `build_virtual_env` 的使用情况以及 `abort` 的异常类型：

toolName: search_by_regex

status: success

toolName: search_by_regex

status: success

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/cli/application.py

toolName: search_by_regex

status: success

现在我对问题和代码结构有了完整理解。创建任务清单并查看剩余关键文件：

toolName: todo_write

status: success

Todos updated: 7 items

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/project/core.py

开始实现。首先在 [core.py](file:///Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py) 中加入原子化环境创建原语：

toolName: Write

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py

changes: undefined

现在在环境接口中添加默认钩子。先更新导入：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/env/plugin/interface.py

changes: undefined

在接口的生命周期区域添加两个钩子：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/env/plugin/interface.py

changes: undefined

在 [virtual.py](file:///Users/ding/Documents/swe/0910061/project-10/src/hatch/env/virtual.py) 插件中覆写这两个钩子：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/env/virtual.py

changes: undefined

现在重构 [core.py](file:///Users/ding/Documents/swe/0910061/project-10/src/hatch/project/core.py) 的环境准备流程：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/project/core.py

changes: undefined

检查 project/core.py 中 `Generator` 和 `contextmanager` 是否仍被使用：

toolName: search_by_regex

status: success

两者仍被使用。现在更新 `hatch env create` 命令，使崩溃残留的半成品环境能被识别重建，而不是误报"already exists"：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/cli/env/create.py

changes: undefined

修正事务成功提交时的操作顺序——先移除 marker 再删备份，消除崩溃窗口导致恢复出损坏环境的可能：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py

changes: undefined

让我检查现有测试中对创建失败后环境是否保留的断言，避免破坏既有约定：

toolName: search_by_regex

status: success

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/env/plugin/interface.py

changes: undefined

核心实现完成。查看现有接口测试的脚手架以便复用：

toolName: todo_write

status: success

Todos updated: 7 items

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/env/plugin/test_interface.py

现在为 venv 核心原语编写单元测试。先确认 Project 如何关联 app：

toolName: search_by_regex

status: success

现在编写 venv 核心测试：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/venv/test_core.py

changes: undefined

在测试文件末尾追加原子事务与恢复的测试：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/venv/test_core.py

changes: undefined

现在检查 Terminal.status 的行为，确保测试中可直接调用：

toolName: search_by_regex

status: success

为 `prepare_environment` 的事务行为添加项目层测试：

toolName: Shell

status: success

toolName: Shell

status: success

运行 venv 核心测试：

toolName: todo_write

status: success

Todos updated: 7 items

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/hatch.toml

用 uv 建立一个测试用虚拟环境：

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

`remove()` 需要能删除备份目录而不仅是文件：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py

changes: undefined

toolName: Shell

status: success

venv 测试全部通过。运行接口层测试：

toolName: Shell

status: success

测试中的 Application 未初始化 data_dir，在辅助函数中补上：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/env/plugin/test_interface.py

changes: undefined

toolName: Shell

status: success

修正测试桩行为，使其更贴近真实生命周期：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/env/plugin/test_interface.py

changes: undefined

toolName: Shell

status: success

单元层通过。现在查看 CLI 集成测试中关于安装命令失败的既有模式：

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/cli/env/test_create.py

先验证网络与基线：运行一个现有的 CLI 集成测试（含真实环境创建）：

toolName: Shell

status: success

toolName: Shell

status: success

基线很快（uv 缓存已预热）。查看 `hatch run` 测试的调用方式：

toolName: search_by_regex

status: success

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/cli/run/__init__.py

现在添加三个 CLI 端到端测试。先看 test_create.py 已有的辅助 import：

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/cli/env/test_create.py

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/cli/env/test_create.py

现在在 test_create.py 末尾追加三个端到端测试：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/cli/env/test_create.py

changes: undefined

toolName: Shell

status: success

运行新增的端到端测试：

toolName: Shell

status: success

三个端到端测试全部通过。运行更广范围的相关测试：

toolName: Shell

status: success

锁文件污染了环境存储目录的列举。按惯例将锁文件放到系统临时目录（以目标路径哈希命名），marker/backup 仍留在环境旁边：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py

changes: undefined

重新运行受影响的测试集：

toolName: Shell

status: success

`recover_incomplete` 在没有任何残留时不应创建目录（不兼容环境场景会检测空状态）：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py

changes: undefined

toolName: Shell

status: success

toolName: Shell

status: success

先确认这两个失败在改动前是否就存在（环境基线问题）：

toolName: Shell

status: success

该失败在改动前的基线上同样存在（本机没有 `python` 命令，属环境问题）。找出另一个失败：

toolName: Shell

status: success

toolName: Shell

status: success

`test_uv_env` 是我的回归。查看具体输出差异：

toolName: Shell

status: success

需要实际观察递归准备 hatch-uv 环境的行为。手动复现：

toolName: Shell

status: success

手动复现输出正确，怀疑是测试顺序导致的状态问题。查看 `is_default_environment`：

toolName: search_by_regex

status: success

单独运行该测试（带我的改动）：

toolName: Shell

status: success

需要理解 BorrowedStatus 的渲染条件：

toolName: search_by_regex

status: success

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/cli/terminal.py

对比基线代码的实际输出顺序（editable 安装，stash 即可切换）：

toolName: Shell

status: success

toolName: Shell

status: success

toolName: search_by_regex

status: success

toolName: Shell

status: success

找到原因：`expose_uv()` 不应提前到事务入口（改变了递归创建 hatch-uv 环境的状态嵌套顺序）。底层事务本身不需要 uv，移除该包裹：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/env/virtual.py

changes: undefined

toolName: Shell

status: success

只剩基线环境问题。继续运行其他依赖 prepare 流程的测试集：

toolName: Shell

status: success

toolName: Shell

status: success

同样疑似本机环境问题（无 `python` 命令）。验证基线：

toolName: Shell

status: success

两个均为基线既有的环境问题。运行剩余全部 CLI 测试：

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

publish 的 22 个错误是临时测试环境缺少 `pytest-xdist`（`worker_id` fixture），与改动无关。装上后复跑：

toolName: Shell

status: success

publish 测试在无 Docker 时正常 skip。现在做静态检查：

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

修正：布尔参数改为 keyword-only，if/else 块改为三元表达式：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/env/plugin/interface.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/env/virtual.py

changes: undefined

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/ruff.toml

toolName: Shell

status: success

将工件路径属性公开为正式 API（恢复工具的合理组成部分），测试不再访问私有成员：

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py

changes: undefined

toolName: Shell

status: success

更新测试文件，改用公开属性并直接写 marker 模拟崩溃现场：

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

toolName: Shell

status: success

按代码库约定修正测试风格。先改 test_core.py：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/venv/test_core.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/venv/test_core.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/venv/test_core.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/venv/test_core.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/env/plugin/test_interface.py

changes: undefined

toolName: Shell

status: success

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/venv/test_core.py

changes: undefined

toolName: Shell

status: success

`pytest.raises` 块内只能有一条语句，用嵌套函数封装失败动作：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/venv/test_core.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/venv/test_core.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/venv/test_core.py

changes: undefined

toolName: Shell

status: success

ruff lint 通过。再检查格式：

toolName: Shell

status: success

toolName: Shell

status: success

格式与 lint 全部通过。重新运行所有相关测试确认最终状态：

toolName: Shell

status: success

查看最终的 venv/core.py 完整代码做一次审查：

toolName: view_files

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py

发现锁重入计数在嵌套释放时有缺陷（set 被提前清空）。改为深度计数字典，并补全类型标注：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py

changes: undefined

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py

changes: undefined

补充重入测试验证锁最终释放，然后复跑：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/tests/venv/test_core.py

changes: undefined

toolName: Shell

status: success

venv/core.py 没有 future annotations，Generator 需运行时导入：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py

changes: undefined

toolName: Shell

status: success

外层锁释放处还需改为 pop：

toolName: edit_file_search_replace

status: success

filePath: /Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py

changes: undefined

toolName: Shell

status: success

29 个 venv 测试通过。运行 mypy 类型检查（CI 有此门禁）：

toolName: Shell

status: success

toolName: Shell

status: success

类型检查全部通过。完整审查最终 diff：

toolName: Shell

status: success

toolName: Shell

status: success

确认文档中没有引用已移除的 `managed_environment`：

toolName: search_by_regex

status: success

无残留引用。做一次完整的手动端到端验证（创建、复用、崩溃恢复、并行）：

toolName: Shell

status: success

存储目录干净、复用正常。模拟进程被强杀后的两种崩溃现场，验证重启恢复：

toolName: Shell

status: success

两种崩溃恢复均正常。再验证并行重建的安全性（两个进程同时创建同一环境）：

toolName: Shell

status: success

第二轮验证环境确实可用（输出只有一次创建，说明第二个进程等待锁后复用了结果）。确认环境目录完整：

toolName: Shell

status: success

toolName: Shell

status: success

目录名 `e2e-app` 是 default 环境的标准命名。验证其可用性：

toolName: Shell

status: success

并行场景完美：一个进程构建，另一个等锁后复用，无残留。最终回归一次：

toolName: todo_write

status: success

Todos updated: 7 items

toolName: Shell

status: success

toolName: Shell

status: success

toolName: todo_write

status: success

Todos updated: 7 items

toolName: Shell

status: success

已完成 Hatch 环境的原子化创建/替换改造，所有相关测试（341+）、ruff、mypy 均通过。

## 核心设计

由于 venv 内的脚本 shebang、`pyvenv.cfg` 等**硬编码绝对路径**，环境目录无法整体搬迁（实测移动后 `pip` 立即 `bad interpreter`），因此采用"**原地构建 + 旧环境停车备份 + 失败回滚 + 重启恢复**"方案：

- 构建始终发生在最终路径，旧环境先原子重命名为同级 `.{env}.backup`
- `.{env}.creating` marker 标记构建中；跨进程文件锁（POSIX `flock` / Windows `msvcrt`，放在系统临时目录避免污染环境存储列举）串行化并行重建
- 任一步失败（含 Ctrl-C 的 `KeyboardInterrupt`、命令失败的 `SystemExit`）→ 删除半成品并恢复备份；`HATCH_KEEP_ENV` 时保留半成品供排查
- 进程被强杀后，下次运行依据 marker/backup 状态机恢复：有备份则恢复上一可用环境，无备份则清除半成品；全成功时先删 marker 再删备份，杜绝恢复出半删备份的窗口

## 代码改动

- [venv/core.py](file:///Users/ding/Documents/swe/0910061/project-10/src/hatch/venv/core.py)：新增可重入跨进程锁 `locked_file`、`is_proper()`（pyvenv.cfg + 解释器检测）、`recover_interrupted()` 状态恢复、`creation_transaction()` 事务（含 `replace_existing`/`keep_env`），`remove()` 同步清理工件
- [interface.py](file:///Users/ding/Documents/swe/0910061/project-10/src/hatch/env/plugin/interface.py#L871-L895)：新增 `recover_incomplete()`（默认空操作）和 `creation_transaction()`（默认保持历史失败删除语义），第三方环境插件零影响
- [virtual.py](file:///Users/ding/Documents/swe/0910061/project-10/src/hatch/env/virtual.py#L165-L171)：virtual 插件覆写两个钩子，委托给底层事务
- [core.py](file:///Users/ding/Documents/swe/0910061/project-10/src/hatch/project/core.py#L184-L253)：`prepare_environment` 重构为"恢复 → 事务内完成创建、pre/post 脚本、项目安装、首次依赖同步"，锁等待后二次检查存在性（并行构建则直接复用）；删除原 `managed_environment`，提取 `synchronize_dependencies`
- [create.py](file:///Users/ding/Documents/swe/0910061/project-10/src/hatch/cli/env/create.py#L28)：`hatch env create` 在存在性判断前先恢复中断现场，避免半成品被误报为 "already exists"

## 行为保持

环境变量、矩阵选择（独立目录天然不受影响）、shell 命令、**已存在环境复用规则**（完整环境直接跳过，不做重建）、既有环境的就地依赖同步均与原行为一致；锁等待后发现其他进程已构建完成时直接复用。

## 验证

- 新增 20+ 单元测试（事务成功/失败回滚/备份恢复/keep_env/Ctrl-C/恢复状态机/锁重入）与 3 个 CLI 端到端测试（失败不留残、重启恢复旧环境、重启清理半成品）
- 手动验证：三轮双进程并行创建仅构建一次且环境可用；模拟强杀后的替换中断/全新创建中断，重启均正确恢复或清理
- 唯一未通过的 `test_new_selected_python` 等 3 个用例在改动前基线上同样失败，原因是本机 PATH 无 `python` 命令，与本次改动无关
