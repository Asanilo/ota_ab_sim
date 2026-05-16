# AI 辅助开发记录

本文件用于手动记录本项目中使用 AI 的过程。

- 什么时候用了 AI。
- 给 AI 的提示词或任务是什么。
- AI 产出了什么内容。
- 哪些内容被人接受、修改或拒绝。
- 最后用什么命令或结果验证。

## 记录模板

### TURN-X

**工作内容**

- 本次在做什么：

**给 AI 的提示词 / 请求**

```text
在这里粘贴原始提示词，或用自己的话概括。
```

**AI 产出**

- 计划：
- 文档：
- 代码：
- 测试：

**人工判断和修改**

- 接受了什么：
- 修改了什么：
- 没有采用什么：

**验证方式**

```bash
# 在这里填写实际运行过的命令
```

验证结果：

- 是否通过：
- 备注：

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

### TURN-8 最终优化与 GitHub 推送前验证

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
