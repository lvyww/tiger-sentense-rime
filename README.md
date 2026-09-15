# 虎整句 · tiger-sentense-rime

基于虎码（虎整句）码表的 Rime 独立整句输入方案：纯 Lua 变长整句解码，
可选本地 n-gram 语言模型排序，输入行为与 TigerClaw（虎爪）Windows 版对齐。
不依赖任何 Windows 组件，可在小狼毫（Weasel）、Linux ibus-rime/fcitx-rime 等
标准 Rime 前端使用。

## 特性

- 字母连续输入整句编码，空格上屏；变长编码 lattice + Beam 解码。
- 明文码表/字频/白名单（txt），可直接编辑或导入其它形码码表。
- 可选 Kneser-Ney n-gram 语言模型（TCSKNM02 分页格式，Lua 直接读取）；
  无模型时自动降级为「码表名次 → 更少码表边 → 分数」排序。
- 形码证据与约 146.5 KiB 的紧凑词先验只重排现有候选，不扩 Beam、
  不进入自动上屏置信度，也不扩大 214 MiB 语言模型。
- 概率型自动提前上屏与空码自动上屏；可选择先暂存在编码区，最后一次性提交。
- 允许单字重码组句（可开关）：分段路径中的非首选单字按语言模型分数竞争。
- 标点由 `symbols.yaml` 直通上屏；数字后的句号自动输出半角小数点 `.`。

## 安装（小狼毫）

1. 复制本方案全部文件到 Rime 用户目录（Windows 默认
   `%APPDATA%\Rime\`）：`tiger_sentence.schema.yaml`、`lua/`、三个
   `tiger_sentence.*.txt`、`tiger_sentence.supplement.txt`、
   `tiger_sentence.lexical.bin`、`symbols.yaml`，
   以及内部配置 `tiger_sentence_ascii.schema.yaml`（不加入 schema_list）。
2. 在已有的 `rime.lua` 中合并注册（若没有则直接复制本包的 `rime.lua`）：

   ```lua
   local tiger = require("tiger_sentence")
   tiger_sentence_processor = tiger.processor_component
   tiger_sentence_translator = tiger.translator
   tiger_sentence_ascii = tiger.ascii_component
   tiger_sentence_buffer_filter = tiger.buffer_filter
   ```

3. 在已有的 `default.custom.yaml` 的 schema_list 中加入 `tiger_sentence`
   （本包附带示例）。
4. （可选）把 `sentence-ngram-mobile.bin` 放入用户目录 `models/`，
   见下节。
5. 「重新部署」，然后切换到 虎整句。

## 纠正学习与兼容性

`tiger_sentence/tab_learning` 默认开启，覆盖 Tab 纠正和直接点选非首选候选。
学习相对当前首选改变的片段，首选点击不反复强化，每次提交只消费一次。
键盘手动选重也使用同一提交通知。学习影响的候选不会作为自动提前上屏的依据。
每次纠正相当于补充语料权重 1000，首次奖励 9 分，两次约 10.386 分，
上限 16 分；累计权重按 30 天半衰期衰减，竞争选择会降低旧偏好。
现有记录按相同规则重建，无需清空学习数据。

学习需要宿主提供 LevelDb，数据按方案保存在用户目录的
`tiger_sentence_learning_<散列>.userdb`。接口缺失或数据库不可用时，正常输入仍可使用。
关闭设置会保留学习数据；备份或移走数据库前请退出 Rime。
宿主提交通知不能证明目标应用实际插入文字。

更新时请整体替换本方案的 `lua/` 模块，包括 `tiger_sentence.lua`、
`tiger_sentence_learning.lua`、`tiger_sentence_ngram.lua`、
`tiger_sentence_cache.lua` 和 `tiger_sentence_lexical.lua`，
并同时更新主 schema、内部 ASCII schema，以及上面的四个 Lua 注册项。
合并现有配置，保留自己的码表和学习数据库。

已修复 Lua 5.5 中对 `for` 控制变量赋值导致的
`attempt to assign to const variable 'line'` / `'r'` 加载错误，
以及由此引起的 processor `func type: nil`。无需修改码表或重新下载模型。
回归覆盖 Lua 5.5、Lua 5.4 和 LuaJIT，仍需各前端实机验收。

## 语言模型（可选）

模型文件 `sentence-ngram-mobile.bin`（TCSKNM02，约 214 MiB）从本仓库
[Releases](https://github.com/lvyww/tiger-sentense-rime/releases) 下载，放入用户目录 `models/`。查找顺序：用户目录 `models/` →
用户目录根部 → 共享目录 `models/`。

没有模型时方案完全可用：解码按码表名次优先，整码单字不会被多段拼接
压过；语言模型排序、紧凑排序先验与提前上屏的置信度计算一并禁用。

## 数据文件与自定义

码表等基础数据为明文 txt；随包词先验是可复现生成的紧凑只读文件：

| 文件 | 格式 | 作用 |
| --- | --- | --- |
| `tiger_sentence.codes.txt` | 每行 `字\t编码`，`#` 注释，兼容 CRLF/BOM | 码表；同码内行序即名次，编码仅小写字母（自动小写化） |
| `tiger_sentence.char_ranks.txt` | 每行一个字，行序=频序 | 常用字最优码过滤与生僻字孤立惩罚；缺失时两者禁用 |
| `tiger_sentence.full_code_whitelist.txt` | 白名单字符，每行一个或连排 | 白名单字保留完整编码参与组句 |
| `tiger_sentence.lexical.bin` | TCSLEX01 Bloom filter，150,032 字节 | 5 万个 2～4 字高频词的有界 Top-5 排序票；缺失时自动禁用 |

