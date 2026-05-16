# AI 辅助开发记录

本文件用于手动记录本项目中使用 AI 的过程。

- 什么时候用了 AI。
- 给 AI 的提示词或任务是什么。
- AI 产出了什么内容。
- 哪些内容被人接受、修改或拒绝。
- 最后用什么命令或结果验证。

## 最终总结

本项目由AI辅助开发。AI生成了候选方案、代码、评审结果和文档草稿。本人负责验收标准、架构约束、最终决策和验证。

最终验证：

- `python3 -m unittest discover -s tests -v`
- 结果：17 项测试通过。
- 测试内容：C/S HTTP CLI 路径、软件包暂存、MD5/SHA256 校验不匹配、非活动槽写入、重启成功、启动失败回滚、路径遍历拒绝以及客户端/服务器边界检查。

关键人工决策：

- 使用 Python 作为 24 小时模拟器，而非真正的嵌入式固件。
- 保持真实的 HTTP C/S 边界。
- 将下载视为本地软件包暂存。
- 避免使用 Docker、数据库、身份验证和前端框架。
- 使用只读的人工智能评审结果作为输入，但最终的接受/拒绝决策由人工做出。

## 开发记录

### TURN-1 初始规划

**工作内容**

- 建立 OTA A/B 模拟器项目的初始规划文档。
- 明确需求、C/S 边界、HTTP API、状态模型、测试点和演示流程。

**给 AI 的提示词 / 请求**

```text
You are helping me build a 24-hour assignment project.

Assignment:
Build a CLI or simple Web tool to simulate an OTA A/B partition upgrade flow.

Requirements:
1. Check current version.
2. Download new firmware from a local dummy firmware folder.
3. Verify MD5 and SHA256.
4. Simulate writing to partition A, reboot, and switch active slot.
5. If upgrade boot fails, automatically roll back to partition B.
6. Must clearly use AI-assisted development.
7. Must use C/S architecture: client CLI/Web separated from server.

Important assumptions:
- Use a real server process with HTTP APIs.
- The client must call the server through HTTP and must not directly modify state files.
- Treat "download" as staging/copying firmware from a local dummy firmware folder, not real network downloading.
- Assume the initial active slot is B and the target upgrade slot is A, to match the assignment wording.
- Keep the project simple enough to finish in 24 hours and demo in under 3 minutes.
- Do not add database, Docker, authentication, frontend framework, or unnecessary abstractions unless required.

Before writing code:
- Create AGENTS.md with project rules for Codex.
- Create SPEC.md with explicit acceptance criteria.
- Create ARCHITECTURE.md with server/client boundaries, API list, data model, and OTA state machine.
- Create TODO.md with implementation steps.
- Create AI_LOG.md template.
- Create demo_script.md with the intended recording flow.

Hidden evaluation risks to avoid:
- Do not create fake C/S separation: the client must only call HTTP APIs and must not directly read or write state files.
- Checksum verification must affect control flow. MD5/SHA256 failure must reject the upgrade and prevent writing to slot A.
- Rollback must update persistent state, not just print a message.
- Boot failure must be simulated during reboot, after slot A has been written and marked pending.
- The demo should clearly show initial active slot B, target slot A, and rollback to B.
- The local dummy firmware "download" should be implemented as staging/copying from a firmware repository folder.
- Every assignment requirement must be verifiable by a command, test, or status field.

Do not implement code yet.
```

**AI 产出**

- 计划：TODO
- 文档：SPEC、AGENT、demo_script、ARCHITECTURE、AI_LOG
- 代码：无
- 测试：无

**人工判断和修改**

- 接受初始 active slot 为 B、升级目标为 A。
- 删除SPEC.md对AI_LOG的要求。
- 审查修正SPEC.md 对任务的约束描述。

### TURN-2 最小可运行实现

**工作内容**

- 实现最小可运行 OTA A/B 模拟器。
- 服务端负责状态、固件 metadata、校验、写 A 槽、重启模拟和回滚。
- 客户端只通过 HTTP 调用服务端。
- 初始化 Git 仓库，用未提交文件记录本轮实现结果。

**给 AI 的提示词 / 请求**

```text
Read AGENTS.md, SPEC.md, ARCHITECTURE.md, and TODO.md.

Implement the smallest working version.

Requirements:
- Server owns OTA state, firmware metadata, checksum verification, slot switching, reboot simulation, and rollback.
- Client only calls server APIs and never mutates state files.
- Use local dummy firmware folders.
- Support MD5 and SHA256 verification.
- Include deterministic demo commands for:
  1. status check
  2. successful upgrade from B to A
  3. checksum failure
  4. boot failure and rollback to B
Add tests for status, checksum failure, successful upgrade, and failed boot rollback.
Update README.md with exact runnable commands.

After implementation, run the tests and show the results.

Implementation correctness requirements:
- Expose state through GET /status, including active_slot, current_version, slot versions, pending upgrade, and last_error.
- POST /upgrade must stage/copy firmware, calculate MD5 and SHA256 from actual file contents, compare them against firmware metadata, write slot A only if both checks pass, and mark A as pending boot.
- POST /reboot must simulate boot success or failure. On success, commit slot A as active. On failure, roll back to slot B and clear pending state.
- Tests must assert persistent state changes, not only response messages.
```

**AI 产出**

