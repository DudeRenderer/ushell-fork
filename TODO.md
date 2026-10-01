# TODO：Windows 依赖本地优先重构

## 目标与已确认约定

- Windows 首次启动能够使用仓库内依赖完成初始化，默认禁止下载。
- 依赖解析顺序：有效安装缓存 → 仓库内匹配版本的包 → 显式允许的网络下载。
- 仅设置 `USHELL_ALLOW_DOWNLOADS=1` 时允许联网补齐依赖。
- 从本机 `%LOCALAPPDATA%\ushell\.working` 的已有缓存整理依赖进仓库。
- 覆盖 cmd、PowerShell 和 Windows 下的 Bash 启动入口；Linux/macOS 的安装策略不变。
- 在 `ushell-local` 分支实施，推送至 `origin/ushell-local`，保留已有 README 和架构文档改动。
- 以下复选框记录待实施工作；本文件本身不表示重构已完成。

## Git workflow

- Complete each coherent implementation step, run its relevant checks, and create a separate commit.
- Push each step's commit to `origin/ushell-local` immediately after committing; do not batch all pushes at the end.
- Update the corresponding TODO checkboxes and document relevant verification results in the same step's commit.
- Write every commit subject, body, and footer in English and follow [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).
- Use the format `<type>[optional scope][!]: <description>`, with a blank line before any body or footer.
- Choose a type that matches the change, such as `feat`, `fix`, `refactor`, `docs`, `test`, or `build`.
- Mark breaking changes with `!` or an English `BREAKING CHANGE:` footer; document the opt-in requirement when Windows dependency downloads become disabled by default.
- Verify that each push succeeds before starting the next implementation step.

## 1. 整理仓库依赖包

- [x] 新建 `dependencies/windows-x64/`，按依赖分别保存 ZIP，使用普通 Git 文件分发。
- [x] 从现有缓存整理 Python 3.14.3。
- [x] 从现有缓存整理 Clink 1.0.0a6。
- [x] 从现有缓存整理 fd 10.3.0。
- [x] 从现有缓存整理 fzf 0.56.3。
- [x] 从现有缓存整理 ripgrep 14.1.1。
- [x] 从现有缓存整理 vswhere 3.1.7。
- [x] 包含 Python 标准库、DLL、现有 Pip 模块、工具配套文件及许可证。
- [x] 保留 embedded Python 必需的标准库 `.pyc`；排除生成的 `__pycache__`、运行日志、工具安装 manifest 和含机器路径的 Pip 启动器。
- [x] 提供可重复执行的打包脚本，显式接收缓存根目录。
- [x] 生成版本化 JSON 清单，记录包名、版本、平台、文件名、SHA-256 和必需运行文件。
- [x] 在清单中注明来源为已安装缓存；为打包快照重新计算校验值，不复用上游压缩包的校验值。

Validation: All six archive and per-file SHA-256 checks passed; a second packaging run produced identical ZIP hashes.

## 2. 改造 Windows Python 启动准备

- [x] 保留 `provision.bat` 入口，使用 Windows PowerShell 辅助脚本读取依赖清单、校验和展开本地 Python 包。
- [x] 确保首次初始化不依赖预先安装的 Python。
- [x] 校验已有 Python 安装的版本和必需运行文件，通过后复用。
- [x] 本地部署不运行 `get-pip.py` 或在线 Pip 安装。
- [x] 缺少可用缓存及本地包时，默认报错并说明缺失依赖、搜索路径和下载开关。
- [x] 显式允许下载时，保留现有固定 Python 版本及校验逻辑作为网络后备。
- [x] 先在临时目录完成校验、解包和运行检查，成功后发布安装并写入成功标记。

Validation: Four Windows provisioning tests passed: offline missing package, corrupt archive without fallback, wrong version, and fresh install/cache reuse/DLL repair in Unicode paths.

## 3. 改造工具解析、安装与缓存

- [ ] 在 `bootstrap.py` 接入本地包来源，沿用现有工具安装目录、命令声明和 shim 生成方式。
- [ ] 按工具名、版本和平台匹配依赖，不使用其他版本或任意 PATH 程序替代。
- [ ] 仅处理当前平台启用的 bundle，并完整部署 Clink DLL 等配套文件。
- [ ] 校验旧工具缓存的版本和必需文件，通过后复用；损坏缓存可从仓库修复。
- [ ] 在临时目录中完成本地包校验、解包和必需文件检查，成功后发布缓存。
- [ ] 对缺包、损坏、版本不匹配和解包失败提供明确错误；损坏的本地包不静默转为下载。
- [ ] 安装失败不留下成功标记或残缺命令清单，不提前破坏可用安装。
- [ ] 更新 bootstrap 失效标记，避免旧主 manifest 绕过新检查。
- [ ] 后续启动能够识别依赖文件丢失，并重新进入本地修复流程。

## 4. 统一联网控制与 Windows 入口行为

- [ ] Windows 依赖下载统一遵守 `USHELL_ALLOW_DOWNLOADS=1` 开关，默认不发起下载。
- [ ] 遗留 Channel Pip 安装和工具下载诊断入口遵守同一开关。
- [ ] 保持 P4、构建产物下载等业务命令的联网行为不受此依赖策略影响。
- [ ] 修正相关 Windows 入口的路径引用，支持仓库目录和工作目录包含空格、中文。
- [ ] 修正 cmd、PowerShell 和 Windows Bash 的错误码传播，确保离线缺包和初始化失败能传回调用方。
- [ ] 确保共用代码的 Windows 分支改动不改变 Linux/macOS 的依赖安装策略。

## 5. 更新文档与分发行为

- [ ] 更新 README，说明默认离线、本地包目录、依赖更新流程和下载开关用法。
- [ ] 更新架构文档中的 Windows provisioning、工具获取、缓存及失败行为描述。
- [ ] 更新相关第三方依赖说明，使其反映仓库已包含本地依赖包。
- [ ] 确保 gather 分发包含依赖包、JSON 清单和许可证。

## 6. 测试与验收

- [ ] 使用标准库 `unittest` 验证来源优先级及版本、平台匹配。
- [ ] 验证缺包、SHA-256 错误、安装中断、必需文件缺失和缓存修复行为。
- [ ] 验证默认禁止下载时，依赖网络入口不会被调用。
- [ ] 通过受控下载替身验证 `USHELL_ALLOW_DOWNLOADS=1` 的网络后备分支。
- [ ] 检查所有依赖包的清单、校验值、许可证及必需运行文件。
- [ ] 验证打包后的 Python 标准库及项目现有原生扩展可以加载。
- [ ] 在独立、空的 `flow_working_dir` 中，通过 cmd 完成离线初始化，不使用用户原有安装缓存。
- [ ] 在独立、空的 `flow_working_dir` 中，通过 PowerShell 完成离线初始化，不使用用户原有安装缓存。
- [ ] 验证 `.help`、命令补全查询及工具版本。
- [ ] 再次启动，确认复用有效缓存。
- [ ] 删除测试缓存中的工具文件，确认可从仓库恢复。
- [ ] 覆盖仓库路径和工作目录包含空格、中文的情况。
- [ ] 验证缺包或损坏时返回非零退出码，且不会产生成功安装标记或残缺命令清单。
- [ ] 检查非 Windows 分支仍保持原有安装策略。
- [ ] 有可用 Windows Bash 环境时执行启动烟测；否则明确记录验证限制。
- [ ] 验证 gather 后的分发目录仍包含离线启动所需资源。
- [ ] 执行 `git diff --check`，检查最终改动范围并记录验收结果。
