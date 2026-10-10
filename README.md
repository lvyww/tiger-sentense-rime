# 虎整句 · tiger-sentense-rime

方案默认采用 `compact` 内存档，包含暂存后长句尾部回删缓存复用及纯暂存文字回删优化。可在 `tiger_sentence.custom.yaml` 的 `patch` 中设置 `"tiger_sentence/memory_profile": balanced` 切换为较大缓存档。

基于虎码（虎整句）码表的 Rime 独立整句输入方案：纯 Lua 变长整句解码，
可选本地 n-gram 语言模型排序，输入行为与 TigerClaw（虎爪）Windows 版对齐。
不依赖任何 Windows 组件，可在小狼毫（Weasel）、Linux ibus-rime/fcitx-rime 等
标准 Rime 前端使用。

## 特性

- 字母连续输入整句编码，空格上屏；变长编码 lattice + Beam 解码。
- 明文码表/字频/白名单（txt），可直接编辑或导入其它形码码表。
- 可选 Kneser-Ney n-gram 语言模型（默认 TCSKNM03 五阶分页格式，纯 Lua 直接读取）；
  无模型时自动降级为「码表名次 → 更少码表边 → 分数」排序。
- 完整码单字奖励与约 146.5 KiB 的紧凑词先验只参与已有搜索的排序，不扩 Beam、
  不进入自动上屏置信度，也不扩大 405.66 MB 语言模型。
- 概率型自动提前上屏；关闭纠错时还可空码自动上屏。支持暂存到编码区后手动提交。
- 自动选重最低码数（默认 3，0 禁用）：达到门槛的非首选单字可省略选重键参与组句。
- 标点由 `symbols.yaml` 直通上屏；数字后的句号自动输出半角小数点 `.`。

## 安装（小狼毫）

当前发行版本为 `1.6.20261010.1`。标准完整包包含运行 Lua、方案、明文词典及当前生产模型；
首次安装和保留个人配置的更新步骤见 [发行版安装说明](docs/RUNTIME_INSTALL.txt)。
完整包不另附源码仓库、Git 历史或开发工具。

