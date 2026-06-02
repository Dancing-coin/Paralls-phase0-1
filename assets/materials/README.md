# Materials Asset Slot

把通用材质、贴图和 shader 资源放在这里。

建议目录结构：

```text
assets/materials/
  characters/
  environment/
  props/
```

如果你导入的 `.glb` 已经内嵌材质，也可以先不拆。

只有在这些情况建议独立管理材质：
- 多个模型复用同一套材质
- 你想统一调色
- 你想在 Godot 内部重做 PBR