- 计划：按现有 TODO 收敛为最小实现。
- 文档：新增/更新 README.md、TODO.md、AI_LOG.md、`.gitignore`。
- 代码：新增 `ota_ab_sim/ota.py`、`ota_ab_sim/server.py`、`ota_ab_sim/client.py`。
- 测试：新增 `tests/test_ota_flow.py`。
- 测试数据：新增 `firmware_repo/firmware_v2.bin`、`firmware_repo/firmware_v2.bin.json`、`firmware_repo/firmware_bad_checksum.bin`、`firmware_repo/firmware_bad_checksum.bin.json`。

**人工判断和修改**

- 使用 Python 标准库实现，避免引入数据库、Docker、认证或前端框架。
- 使用 `unittest`，因为当前环境的 `pytest` 受本机插件版本冲突影响无法启动。
- 按当前实现要求使用 `POST /upgrade` 一次完成 staging、MD5/SHA256 校验、写入 A 槽和 pending 标记。
- 接受 `GET /status`、`GET /firmware`、`POST /upgrade`、`POST /reboot`、`POST /reset` 作为最小 API。
- 接受 `.gitignore` 忽略运行态 `data/` 和 Python 缓存文件。
- 人工执行了 `git init`，当前文件仍未提交，方便最后统一检查后提交。

**验证方式**

```bash
git status --short
python3 -m unittest discover -s tests -v
rg -n "state\.json|firmware_repo|staging|copyfile|shutil|Path\(|open\(" ota_ab_sim/client.py ota_ab_sim/server.py ota_ab_sim/ota.py tests/test_ota_flow.py
python3 -m ota_ab_sim.server --host 127.0.0.1 --port 8766
python3 -m ota_ab_sim.client --server http://127.0.0.1:8766 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8766 upgrade firmware_v2.bin
python3 -m ota_ab_sim.client --server http://127.0.0.1:8766 reboot --boot-ok
python3 -m ota_ab_sim.client --server http://127.0.0.1:8766 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8766 upgrade firmware_bad_checksum.bin
python3 -m ota_ab_sim.client --server http://127.0.0.1:8766 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8766 upgrade firmware_v2.bin
python3 -m ota_ab_sim.client --server http://127.0.0.1:8766 reboot --boot-fail
```

验证结果：

- `python3 -m unittest discover -s tests -v` 通过，4 个测试全部 OK。
- 覆盖初始 B 槽状态、checksum 失败阻断写 A、成功升级到 A、boot failure 后持久化回滚到 B。
- 静态搜索确认 `client.py` 不直接读取 `data/state.json`、不访问 `firmware_repo/`、不复制固件文件。
- 真实 HTTP server + CLI 路径验证通过：初始状态为 B/A，成功升级可切到 A，checksum 失败不写 A，boot failure 后回滚到 B。

### TURN-3 项目检查和文档同步

**工作内容**

- 检查最小实现后的项目状态。
- 将 AI 记录补充为更完整的中文记录。
- 同步 `SPEC.md`、`ARCHITECTURE.md`、`demo_script.md`，让文档与当前 `POST /upgrade` 实现一致。

**给 AI 的提示词 / 请求**

```text
这是这轮的操作帮我检查项目，并修改AI——LOG我创建了git init
```

**AI 产出**

- 计划：先检查 git 状态、关键文档、实现代码和测试，再修改 AI_LOG。
- 文档：更新 `AI_LOG.md` 的 TURN-2 记录；修正 `SPEC.md`、`ARCHITECTURE.md`、`demo_script.md` 中旧的 download/verify/write 分步描述。
- 代码：无。
- 测试：重新运行现有 `unittest`。

**人工判断和修改**

- 保留当前最小 API：`GET /status`、`GET /firmware`、`POST /upgrade`、`POST /reboot`、`POST /reset`。
- 接受 `POST /upgrade` 一次完成 server-side staging、checksum verification、slot A write 和 pending 标记。
- 继续保持 client 只通过 HTTP 调用 server。

**验证方式**

```bash
git status --short
python3 -m unittest discover -s tests -v
rg -n "state\.json|firmware_repo|staging|copyfile|shutil|Path\(|open\(" ota_ab_sim/client.py ota_ab_sim/server.py ota_ab_sim/ota.py tests/test_ota_flow.py
python3 -m ota_ab_sim.server --host 127.0.0.1 --port 8766
python3 -m ota_ab_sim.client --server http://127.0.0.1:8766 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8766 upgrade firmware_v2.bin
python3 -m ota_ab_sim.client --server http://127.0.0.1:8766 reboot --boot-ok
python3 -m ota_ab_sim.client --server http://127.0.0.1:8766 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8766 upgrade firmware_bad_checksum.bin
python3 -m ota_ab_sim.client --server http://127.0.0.1:8766 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8766 upgrade firmware_v2.bin
python3 -m ota_ab_sim.client --server http://127.0.0.1:8766 reboot --boot-fail
```

验证结果：

- `python3 -m unittest discover -s tests -v` 通过，4 个测试全部 OK。
- 真实 HTTP server + CLI 路径验证通过。
- 检查发现旧文档仍引用 `download`、`verify`、`write` 分步命令，已同步为当前 `upgrade` 命令。
- 当前 Git 状态显示项目文件均为未提交状态，符合刚执行 `git init` 后的状态。

### TURN-4 严格有效性检查草稿

**工作内容**