1. 复制本方案全部文件到 Rime 用户目录（Windows 默认
   `%APPDATA%\Rime\`）：`tiger_sentence.schema.yaml`、`lua/`、三个
   `tiger_sentence.*.txt`、`tiger_sentence.supplement.txt`、
   `models/tiger_sentence.lexical.bin`、`symbols.yaml`，
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
4. （可选）把 `sentence-fivegram-mobile.bin` 放入用户目录 `models/`，
   见下节。词汇辅助文件也必须放在 `models/`，避免被部署清理移走。
5. 「重新部署」，然后切换到 虎整句。

## 手机同排邻键纠错（默认关闭）

方案菜单提供“按键纠错关／弱／中／强”四档，最终每个错键的惩罚分别为不纠错、8、6、4分。
选择保存在 `tiger_sentence.options.yaml`，跨会话恢复；首次默认关闭，不使用 `reset` 覆盖已有选择。
旧前端的 `tiger_sentence_key_correction` 二态按钮仍可用，开启映射到“中”（6分）；
需要保持早期8分积极度时请选择“弱”。档位说明见 [`docs/CORRECTION_LEVELS.md`](docs/CORRECTION_LEVELS.md)。

按标准 QWERTY 的三排字母处理，只尝试左右紧邻替换，例如 `w → q/e`，不处理跨排、
增删键、颠倒顺序、数字或标点。每段尚未确认的编码最多改两处；至少四个字母、
纠错后至少两个汉字才展示。纠错结果只标注单个 🐞，最多展示两个接近最佳分数的纠错项。
原编码即使已有候选也会尝试纠错，精确候选之间的顺序不被纠错通道改写。

**主线默认搜索档A已启用D89：单错分差8、双错分差9。** 两组分别与本组最优路径比较，
再受原有16／8条数量上限及每次输入的评分配额约束；长输入沿用原先的减半上限。
这是纠错搜索内部剪枝，不是弱／中／强的最终惩罚，不改正码Beam，也没有增加用户开关。
发布包直接使用这份默认参数，不再在打包时临时启用D89。实现与测试见
[`docs/D89_PRUNING.md`](docs/D89_PRUNING.md)。

原始编码和光标位置不会被重写。弱／中／强均禁用空码顶屏，避免 `ptu` 抢先提交“跃”，
使继续输入的 `ptue` 仍有机会纠为“是的”。概率型提前上屏保留原有安全规则，
纠错首选或搜索未完成时不自动提前上屏；空格、点选、标点和Tab手动确认仍可使用。
显式选重码段和已确认前缀不会被重新纠正；切档只刷新未确认候选，不能撤回已提交文字。
希望整段都等待确认时，可同时关闭“提前上屏”。所选候选含纠错路径（包括已确认前缀的纠错历史）时不写入自学习。
菜单中出现其它纠错候选，不会阻止正码候选的学习。明确点选或 Tab 确认正码并成功提交后，
学习记录保存实际输入编码与所选正码片段，通过分数参与解码；分数足够时可以超过纠错候选。
独立选择两个字时确认这两个字的组合，例如 `kzjuy → 淦掉`。以后在“去淦掉／他淦掉”等句子里
选择它，可以强化同一个已确认片段，并用于“没淦掉”等未选择过的前缀。
完整路径、编码边界、已确认前缀和片段歧义仍受检查；不会把纠错候选的改码保存为正码。
同一码表 Direct 候选保持名次顺序；Direct 与组句候选之间可以按普通学习分竞争。
旧 `fusion-v1|` 与 `exact-correction-v1|` 硬排序记录直接忽略，不占有效学习条数；
文件中的原始记录不删除，既有普通片段记录继续使用。关闭自学习停止读取与写入评分，重新启用后恢复。
自动上屏继续使用独立的模型证据和实际人工确认次数。详见 [可复用片段与纠错竞争](docs/EXACT_CORRECTION_LEARNING.md)。


需要当前五阶模型；缺失或读取失败时退回无模型输入。更新时请整体替换 `lua/` 和schema，
保留自己的配置、词库及学习数据。桌面回归不等于所有手机前端验收，也不保证任意长句的时延。

## 纠正学习与可读文件

`tiger_sentence/tab_learning` 默认开启。首次及后续每次人工改选并成功提交，都按当前分差增加 1～3 级，累计封顶 10；不是固定加三级。正常首选和自动提前上屏不强化，无时间衰减。

已有普通学习记录、用户补充语料中的片段可在后续改选时单独加强。片段可跨过共同边界形成的差异区间，
但必须与实际变化重叠，并且唯一最长匹配包含其它已确认匹配；存在歧义时沿用原始差异片段。
每段最多 16 个字、128 码，不越过已确认的编码边界，不改补充语料原始权重。

学习保存在用户目录的 `自学习-<schema_id>.txt`，默认 `自学习-tiger_sentence.txt`。UTF-8 中文列名直接显示片段、编码、前文、本次升级、UTC 时间；一条片段记录代表一次纠正。**不读取、不迁移旧版数据库。** LevelDb 只保留进程互斥锁，不再作为学习记录库。编辑前完整退出 Rime；字段无效时保留文件并停止学习写入，不静默覆盖。

完整行为、格式及验证边界见 [自适应学习说明](docs/ADAPTIVE_LEARNING.md)。宿主提交通知不代表目标应用确实插入文字。排序跳级与真实确认次数分开，首次 +3 不会被视为三次确认提高提前上屏置信度。

更新时整体替换 `lua/`（包括新增 `tiger_sentence_learning_text.lua`）和 schema，保留自己的配置、码表、补充语料；无需重新训练模型。

已修复 Lua 5.5 中对 `for` 控制变量赋值导致的
`attempt to assign to const variable 'line'` / `'r'` 加载错误，
以及由此引起的 processor `func type: nil`。无需修改码表或重新下载模型。
回归覆盖 Lua 5.5、Lua 5.4 和 LuaJIT，仍需各前端实机验收。

## 语言模型（可选）

默认模型为 `sentence-fivegram-mobile.bin`（TCSKNM03），放入用户目录 `models/`。
TCSKNM03 是纯 Lua 直接读取的字符五阶模型：Beam 每条路径保存最近四个字符历史，
BOS/EOS 都参与评分；同一文件同时提供孤立字先验需要的 observed-bigram 查询，
不再需要为了这一先验额外常驻旧三阶模型。格式、构建与分页缓存见
[`docs/TCSKNM03.md`](docs/TCSKNM03.md)。

当前默认模型为三源融合 TCSKNM03 Q8 五阶，405,663,171 字节（405.66 MB）。
Corpus4 50% / Articles 25% / Brightmart 非新闻 25%，按历史加权 KL 剪枝。
SHA256：`756f6c92cf43ad6e8e3087ce66b711ac6ad0fc41e6f3fb82b3766e35ecab8681`。
模型身份以 `default-model.json` 为准；更新源码不会自动更新公开 Release 附件。
请使用配套实验包或核对下载文件的哈希，不要把旧 Release 模型当作新版默认模型。

查找顺序：用户目录 `models/` → 用户目录根部 → 共享目录 `models/`。
仅加载 `sentence-fivegram-mobile.bin`，不再回退到旧三阶文件。

没有模型时方案完全可用：解码按码表名次优先，整码单字不会被多段拼接
压过；语言模型排序、紧凑排序先验与提前上屏的置信度计算一并禁用。

## 数据文件与自定义

码表等基础数据为明文 txt；随包词先验是可复现生成的紧凑只读文件：

| 文件 | 格式 | 作用 |
| --- | --- | --- |
| `tiger_sentence.codes.txt` | 每行 `字\t编码`，`#` 注释，兼容 CRLF/BOM | 码表；同码内行序即名次，编码仅小写字母（自动小写化） |
| `tiger_sentence.char_ranks.txt` | 每行一个字，行序=频序 | 常用字最优码过滤与生僻字孤立惩罚；缺失时两者禁用 |
| `tiger_sentence.full_code_whitelist.txt` | 白名单字符，每行一个或连排 | 白名单字保留完整编码参与组句 |
| `models/tiger_sentence.lexical.bin` | TCSLEX01 Bloom filter，150,032 字节 | 5 万个 2～4 字高频词的有界 Top-5 排序票；缺失时自动禁用 |