- schema 配置 `tiger_sentence/high_freq_limit`（默认 `1500`）：常用字
  （字频前 N）只保留最优码；`0` 全部放开；负数按 `0`。
  带方案的入口独立读取该方案配置，缺失、不可读或返回非数值时按默认 `1500`，
  不继承上一方案的值；内部无方案参数的解码/诊断调用只复用当前词库。
  相同有效限制不重建词库；`apply_high_freq_limit(nil)` 不修改限制或缓存。
- schema 配置 `tiger_sentence/min_retained_raw_length`（默认 `0`）：
  自动上屏最少保留编码数，概率型提交仍永远不少于三键。
- 导入其它形码码表：直接替换 `tiger_sentence.codes.txt`（编码仅限拉丁
  字母，单字与多字词均可，行序=选重名次）；想全部保留非最优码时把
  `high_freq_limit` 设为 `0` 并清空白名单。
- `tiger_sentence.supplement.txt`：个人补充语料，每行 `词条 [权重]`，
  默认权重 1000；奖励 `clamp(9 + 2 * ln(weight / 1000), 0, 16)`。
- 内置排序先验：正常的逐字主码按覆盖编码长度提供形码证据；只有完整 4 码
  才能免除该字的孤立生僻惩罚。词先验仅对语言模型已经生成的 Top-5 做
  非重叠词覆盖重排。三者均不计入提前上屏概率；参数选择与复现见
  [紧凑排序先验记录](docs/RANKING_PRIORS.md)。
- `symbols.yaml`：标点映射，标量/`commit` 直接上屏，数组映射显示候选。

## 输入行为

- 字母连续输入整句编码；空格提交候选，回车提交原始编码，Esc 清空。
- 有编码时 `;` `'` 数字分别选择码表第 2、3、N 项（`0` 为第 10 项）；
  无编码时由 `symbols.yaml` 输出中文标点。
- 无编码时数字直接上屏（全角开关输出 ０-９，小键盘同）；其后紧邻的
  句号自动输出半角小数点（包括全角数字后），其它标点不受影响。
- Up/Down 或 Tab/Shift+Tab 遍历候选；Tab/Shift+Tab 循环高亮，不立即上屏。
  Tab 高亮后继续输入字母，会锁定该候选的文本和编码边界，后续组句不再跨越
  这个边界重新切分。开启提前上屏时，此次确认立即提交尚未上屏的选中文字；
  关闭时，退格到未提交的锁定边界会解除锁定。Up/Down 本身不触发锁定，
  数字、`;`、`'` 仍用于当前码段选重。
- 一码段只在整段输入只有一码时合法；只有整个输入由单一码表边消费时
  才隐式显示全部名次；非首选多字词在任何切分路径中必须显式选重。
