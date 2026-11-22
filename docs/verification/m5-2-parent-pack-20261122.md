# M5-2 父包叠层与内容钉定

## 离线加载

调用者通过 `parent_packs` 提供按 (pack_id, pack_version) 固定的目录映射。每个包独立校验 YAML、清单与本包文件，按父包到子包合并内容分区。同 ID 的条目整体替换，未列出的父包条目继承。校验器核对父包清单的身份与固定引用，拒绝环。FactType、实体槽位和 Resolver 的依赖在合并后的表上解析。

覆盖继承的 FactType 要保留 Owner、原语、identity 与 unknown 策略。可见性允许保留原声明或缩小 `learnable_by` 集合，其他条件须相同。当前选择用集合包含关系验证可判定的收窄，未引入跨 class 或更改传播模型的隐式比较。

`LoadedPack.resolved_packs` 按父到子返回不可变的 ID、版本、各包原始内容哈希。叠层摘要基于有序版本链。单包摘要沿用原序列化规则。可用 `expected_content_hash` 检测与旧钉定版本不一致的加载。使用 `load_credential_pack` 对比现有 Credential 包，改动前后均为 `8d3dadb80689276f5ada3a81189e9c1ffbfcb8c8a47452858b0111093c92975d`。

## 验证

代码在临时检出 `b73b17360fc1f30ad8c35102ce32826a22a085f1` 验证。Python 3.12.2，SQLite 3.43.1，`PYTHONPATH` 和 `app.__file__` 均落在 `F:/codex-temp/a-ip-f759a465/backend`。

- `python -m pytest -q -p no:cacheprovider backend/tests/test_rule_pack_validator.py -k "parent or overlay or overridden_entry"`，上线前 7 failed、69 deselected。输出 `F:/paralls-verification/thread-a/et-438d8ccefb/red.txt`。
- `python -m pytest -q -p no:cacheprovider` 运行 validator、Pool runtime、Credential pack schema boundary、reference chain、FactType registry 和 Credential rebuild 六个测试文件，`108 passed, 2 warnings`。输出 `F:/paralls-verification/thread-a/et-455e85951f/targeted.txt`。
- `compare_selection.py --repo <worktree> --selection <selection.json> --output <run>/<selection>`，五组冻结选集 1,169 个节点与八组登记选集 62 个节点合计 1,231。各组 `problems=0 improvements=0`，退出 0。输出 `F:/paralls-verification/thread-a/et-9987f71077`。

## 生产接线与单元 DoD

解析链落入存档、生产迁移 writer 与按迁移切点重放未做。现有 world config 钉定字段与版本链的绑定路径待裁定，见 [M5-3 前置审计](m5-3-pack-migration-preflight-20261122.md)。U4、U8 离线加载验证，U6 仅静态核对读写接口，U10 为本文件，U11 登记 8 个定向节点。U1、U2、U3、U5、U7 的域实现与 U9 声明探针未做。

工作分支代码提交 `4747acaf`。用于合并状态回归的工作分支包含本提交及命令目录切片。
