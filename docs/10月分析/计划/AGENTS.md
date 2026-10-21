# 十月分析计划目录规则

本目录只保存 implementation plan，状态统一为 `analysis/planned/non-authorizing`。计划必须引用 `../规格/` 中对应规格，按依赖顺序拆成可独立检查的任务，并列出文件责任、接口、测试、Harness 证据和回滚点。

命名规则：`NN-主题实施计划.md`，与规格目录保持一一对应或明确说明一对多关系。计划文件不得重新定义领域对象；发现冲突时回到规格目录修订。

角色计划必须先处理现有 `CharacterTurnContext`、MindFrame、memory、model gateway、L1/L2/L3/L4 和 skill service，再进入跨域领域适配。自走棋装备计划属于未来单局运行时的 deferred 归档，不进入当前开放世界执行顺序、active gate 或完成条件；重新启动时必须另立单局批次及其 owner、spec、plan 和验证证据。

计划若采用与原始分析设计不同的执行顺序、provider 路线、候选协议、场景载体或延期范围，必须引用 `../回写/README.md`，并确认对应原始设计文档已存在“本批规格与计划回写”小节。计划中的来源矩阵只能证明任务可追踪，不能证明偏离已经获得设计审阅或运行授权。