- schema 配置 `tiger_sentence/high_freq_limit`（默认 `1500`）：常用字
  （字频前 N）只保留最优码；`0` 全部放开；负数按 `0`。
  带方案的入口独立读取该方案配置，缺失、不可读或返回非数值时按默认 `1500`，
  不继承上一方案的值；内部无方案参数的解码/诊断调用只复用当前词库。
  相同有效限制不重建词库；`apply_high_freq_limit(nil)` 不修改限制或缓存。
- schema 配置 `tiger_sentence/auto_select_min_code_length`：**自动选重最低码数**，
  默认 `3`，整数范围 `0～128`，`0` 禁用自动选重。分段非首选单字的匹配编码
  至少达到此长度，才能在组句时省略选重键。只计算该词条的字母编码，
  不计算数字、`;`、`'` 后缀；首选、显式选重及整段完整匹配的候选菜单不受此门槛限制。
  非首选多字词仍须显式选重。新设置合并原“允许单字重码组句”开关；
  不再读取旧开关，修改方法见 [自动选重最低码数](docs/AUTO_SELECT_MIN_CODE_LENGTH.md)。
- schema 配置 `tiger_sentence/min_retained_raw_length`（默认 `0`）：
  自动上屏最少保留编码数，概率型提交仍永远不少于三键。
