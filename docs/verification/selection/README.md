# 迁移单元选集登记

- 依据：迁移规格（文档仓库 `docs/superpowers/specs/2026-11-22-architecture-v2-migration-spec.md`）第五节 U11、成功标准 10。
- 目录约定：**一个迁移单元一个文件**，文件名 `<unit>.json`，例如 `life_state.json`、`action_consequence.json`。
- 归属：该单元的迁移线程拥有自己的文件，其他线程不得增删。单元后续被改动时由改它的线程更新。

## 为什么要有这个目录

`absorb-main-3bf3418e/` 下的五组选集（1,169 节点）冻结在吸收期，不覆盖迁移后新增的单元测试。没有本目录，迁移过的单元会逐次脱离回归覆盖，而合并门禁仍然显示"无新增失败"。

## 文件格式

与 `absorb-main-3bf3418e/*.json` 完全一致：

```json
{
  "head": "<登记时的提交 SHA>",
  "description": "<单元名>：<这组节点防的是什么回归>",
  "tests": [
    {"test_name": "tests/test_x.py::test_y", "outcome": "passed", "failures": []}
  ]
}
```

- `tests[].test_name` 必须是可被 pytest 直接接受、**在本仓库 cwd 为 `backend` 时也能解析**的节点 ID。
- `outcome` 写登记当时的实际结果。若为 `failed`，该节点必须先在 `claims/` 按 P-2 登记，否则合并门禁会把它当作新增失败来源。
- 节点必须唯一；重复会导致 `compare_selection.py` 直接退出（"selection must contain unique nodes"）。

## 登记什么

**能发现该单元回归的最小节点集**：

1. 该单元新增或修改的定向测试（正向、边界、失败各至少一例）；
2. 覆盖它依赖路径的既有测试（读取方、共享机制、事件 schema）。

不登记整个测试文件的全量，也不只挑一两个正例。

## 怎么跑

合并执行者按 `docs/v2-coordination/AUTONOMY.md` §三 G5 逐份运行：

```powershell
& '$python312' 'docs/verification/absorb-main-3bf3418e/compare_selection.py' `
    --selection 'docs/verification/selection/<unit>.json' `
    --output '<尚不存在的目录>/<unit>'
```

线程自测时同样可以跑自己那一份，用来在提交前确认没有把本单元弄坏。

## 增加文件时的检查

- [ ] 文件名是单元名，不是测试文件名
- [ ] `tests` 非空，节点唯一
- [ ] 至少包含一个能覆盖"本单元最容易被后续改动弄坏"的行为的测试
- [ ] 所有 `failed` 节点已在 `claims/` 登记
- [ ] 在本机跑过一次，`problems=0`