- 检查 checksum、rollback、boot failure 是否是真实状态变化，而不是只打印日志。
- 按严格清单验证 `status` 字段、持久化状态、失败路径和测试断言。

**给 AI 的提示词 / 请求**

```text
回答我
- 是否把 checksum、rollback、boot failure 写成真实状态变化，而不是只打印日志。
建议验证 status、successful upgrade、checksum failure、boot failure rollback、测试命令。
更严格检查 status 字段、checksum failure 后 A 不 pending、successful upgrade 后持久化 active_slot=A、
boot failure 必须发生在 reboot API 中、rollback 后持久化 active_slot=B/current_version/pending state、
测试必须断言状态字段。
把发现的问题记录到 AI_LOG.md 草稿里。
```

**AI 产出**

- 计划：运行单元测试和真实 HTTP server/client 流程，并读取 `data/state.json` 验证持久化状态。
- 文档：更新 `AI_LOG.md` 本草稿记录；同步 `SPEC.md`、`ARCHITECTURE.md`、`README.md`、`demo_script.md` 的 `slot_versions` 字段描述。
- 代码：补充 `OtaService.status()` 和 `_save_raw()`，让状态响应和持久化 JSON 都包含 `current_version`、`active_version`、`slot_versions`。
- 测试：补充 `tests/test_ota_flow.py`，断言 `slot_versions`，并断言 successful upgrade / rollback 后的持久化 `current_version` 和 pending state。

**发现的问题**

- 严格项缺口 1：`status` 原先有 `slots`，但没有显式 `slot_versions` 字段。
- 严格项缺口 2：`data/state.json` 原先持久化 `active_slot` 和 slot version，但没有直接持久化 `current_version`。

**人工判断和修改**

- 接受把 `slot_versions` 作为 evaluator-visible 状态字段，保留原有 `slots` 详细结构。
- 接受把 `current_version`、`active_version`、`slot_versions` 写入持久化 JSON，同时读取 status 时重新计算这些派生字段。
- 不改变核心 OTA 流程：checksum 失败仍停在 `verification_failed`，boot failure 仍只在 `POST /reboot` 中触发 rollback。

**验证方式**

```bash
python3 -m unittest tests.test_ota_flow.OtaFlowTests.test_status_starts_on_slot_b_with_target_slot_a -v
python3 -m unittest tests.test_ota_flow.OtaFlowTests.test_successful_upgrade_writes_slot_a_then_reboot_commits_a tests.test_ota_flow.OtaFlowTests.test_failed_boot_rolls_back_to_b_and_persists_state -v
python3 -m unittest discover -s tests -v
python3 -m ota_ab_sim.server --host 127.0.0.1 --port 8769
python3 -m ota_ab_sim.client --server http://127.0.0.1:8769 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8769 status
python3 -m ota_ab_sim.client --server http://127.0.0.1:8769 upgrade firmware_v2.bin
python3 -m ota_ab_sim.client --server http://127.0.0.1:8769 reboot --boot-ok
sed -n '1,240p' data/state.json
python3 -m ota_ab_sim.client --server http://127.0.0.1:8769 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8769 upgrade firmware_bad_checksum.bin
sed -n '1,220p' data/state.json
python3 -m ota_ab_sim.client --server http://127.0.0.1:8769 reset
python3 -m ota_ab_sim.client --server http://127.0.0.1:8769 upgrade firmware_v2.bin
python3 -m ota_ab_sim.client --server http://127.0.0.1:8769 reboot --boot-fail
sed -n '1,240p' data/state.json
```

验证结果：

- 单元测试通过：4 个测试全部 OK。
- `status` 输出包含 `active_slot`、`current_version`、`slot_versions`、`pending_upgrade`、`last_error`。
- successful upgrade 后，`data/state.json` 显示 `active_slot: A`、`current_version: 2.0.0`、`pending_upgrade: null`。
- checksum failure 后，`data/state.json` 显示 `ota_state: verification_failed`、`slots.A.boot_status: empty`、`slots.A.version: null`、`pending_upgrade: null`。
- boot failure 由 `reboot --boot-fail` 触发；rollback 后，`data/state.json` 显示 `active_slot: B`、`current_version: 1.0.0`、`pending_upgrade: null`、`slots.A.boot_status: failed`。

### TURN-5 只读严格审查记录

**工作内容**

- 使用严格只读 reviewer 角色检查实际实现、测试、README、AI_LOG 和 demo_script。
- 不修改代码，不执行破坏性命令。
- 记录 reviewer 发现的问题和建议修复项。

**给 AI 的提示词 / 请求**

```text
You are a strict read-only reviewer for this OTA A/B simulator assignment.

verify the actual implementation from code, tests, README, AI_LOG, and demo_script.

Do not modify files.
Do not run destructive commands.
Do not praise the project.

For each finding, include:
- requirement affected;
- evidence from file path;
- severity;
- concrete fix;
- command to verify if applicable.

Return:
1. Pass/fail table.
2. Critical issues.
3. Missing evidence.
4. Concrete fixes.
```

**AI 产出**

- 计划：只读检查项目文件、运行非破坏性测试、核对 client/server 边界和持久化状态。
- 文档：本条记录。
- 代码：无。
- 测试：运行现有 `unittest`，未新增测试。

**审查结论摘要**

