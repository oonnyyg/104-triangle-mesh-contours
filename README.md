# Triangle Mesh Contours

从带标量值的二维三角网格中提取等值线（marching triangles），仅依赖 Python 3.12+
标准库。输出可复现：三角形顺序、朝向改变都不会改变结果。

## 输入格式

JSON 文件包含三个字段：

- `vertices`：非空数组。每个顶点可以是
  - 数组形式 `[x, y, value]`，其标识即数组下标；或
  - 对象形式 `{"id": ..., "x": ..., "y": ..., "value": ...}`。
  所有 `x`、`y`、`value` 必须是有限数值；`id` 不可重复且类型一致、可比较。
- `triangles`：非空数组，每项为 3 个顶点标识。校验规则：
  - 引用的顶点必须存在；
  - 三个顶点互不相同且不共线（拒绝零面积三角形）；
  - 同一三角形（忽略顶点顺序）不得重复；
  - 任意一条边最多被两个三角形共用，否则报错；
  - 可假定非相邻三角形互不相交。
- `levels`：等值线高度数值数组（可为空）。

等值线高度限制：

- 高度等于任意顶点标量值时拒绝处理，该高度返回空结果（避免等值线穿过顶点的歧义）；
- 高度落在数据最小/最大值范围之外（含端点）时返回空结果。

## 算法与规范化

- 对每个三角形，在严格跨越高度的边上做线性插值得到穿越点，每个三角形产生 0 或 2 个穿越点并连成线段。
- 穿越点节点以**共享边的顶点标识**（排序后的顶点 id 对）为键拼接，不使用坐标近似相等合并。
- 边界上的等值线是开放折线；内部等值线是闭环。各独立分支分别输出，共享节点不重复。
- 开放折线从坐标较小的端点开始（逐坐标字典序比较）。
- 闭环不重复首点；从最小坐标点开始，并在两个方向中选择坐标序列字典序较小者。
- 同一高度的多条等值线按坐标序列排序；高度按数值升序输出。

## 输出格式

### JSON 汇总（`--json`）

```json
{
  "level_count": 1,
  "levels": [
    {
      "level": 2.0,
      "contour_count": 1,
      "total_length": 1.4142135623730951,
      "contours": [
        {
          "closed": false,
          "points": [[0.0, 1.0], [1.0, 0.0]],
          "length": 1.4142135623730951
        }
      ]
    }
  ]
}
```

- `points` 为 `[x, y]` 坐标序列；闭环不包含重复的首点。
- `length` 为等值线总长度；闭环长度包含首尾闭合段。空结果仍保留
  `{"level_count": ..., "levels": [...]}` 结构，`contours` 为空数组。

### CSV 明细（`--csv`）

每个等值线坐标点一行，列为
`level, contour_index, closed, point_index, x, y, segment_length, total_length`。
`segment_length` 是该点到下一点（闭环末点回到首点）的边长；开放折线的末点该列为空。
空结果仅输出表头行。

## 命令行用法

```sh
python -m contours sample_input.json
python -m contours input.json --json summary.json --csv detail.csv
python -m contours input.json --json - --csv -
```

最后一例将 JSON 打到 stdout 且不写 CSV。默认在输入文件旁生成
`<input>.contours.json` 与 `<input>.contours.csv`。
输入校验失败时进程返回非零状态并向 stderr 输出原因。

## 作为库使用

```python
from contours import read_mesh, extract_contours
from contours.report import to_json, to_csv

with open("sample_input.json", encoding="utf-8") as f:
    mesh, levels = read_mesh(f)
result = extract_contours(mesh, levels)
print(to_json(result))
print(to_csv(result))
```

## 测试

```sh
python -m unittest discover -s tests -v
```

测试覆盖单三角形插值、跨共享边拼接、三角形重排/朝向不变性、闭环方向规范化、
独立分支排序及各类输入校验。