- 导入其它形码码表：直接替换 `tiger_sentence.codes.txt`（编码仅限拉丁
  字母，单字与多字词均可，行序=选重名次）；想全部保留非最优码时把
  `high_freq_limit` 设为 `0` 并清空白名单。
- `tiger_sentence.supplement.txt`：个人补充语料，每行 `词条 [权重]`，
  默认权重 1000；奖励 `clamp(9 + 2 * ln(weight / 1000), 0, 16)`。
- 内置排序先验：取消逐字主码的 `2 × 码长` 奖励。整个输入无显式选重、
  一次匹配一个单字时保留 `+5`；只有前 N 高频且不在白名单里的字才要求最优码，
  白名单和范围外单字可用码表已有的非最优码获得此奖励。N 沿用上面的用户设置，
  不改变码表的既有主码过滤。完整 4 码的孤立生僻字保护及 Top-5 词先验保持原有规则，
  这些排序奖励均不计入提前上屏概率。细节见
  [非最优码评分规则](docs/NONOPTIMAL_CODE_SCORING.md)；历史参数见
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
- `自动选重最低码数`（默认 `3`）：分段路径中的非首选单字在匹配编码达到
  门槛时按语言模型分数竞争，`0` 禁用；`提前上屏` 开关同时控制概率型提前上屏与空码自动上屏。

自动上屏按 `(文本前缀, raw 边界)` 独立
累计证据，置信阈值 `0.995`、强证据/边界封闭 `0.99999`；截断的候选池
绝不触发高置信空码上屏；提交通过一次原子输入赋值重建 composition，
避免候选窗闪烁。
空码自动上屏的唯一候选分支会额外检查完整码表路径，不把 Beam 裁剪后只剩
一个候选误认为真正唯一；同一文本的不同切分不算不同输出。

## 开发与测试

四档纠错下的精确候选学习回归复用生产 processor、提交通知和可读文件存储适配器：
`lua tools/test_sentence_learning.lua <源码目录> <含配套码表及models的临时数据目录>`。
该可选实模矩阵覆盖四档纠错下的点击、Tab、取消、反向选择、重复通知、重开和“淦掉”的跨前缀复用；
省略第二个目录仍运行核心回归。`tools/test_fragment_selection.lua` 单独覆盖片段提取、等级计划与旧记录忽略。
真实 librime 的强档提交与重启验证使用 `tools/test_rime_learning_integration.py --case fusion --correction strong --selection tap`
或 `--selection tab`，同时传入下文的探针、插件和模型参数。

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

“提前上屏”“提前上屏至编码”“按键纠错”记住最后选择，跨应用和重启后恢复；
已打开的其他会话在下一次输入前同步。菜单和手机 API 切换均适用。
偏好保存在用户目录 `tiger_sentence.options.yaml`，更新时保留，本仓库不分发个人偏好。
已有 `user.yaml` 中保存的这三个值可作为首次迁移来源。
首次默认值为开、关、关，配置在 `tiger_sentence/option_defaults/` 下，保存值优先。
这些 switch 不应配置 `reset`，否则新会话会强制恢复默认；升级时同时更新 Lua
和主 schema，并移除旧自定义补丁中针对这些开关的 `reset`。

锁定前缀使用增量缓存；学习只更新受影响的编码分区，墙钟时间不会触发学习重算。
码表初始化、置信度对象分配、暂存显示和模型页缓存也做了优化。

## 来源与许可

本方案是 TigerClaw（虎爪）输入法整句行为的独立 Rime 移植。
`models/tiger_sentence.lexical.bin` 派生自 rime-mohu 词库；来源、版本、转换与许可见
[词先验署名](docs/LEXICAL_PRIOR_ATTRIBUTION.md)和
[机器可读清单](docs/LEXICAL_PRIOR_MANIFEST.json)。
许可证见 [LICENSE](LICENSE)（GPL-3.0）。