- 查询当前版本：通过。
- 本地 dummy firmware staging：通过，但缺真实 HTTP 自动化测试证据。
- MD5/SHA256 校验：部分通过，现有测试只覆盖 MD5 失败，没有单独 SHA256 mismatch 测试。
- 写 A、重启、切换 active slot：通过，但自动化测试主要是 service-level。
- boot failure rollback 到 B：通过，但自动化测试主要是 service-level。
- AI 辅助开发记录：通过。
- C/S 架构：部分通过，client 实现使用 HTTP，但测试没有启动真实 server 或通过 CLI 验证。

**发现的问题**

- 高严重度：测试没有证明真实 C/S 架构。证据：`tests/test_ota_flow.py` 直接导入并调用 `OtaService`，没有启动 HTTP server，也没有 subprocess 调用 CLI。
- 中严重度：缺少 SHA256 mismatch 的独立测试。证据：测试 fixture 只有 `bad_md5` 参数，失败测试只断言 `MD5`。
- 中严重度：当前工作区存在运行态 `data/state.json`。证据：`data/state.json` 可能保存 rolled_back 或其他演示后的状态；虽然 `data/` 被 `.gitignore` 排除，但直接启动 server 时会复用已有 state 文件。

**建议修复**

- 新增 `tests/test_http_api.py`，用临时目录启动真实 server，通过 `python3 -m ota_ab_sim.client --server ...` 跑 reset/status/upgrade/reboot。
- 新增静态测试，断言 `client.py` 不包含 `OtaService`、`state.json`、`firmware_repo`、`shutil`、`Path(` 等 server-side 状态或文件访问痕迹。
- 新增 SHA256 失败固件或测试 fixture 参数 `bad_sha256=True`，断言 SHA256 mismatch 会进入 `verification_failed`，且 slot A 不写入、不 pending。
- 提交或打包前确认 `data/` 不进入版本控制；demo 第一条继续执行 `reset`。如果评测直接启动 server 后查初始状态，需要补充 clean-state 说明或调整初始化策略。

**验证方式**

```bash
python3 -m unittest discover -s tests -v
rg -n "OtaService|state\.json|firmware_repo|staging|copyfile|shutil|Path\(|open\(" ota_ab_sim/client.py tests
sed -n '1,120p' data/state.json
```

验证结果：

- 实际运行 `python3 -m unittest discover -s tests -v`，4 个测试全部 OK。
- reviewer 判断：现有测试通过，但 C/S 自动化证据、SHA256 独立失败证据仍不足。

**人工审查 / 处理意见**

- 接受高严重度问题：当前实现本身是 C/S，`client.py` 使用 `urllib.request.urlopen` 调 HTTP；但自动化测试只覆盖 `OtaService`，没有证明真实 server process + CLI client 的路径。因此 reviewer 对“C/S 证据不足”的判断成立。后续应优先补 `tests/test_http_api.py`，用临时目录启动 server，并用 subprocess 调 CLI 跑 reset/status/upgrade/reboot。
- 接受中严重度问题：MD5 和 SHA256 在实现中都会比较，但测试只有 bad MD5 用例，没有单独制造 SHA256 mismatch。因此 reviewer 对“SHA256 独立失败证据不足”的判断成立。后续应补 `bad_sha256` fixture 或 `firmware_bad_sha256.bin`。
- 部分接受 data/state 风险：`data/` 已在 `.gitignore` 中，不应进入提交；README 和 demo_script 也要求先 reset，所以正常演示路径可控。但如果评测直接启动 server 并读取已有工作区状态，脏 `data/state.json` 会影响初始状态判断。提交前应确认 `git status --short` 不包含 `data/`，演示前执行 reset；是否修改 server 初始化策略暂不决定。
- 不立即修改代码：本轮要求是“浏览项目、谈论建议、记录人工审查”，所以只更新 AI_LOG，不实现 reviewer 建议。
- 优先级排序：第一优先补真实 HTTP/CLI 自动化测试；第二优先补 SHA256 mismatch 测试；第三优先补 client 静态边界测试；最后处理 clean-state/交付说明。

### TURN-6 转交 Review 意见并修复实现

**工作内容**

- 人工将 TURN-5 的 reviewer 意见转发给代码编写 agent。
- 实现 reviewer 建议中的自动化证据补强。
- 补真实 HTTP server + CLI 子进程测试。
- 补 SHA256 mismatch 独立失败测试。
- 补 client/server 边界静态测试。

**给 AI 的提示词 / 请求**

```text
给代码编写 agent：

1. 真实 C/S 自动化测试证据不足。当前测试直接调用 OtaService，没有启动真实 HTTP server，也没有通过 CLI 调用。
2. SHA256 mismatch 没有独立失败用例。当前只覆盖 bad MD5。
3. data/state.json 是运行态目录风险。data/ 已被 .gitignore 排除，但提交/演示前要确认不会污染初始状态。

请根据这些意见补测试和必要文档，不改变项目边界：
- client 仍然只能通过 HTTP 调 server；
- server 仍然拥有状态、staging、checksum、slot write、reboot、rollback；
- 不引入数据库、Docker、认证或复杂前端。
```

**AI 产出**

- 测试：新增 `tests/test_http_api.py`。
- 测试：扩展 `tests/test_ota_flow.py`，新增 SHA256 mismatch 独立失败用例。
- 固件：新增 `firmware_repo/firmware_bad_sha256.bin`。
- 固件 metadata：新增 `firmware_repo/firmware_bad_sha256.bin.json`。
- 文档：更新 `README.md`、`TODO.md`、`AI_LOG.md`。
- 验证：补充真实 HTTP server + CLI subprocess 测试，补充 client 边界静态测试。

