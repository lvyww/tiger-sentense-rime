# 紧凑词先验：来源与署名

`tiger_sentence.lexical.bin` 是一个不可逆的 Bloom filter，派生自
[`fcxxxz/rime-mohu`](https://github.com/fcxxxz/rime-mohu) 的
`mohu_flypy.base.dict.yaml`：

- 上游版本：`9f43098cefdb450fe8dec0f3069fe8d9999b9d10`
- 原文件 SHA-256：`877c6dacb4d5bb6738e230ce2d9235f3ac0f48404959c2db26fb18c7ddd31cb6`
- 原文件声明许可：CC BY 4.0
- 作者/贡献者：rime-mohu contributors
- 原文件列明的数据来源：Rime 八股文词库、THUOCL（依其原许可再发行）、
  雾凇拼音词库补充数据及人工补充词
- 原项目说明：完整方案按 GPL-3.0 发布；文件另有声明时以文件声明为准
- 许可文本：[Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/)

本项目所作变更：只保留虎整句码表可编码的 2～4 字条目，按上游权重、词长和
Unicode 顺序稳定排序，选取前 50,000 条；随后丢弃词文本和权重，仅发布
1,200,000 bit、10 次散列的 TCSLEX01 Bloom filter。其估算假阳性率约为
`2.11e-5`。该转换不表示上游作者认可本项目。

精确参数、输入/输出摘要见 [`LEXICAL_PRIOR_MANIFEST.json`](LEXICAL_PRIOR_MANIFEST.json)。
在取得上述上游版本后，可从仓库根目录复现：

```sh
python3 tools/build_lexical_prior.py \
  --source /path/to/rime-mohu/mohu_flypy.base.dict.yaml \
  --source-repository https://github.com/fcxxxz/rime-mohu \
  --source-revision 9f43098cefdb450fe8dec0f3069fe8d9999b9d10 \
  --source-license CC-BY-4.0 \
  --codes tiger_sentence.codes.txt \
  --output tiger_sentence.lexical.bin \
  --manifest docs/LEXICAL_PRIOR_MANIFEST.json
```
