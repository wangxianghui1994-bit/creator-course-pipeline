# Creator Course Pipeline（课程创作流水线）

这是一个可复用的 Agent Skills 工具包，用于把课程逐集制作成可检查的
本地视频包，并准备未公开的多平台草稿。

## 两个 Skill

- `course-production-pipeline`：逐集生产、适配器登记、横竖屏渲染、字幕、
  清单、Hash、FFprobe 媒体验收、可选来源追溯和草稿链校验。
- `multi-platform-publish`：本地关键词规则、发布状态机、草稿安全边界，
  以及 AiToEarn 固定白名单只读查询。

已经打通的是本地生产和验收、可选来源追溯、关键词由元数据决定、适配器接口
和 AiToEarn 只读能力检查；没有打通也不会假装打通的是自动公开发布、定时发布、删除、
评论、任意 URL 请求、上传签名、确认资源、创建 Flow 和浏览器页面脚本。

## 先跑通演示

```powershell
python scripts/create_demo_assets.py --output examples/demo/generated
python skills/course-production-pipeline/scripts/validate_episode_package.py examples/demo/generated/EP00-demo
python skills/course-production-pipeline/scripts/validate_skill_chain.py --package-dir examples/demo/generated/EP00-demo --registry examples/demo/generated/registry.json
```

演示素材由 FFmpeg 本地合成，不需要课程视频、声音或平台账号。

## 安装

安装默认只预览，不写入：

```powershell
python scripts/install_skills.py
```

确认计划后才应用：

```powershell
python scripts/install_skills.py --apply
```

发现已有同名 Skill 时，脚本会先复制到旁路备份目录并生成 Hash 清单。

## 来源追溯和 NotebookLM

来源追溯是可选项，不使用 NotebookLM 也能运行完整课程生产流程。若在
`metadata.json` 中声明 `source_type: "notebooklm"`，必须同时提供脱敏的
`source_ref`、已保存的来源快照、引用数量和人工确认。Skill 只检查这些声明，
不会登录 NotebookLM、读取私人链接或上传研究内容。具体规则见
`skills/course-production-pipeline/references/source-material-policy.md`。

## 关键词

核心词由课程元数据提供，要求非空、有序、不可重复；平台自动推荐但不在
`core + episode` 允许清单中的词会失败。阳明课程只作为公开的元数据示例，
核心词顺序为：

`阳明心学 → 致良知 → 心即理 → 企业AI转型 → 企业家`

它不包含真实视频、声音、账号、草稿或完整课程稿件。

## AiToEarn

只读脚本从当前进程的 `AITOEARN_API_KEY` 读取密钥，使用固定 GET 白名单，
默认输出摘要并脱敏。它不上传、不创建 Flow、不确认资源、不立即发布、不定时、
不删除，也不自动操作浏览器。公开文档请参见 [AiToEarn 开放平台](https://docs.aitoearn.cn/)。

## 规范与安全

两个目录遵循 [Agent Skills specification](https://agentskills.io/specification)，
仓库使用 MIT 许可证。贡献前阅读 `CONTRIBUTING.md`；不要提交 Key、Cookie、
账号资料、私有路径、真实课程媒体、克隆声音、平台截图或草稿证据。