**人工判断和修改**

- 接受 C/S 自动化证据不足的问题，并要求用真实 HTTP server + CLI subprocess 覆盖。
- 接受 SHA256 独立测试不足的问题，并要求新增 bad SHA256 fixture。
- 接受 client/server 边界需要自动化证据，但要求静态检查避免误判 HTTP `urlopen()` 为文件 `open()`。
- 对 `data/` 风险采用交付控制：`data/` 继续由 `.gitignore` 排除，提交前确认工作区不包含运行态 state。
- 不改变 server 初始化策略，不引入额外基础设施。

**验证方式**

```bash
python3 -m unittest discover -s tests -v
rg -n "OtaService|state\.json|firmware_repo|staging|copyfile|shutil|Path\(" ota_ab_sim/client.py
find data -maxdepth 3 -type f -print
git status --short --ignored
```

验证结果：
- 7 个测试全部通过：

```text
Ran 7 tests in 0.734s
OK
```

- `tests/test_http_api.py` 覆盖真实 HTTP server + CLI subprocess 路径，并断言持久化 `state.json` 变为 `active_slot: A`。
- `tests/test_http_api.py` 静态检查 `client.py` 不包含 `OtaService`、`state.json`、`firmware_repo`、`staging`、`copyfile`、`shutil`、`Path(` 等 server-state 访问痕迹。
- `tests/test_ota_flow.py` 覆盖 SHA256 mismatch，断言 `ota_state: verification_failed`，且 slot A 不写入。
- `find data -maxdepth 3 -type f -print` 当前返回 `data` 不存在。
- `git status --short --ignored` 当前只显示 ignored `__pycache__/`，不显示 `data/`。

### TURN-7 嵌入式 OTA 语义增强

**工作内容**

- 增强最小模拟器的嵌入式 OTA A/B 工程语义。
- 增加真实 slot 文件写入、OTA event log、boot failure 语义字段和 firmware repo index。
- 更新 README，明确 Python 项目模拟 OTA 控制面和状态机，不是 bootloader 或 flash driver。
- 主 coder 完成改动后反馈：已补完，未提交。

**给 AI 的提示词 / 请求**

```text
1. 补真实 slot 文件写入
      - 当前写 A 主要是更新 metadata。
      - 请新增类似：
          - data/slots/A/firmware.bin
          - data/slots/B/firmware.bin
      - upgrade 校验通过后，把 staged firmware copy 到 data/slots/A/
        firmware.bin。
      - state 里记录：
          - slot file path
          - size
          - md5
          - sha256
      - 测试要求：
          - checksum failure 后，A slot 文件不存在或未改变。
          - successful upgrade 后，A slot 文件存在且 checksum 匹配。
  2. 补 OTA event log / steps
      - 当前 POST /upgrade 一次完成 stage、verify、write A，流程感偏弱。
      - 不一定要拆 API，但 status/response 里要能看到步骤，例如：
          - staged
          - verified
          - written_to_A
          - pending_reboot
          - boot_confirmed
          - rolled_back
      - 建议字段：events 或 last_steps。
      - 测试要求：
          - successful upgrade 包含 staged/verified/written_to_A。
          - boot failure 包含 reboot_started/boot_failed/rolled_back。
  3. 补 README 说明 Python 定位
      - 加一段明确说明：

     This project simulates the OTA control plane and A/B state machine.
     It does not implement a real bootloader or flash driver.
     A/B slots, firmware staging, checksum verification, boot result,
     and rollback are simulated with filesystem files and persistent
  JSON state.
      - 中文意思：这是 OTA 控制面和状态机模拟，不是设备端固件实现。

  建议处理

  4. 补 firmware_repo/index.json
      - 让 firmware repo 更像 OTA 仓库。
      - 示例字段：
          - version
```

**AI 产出**

- 代码：更新 `ota_ab_sim/ota.py`，把校验通过的 staged firmware 复制到 `data/slots/A/firmware.bin`，并记录 file path、size、md5、sha256。
- 代码：checksum 失败不会写 A slot 文件。
- 状态：state/response 增加 `events`，成功 upgrade 包含 `staged`、`verified`、`written_to_A`、`pending_reboot`；boot fail 包含 `reboot_started`、`boot_failed`、`rolled_back`。
- 状态：增加 `boot_attempts`、`max_boot_attempts`、`rollback_reason`、`boot_failed_at_reboot`。
- 测试：扩展 `tests/test_ota_flow.py` 和 `tests/test_http_api.py`，覆盖 slot 文件、events、boot rollback 语义、firmware index。
- 文档：更新 `README.md`，说明这是 OTA control plane / A/B state machine 模拟，不是 bootloader 或 flash driver。
- 数据：新增 `firmware_repo/index.json`。

**人工判断和修改**

- 保持单一 `POST /upgrade` API，不拆 stage/verify/write 三个 API；用 `events` 字段展示流程步骤。
- 保持标准库 Python 和文件系统模拟，不引入数据库、Docker、认证或前端框架。

**验证方式**

```bash
python3 -m unittest discover -s tests -v
git status --short --ignored
```

验证结果：

- 8 个测试全部通过：

