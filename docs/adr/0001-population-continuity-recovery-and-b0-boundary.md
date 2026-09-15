# 群体连续性恢复锚点与 B0 边界

状态：accepted

群体连续性以事件追加成功作为提交锚点；current state、checkpoint 和热状态都是可重建投影，使用独立的仿真时间游标与 source revision 表示恢复进度。B0 只产生客观连续状态的结构化增量、presentation seed 或 deferred result，Character Core 与 Domain Owner 的写入只能由更高层级的已授权意图触发。这样避免跨存储事务和认知边界被热路径绕过，同时允许对同构数值字段采用性能门禁后的混合数据导向布局。
