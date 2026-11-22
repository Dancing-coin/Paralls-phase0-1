# M5-1 命令目录离线加载

代码提交 `eebd34e5`，在临时检出 `36b41f08` 验证，迁入后以 `git diff --exit-code 36b41f08 eebd34e5 -- backend packs` 确认内容相同。

`load_pack` 接收可信调用方提供的 Owner ID → domain 映射。规则包可声明规范命令名、一个已登记处理 Owner、版本、payload schema 引用、授权要求及四种幂等键形状。YAML 无权增加 Owner domain，历史 `Credential` 条目也不用于注册命令。父包叠层保留原 handler，拒绝取消继承的授权要求。生产请求入口和 payload schema 的解析尚未接入。

Python 3.12.2，SQLite 3.43.1。临时检出 `PYTHONPATH=F:/codex-temp/a-ip-f759a465/backend`，`app.__file__` 已核验在该目录内。

- `python -m pytest -q -p no:cacheprovider backend/tests/test_rule_pack_validator.py -k "command_catalog or own_command_domain"`，接入前 13 failed、77 deselected。输出 `F:/paralls-verification/thread-a/et-dae8d13b02/red.txt`。
- `python -m pytest -q -p no:cacheprovider` 覆盖 validator、Pool runtime、Credential pack schema boundary、reference chain、FactType registry 和 Credential rebuild，接入后 122 passed、2 warnings。输出 `F:/paralls-verification/thread-a/et-54fc3052ee/targeted.txt`。
- `compare_selection.py --repo <worktree> --selection <selection.json> --output <run>/<selection>`。14 组选集共 1,245 个节点，每组 `problems=0 improvements=0`，退出 0。包含本切片新增 14 节点。输出 `F:/paralls-verification/thread-a/et-2d5924a677`。

U4、U8 离线加载验证，U6 静态核对入口，U10 为本文件，U11 已登记。U1、U2、U3、U5、U7 的域级工作与 U9 声明探针未做。

父包与命令目录合并状态全量待采集。