```text
Ran 8 tests in 1.374s
OK
```

- 主 coder 报告 `git status --short --ignored` 当前显示：

```text
 M AI_LOG.md
 M README.md
 M ota_ab_sim/ota.py
 M tests/test_http_api.py
 M tests/test_ota_flow.py
?? firmware_repo/index.json
!! ota_ab_sim/__pycache__/
!! tests/__pycache__/
```

- 没有 `data/` 进入 git；只有 `__pycache__/` 被 ignored。
- `find data -maxdepth 3 -type f -print` 返回 `data` 不存在。
- 本轮改动未提交。

### TURN-8 优化与 GitHub 推送前验证

**工作内容**

- 创建并推送 GitHub 仓库：`https://github.com/Asanilo/ota_ab_sim`
- 更新 `ARCHITECTURE.md`，让架构文档与当前实现一致。
- 支持二次升级：成功 boot 到 `A` 后，下一次 `target_slot` 变为 `B`。
- 使用 `firmware_repo/index.json` 做固件白名单校验，未列入 index 的固件会被拒绝。

**最终实现 commit**

```text
16ba44b feat: support indexed OTA upgrades
```

**测试命令**

```bash
python3 -m unittest discover -s tests -v
```

**测试结果**

```text
Ran 10 tests in 1.431s
OK
```

**Git 状态命令**

```bash
git status --short --ignored
```

**Git 状态结果**

```text
!! ota_ab_sim/__pycache__/
!! tests/__pycache__/
```

说明：

- 没有未提交源码改动。
- `data/` 没有进入 git 状态。
- 只有 Python 缓存目录被 `.gitignore` 忽略。

### TURN-9 Package Directory OTA Refactor

**工作内容**

- 按 `ENGINEERING_ROADMAP.md` 做下一轮实现，控制范围为 package-directory OTA pipeline。
- 将固件输入从 flat firmware 文件迁移为 `firmware/<package_id>/manifest.json + firmware.bin`。
- 增加 step-by-step API/CLI：`stage`、`verify`、`install`。
- 保留 `POST /upgrade` 一键流程，内部执行 `stage -> verify -> install`。

**给 AI 的提示词 / 请求**

```text
按 ENGINEERING_ROADMAP.md 做下一轮实现，但控制范围：
1. firmware/<package_id>/manifest.json + firmware.bin 包目录结构。
2. staging 复制整个 package directory 到 data/staging/<package_id>/。
3. 校验必须读取 staged manifest 和 staged firmware.bin。
4. install/write 只写 inactive slot，写到 data/slots/<slot>/firmware.bin。
5. state 增加 pending_slot、slot status、staged_package；保留 pending_upgrade 兼容旧测试。
6. 保留 POST /upgrade 一键流程，内部按 stage -> read manifest -> verify -> write inactive slot -> pending boot 走。
7. 补 path traversal 测试，防止 package id 传 ../。
8. 更新 README、ARCHITECTURE、SPEC、demo_script、TODO、AI_LOG。
```

**AI 产出**

- 代码：更新 `ota_ab_sim/ota.py`，实现 package staging、staged manifest verification、inactive slot install、pending boot、rollback。
- API：更新 `ota_ab_sim/server.py`，新增 `/stage`、`/verify`、`/install`。
- CLI：更新 `ota_ab_sim/client.py`，新增 `stage`、`verify`、`install`。
- 固件：新增 `firmware/v2_success`、`firmware/v3_success`、`firmware/v2_bad_md5`、`firmware/v2_bad_sha256` 包目录。
- 清理：删除旧 `firmware_repo/` 平铺固件文件，避免两套仓库模型并存。
- 测试：重写 `tests/test_ota_flow.py` 和 `tests/test_http_api.py` 覆盖 package flow、path traversal、step-by-step CLI、one-shot CLI。
- 文档：更新 README、ARCHITECTURE、SPEC、demo_script、TODO、AI_LOG。

**人工判断和修改**

- 保持 Python 标准库实现。
- 不引入 Docker、数据库、认证、前端框架或真实 bootloader。
- 保留旧字段兼容：`pending_upgrade`、`staged_firmware`、slot `boot_status`、slot checksum aliases。

**验证方式**

```bash
python3 -m unittest discover -s tests -v
git status --short --ignored
```

验证结果：

- 13 个测试全部通过：

```text
Ran 13 tests in 2.291s
OK
```

- `git status --short --ignored` 显示本轮源码、文档、测试、`firmware/` 包目录新增和旧 `firmware_repo/` 文件删除；`data/` 不存在且未进入 git。

### TURN-9 Reviewer Roadmap 文档审查与记录

**工作内容**

- 人工向 reviewer 提出下一轮工程化建议：
  - 固件从“散文件 + json”升级为“固件包目录 + manifest”。
  - staging 复制整个包，而不是只复制 bin。
  - 状态字段更接近 OTA 状态机语言：`active_slot`、`pending_slot`、`rollback_slot`、slot status。
  - `upgrade` 内部流程明确展示 `stage -> read manifest -> verify -> write inactive slot -> pending boot`。
- reviewer 编写了 `ENGINEERING_ROADMAP.md`。
- 检查文档 diff，判断该 roadmap 是否覆盖上述建议。

**给 AI 的提示词 / 请求**