- `允许单字重码组句` 开关（默认开）：分段路径中的非首选单字按语言模型
  分数竞争；`提前上屏` 开关同时控制概率型提前上屏与空码自动上屏。

自动上屏按 `(文本前缀, raw 边界)` 独立
累计证据，置信阈值 `0.995`、强证据/边界封闭 `0.99999`；截断的候选池
绝不触发高置信空码上屏；提交通过一次原子输入赋值重建 composition，
避免候选窗闪烁。
空码自动上屏的唯一候选分支会额外检查完整码表路径，不把 Beam 裁剪后只剩
一个候选误认为真正唯一；同一文本的不同切分不算不同输出。

## 开发与测试

性能优化保留现有 Beam 和原评分规则，测量条件见 [性能记录](tools/RIME_PERFORMANCE.md)。
本次等价缓存优化、长码修复及独立差分验收见 [审查改进记录](docs/REVIEW_OPTIMIZATIONS.md)。
紧凑排序先验的差异集消融、包体与边界见 [排序先验记录](docs/RANKING_PRIORS.md)。
真实 librime 工具覆盖暂存/回删/标点（`tools/test_rime_preedit_integration.py`）、
点选/Tab/重启学习（`tools/test_rime_learning_integration.py`）和多会话/进程重启/
偏好迁移（`tools/test_rime_options_integration.py`）。编译对应 C++ 探针后以
`--exe <探针> --plugin <librime-lua.so>` 运行；模型测试另传 `--model` 或
`--production-model`。它们只使用临时目录，不代替前端实机验收。

```bash
# 无模型全量测试（Lua 5.3+；LuaJIT 亦可）
lua tools/test_tiger_sentence_incremental.lua .

# 真实模型全量测试（模型需在查找路径中）
lua tools/test_tiger_sentence_incremental.lua . --require-model

# 解码性能基准
lua tools/bench_tiger_sentence_lua.lua . --mode mobile --repeat 3

# 全套隔离回归；同样使用 Lua 5.5 和 LuaJIT 运行
python3 tools/run_regressions.py --lua lua --negative-control

# 学习索引 CPU 基准，不读写真实学习数据库
lua tools/bench_rime_learning.lua lua 10
```

诊断：Lua 模块导出 `data_status()`（码表/字频/白名单加载状态）与
`performance_status()`（解码耗时、缺页、缓存命中）。

## 提前上屏至编码与开关记忆

同时开启“提前上屏”和“提前上屏至编码”（后者默认关），提前确认的文字暂存在
预编辑区，候选只显示尚未确认的后缀。空格或点选合并整段后提交到应用。
退格先删除剩余编码，到边界后逐字删除暂存文字，不恢复原编码；只剩暂存文字时
隐藏候选列表，继续输入后恢复。逗号等标点先提交整段，再按标点配置处理。
回车提交暂存文字和剩余编码；Esc、取消和切换方案取消暂存。
学习等待最终宿主提交。中途关闭选项不会丢失已暂存文字。

“提前上屏”“单字重码组句”“提前上屏至编码”记住最后选择，跨应用和重启后恢复；
已打开的其他会话在下一次输入前同步。菜单和手机 API 切换均适用。
偏好保存在用户目录 `tiger_sentence.options.yaml`，更新时保留，本仓库不分发个人偏好。
已有 `user.yaml` 中保存的这三个值可作为首次迁移来源。
首次默认值为开、开、关，配置在 `tiger_sentence/option_defaults/` 下，保存值优先。
这三个 switch 不应配置 `reset`，否则新会话会强制恢复默认；升级时同时更新 Lua
和主 schema，并移除旧自定义补丁中针对这三个开关的 `reset`。

锁定前缀使用增量缓存；学习只更新受影响的编码分区，时间衰减按查询需要计算。
码表初始化、置信度对象分配、暂存显示和模型页缓存也做了优化。

## 来源与许可

本方案是 TigerClaw（虎爪）输入法整句行为的独立 Rime 移植。
`tiger_sentence.lexical.bin` 派生自 rime-mohu 词库；来源、版本、转换与许可见
[词先验署名](docs/LEXICAL_PRIOR_ATTRIBUTION.md)和
[机器可读清单](docs/LEXICAL_PRIOR_MANIFEST.json)。
许可证见 [LICENSE](LICENSE)（GPL-3.0）。