```text
给reviewer 提了以下内容：
- 固件应该从“散文件 + json”升级为“固件包目录 + manifest”。
- staging 应该复制整个包，而不是只复制 bin。
- 状态字段应该更接近 OTA 状态机语言：active_slot、pending_slot、rollback_slot、slot status。
- upgrade 内部流程应该明确展示：stage -> read manifest -> verify -> write inactive slot -> pending boot。

```

**AI 产出**

- 文档：检查 `README.md` diff，确认 README 指向 `ENGINEERING_ROADMAP.md`。
- 文档：检查新文件 `ENGINEERING_ROADMAP.md`，确认其覆盖 package directory、manifest schema、whole-package staging、`pending_slot`、slot `status`、bootloader-like state、step-by-step API 和测试要求。
- 判断：该 roadmap 是下一轮工程计划，不是当前实现；当前代码仍是 `firmware_repo/firmware_v2.bin + .json` 的平铺模型。

**人工判断和修改**

- 接受保留 `ENGINEERING_ROADMAP.md`，因为它系统覆盖 reviewer 的四条工程化建议。
- 明确 README 中 “For the next engineering pass” 的表述是准确的，避免把 roadmap 误说成已实现功能。
- 要求提交时必须包含 `ENGINEERING_ROADMAP.md`，否则 README 会指向不存在的文件。
- 后续给 coder 的范围建议：
  - 必做：package dir + manifest、staging whole package、verify staged payload、write inactive slot、`pending_slot`/slot `status`。
  - 可选：新增 `/stage`、`/verify`、`/install` 分步 API。
  - 保留：`POST /upgrade` 一键流程，避免 demo 复杂化。
- 注意目录命名迁移：roadmap 建议新目录为 `firmware/`，当前实现是 `firmware_repo/`；后续实现时不能混用导致 README、ARCHITECTURE 和测试不一致。

**验证方式**

```bash
git status --short
git diff --stat
git diff -- README.md SPEC.md ARCHITECTURE.md TODO.md demo_script.md AI_LOG.md
sed -n '1,260p' ENGINEERING_ROADMAP.md
sed -n '260,620p' ENGINEERING_ROADMAP.md
```

验证结果：

- 当前 diff 包含：

```text
 M AI_LOG.md
 M README.md
?? ENGINEERING_ROADMAP.md
```

- tracked diff 很小：README 新增 roadmap 链接；AI_LOG TURN-8 标题有轻微修改。
- `ENGINEERING_ROADMAP.md` 是新文件，内容覆盖下一轮 package-based OTA A/B refactor。
- 本轮准备提交这些文档改动。

### TURN-10 Final Package-Based OTA Verification

**工作内容**

- 检查最终提交后的 package-based OTA A/B simulator 完成度。
- 核对 GitHub remote、最新 commit、工作区状态、测试结果、代码实现和文档一致性。
- 回答最终交付前 reviewer 问题：当前是否覆盖 `ENGINEERING_ROADMAP.md` 的核心要求，是否还存在影响提交的缺口。

**给 AI 的提示词 / 请求**

```text
检查目前的项目，完成度如何？

已按 ENGINEERING_ROADMAP.md 完成并推送到 GitHub：
https://github.com/Asanilo/ota_ab_sim

最新提交：
39e90d5 feat: add package-based OTA flow

完成内容：
- firmware/<package_id>/manifest.json + firmware.bin 包目录结构。
- stage 复制整个 package directory 到 data/staging/<package_id>/。
- verify 读取 staged manifest 和 staged firmware.bin。
- install 只写 inactive slot 到 data/slots/<slot>/firmware.bin。
- state 增加 pending_slot、slot status、staged_package、bootloader，并保留兼容别名。
- 保留 POST /upgrade 一键流程，内部执行 stage -> verify -> install。
- 新增 POST /stage、POST /verify、POST /install 和 CLI stage/verify/install。
- 增加 package id path traversal 测试。
- 更新 README.md、ARCHITECTURE.md、SPEC.md、demo_script.md、TODO.md、AI_LOG.md。
- 删除旧 firmware_repo/ 平铺固件模型。

验证结果：
python3 -m unittest discover -s tests -v
Ran 13 tests in 2.318s
OK
```

**AI 产出**

- 审查结论：当前项目已经从基础流程模拟升级为 package directory + manifest + staging + inactive slot + boot/rollback state machine 的 OTA A/B simulator。
- 代码审查：确认 `ota_ab_sim/ota.py` 实现 package staging、manifest validation、staged payload checksum、inactive-slot install、one-shot upgrade、reboot commit 和 rollback。
- API/CLI 审查：确认 `server.py` 暴露 `/stage`、`/verify`、`/install`、`/upgrade`、`/reboot`、`/reset`；`client.py` 对应提供 `stage`、`verify`、`install`、`upgrade`、`reboot`、`reset`。
- 测试审查：确认测试覆盖 package staging、staged-file verification、MD5/SHA256 failure、path traversal rejection、inactive slot write、second upgrade writes inactive B、HTTP/CLI subprocess flow。
- 文档审查：确认 README、ARCHITECTURE、SPEC、demo_script 已描述 package-based OTA flow。
- 发现的文档清理项：`TODO.md` 前半部分仍记录 early flat `firmware_repo/` baseline；`AI_LOG.md` 需要追加最终验证记录；`demo_script.md` 可以更明确展示 C/S 架构边界。

**人工判断和修改**

- 接受保留 `TODO.md` 的历史阶段，但将 Phase 0-6 标注为 early baseline，明确 Phase 7 是最终 package-based OTA refactor。
- 接受追加本 TURN-10，记录最终 commit、测试结果、Git 状态、实现范围和文档清理。
- 接受增强 `demo_script.md`，增加 HTTP server proof、client/server static boundary proof、最终测试与 git status proof。
- 不再扩大实现范围，不引入数据库、Docker、前端框架、真实 bootloader 或真实 flash partition。

**验证方式**

```bash
git status --short --ignored
git log --oneline --decorate -8
python3 -m unittest discover -s tests -v
rg --files
nl -ba ota_ab_sim/ota.py
nl -ba tests/test_ota_flow.py
nl -ba tests/test_http_api.py
nl -ba README.md
nl -ba ARCHITECTURE.md
nl -ba SPEC.md
nl -ba demo_script.md
```

验证结果：

- 最新本地与 remote commit 一致：

```text
39e90d5 (HEAD -> master, origin/master) feat: add package-based OTA flow
```

- 测试通过：

```text
Ran 13 tests in 2.178s
OK
```

- `git status --short --ignored` 只显示 ignored Python cache directories：

```text
!! ota_ab_sim/__pycache__/
!! tests/__pycache__/
```

- reviewer 判断：当前实现满足笔试核心要求，并覆盖 package-based engineering roadmap 的主要验收项。

### TURN-11 CLI Human-Readable Output Roadmap

**工作内容**

- 审查当前 CLI 输出方式。
- 确认当前已有一键升级命令 `upgrade <package>`，但默认输出是完整 JSON，观感不够像常规 OTA CLI。
- 编写 `CLI_OUTPUT_ROADMAP.md`，作为交给 coder 的下一轮明确实现提示词。

**给 AI 的提示词 / 请求**

```text
检查是否有一键升级的指令吗？
一键升级成功和失败是否会有提示吗？
CLI 的提示能做得美观一点吗？
把这次 JSON 输出修改写成提示词，我会交给 coder，然后记录此次 LOG。
```

**AI 产出**

- 判断：当前已经有一键升级命令：

```bash
python3 -m ota_ab_sim.client --server http://127.0.0.1:8000 upgrade v2_success
```

- 判断：当前一键升级成功/失败会通过 JSON 字段体现，但默认 CLI 没有人类可读摘要。
- 文档：新增 `CLI_OUTPUT_ROADMAP.md`，要求：
  - 默认输出改为简洁的人类可读文本。
  - 增加全局 `--json` 参数，保留完整 JSON 输出给测试和验收。
  - `upgrade v2_success` 成功时输出 staged、verified、installed、wrote slot、next step。
  - `upgrade v2_bad_md5` 失败时输出错误原因和 `slot write : blocked`。
  - `reboot --boot-ok` 和 `reboot --boot-fail` 有明确成功/回滚提示。
  - 更新测试覆盖 JSON 模式和默认人类可读模式。

**人工判断和修改**

- 接受保留 `POST /upgrade` 和 CLI `upgrade <package>` 作为一键升级入口。
- 接受默认输出面向录屏和使用者，完整 JSON 改为通过 `--json` 显式请求。
- 明确 client 仍然只能打印 server 返回的信息，不能为了格式化输出去读取 `firmware/`、`data/staging/`、`data/slots/` 或 `data/state.json`。
- 本轮只写 coder roadmap，不修改 CLI 实现代码。

**验证方式**

```bash
sed -n '1,240p' ota_ab_sim/client.py
rg -n "upgrade|--json|print_json|stage|verify|install" README.md demo_script.md SPEC.md TODO.md AI_LOG.md ota_ab_sim/client.py tests
git status --short
```

验证结果：

- 当前 `client.py` 已支持 `upgrade <package>`、`stage`、`verify`、`install`、`reboot`。
- 当前 `client.py` 仍默认调用 `print_json(payload)` 输出完整 JSON。
- `CLI_OUTPUT_ROADMAP.md` 已创建，包含输出示例、实现建议、测试要求和验收清单。

### TURN-12 CLI Default Human Output

**工作内容**

- 按 `CLI_OUTPUT_ROADMAP.md` 实现 CLI 默认人类可读输出。
- 增加全局 `--json`，保留完整 JSON 输出给测试和验收。
- 默认输出增加 ANSI 色彩提示，不引入第三方库。

**给 AI 的提示词 / 请求**

```text
CLI_OUTPUT_ROADMAP.md 实现CLI默认输出，CLI提示带上色彩。
```

**AI 产出**

- 代码：更新 `ota_ab_sim/client.py`，增加 formatter、`--json`、默认彩色摘要输出。
- 测试：更新 `tests/test_http_api.py`，JSON 模式显式传 `--json`，新增默认输出文本和彩色提示断言。
- 文档：更新 `README.md` 和 `demo_script.md`，说明默认输出和 `--json`。

**人工判断和修改**

- 保持 client 只调用 HTTP API，不读取 server-owned 文件。
- 使用 ANSI escape code 实现颜色，不引入 terminal color library。
- 默认输出面向录屏；`--json` 面向脚本化验证。

**验证方式**

```bash
python3 -m unittest discover -s tests -v
git status --short --ignored
```

验证结果：

- 17 个测试全部通过：

```text
Ran 17 tests in 5.192s
OK
```
