# Video Editing Analyzer

用于分析剪辑教程、拆解视频和教程截图，并把其中明确展示的剪辑知识整理成可复用的知识卡片；也可以根据口播文案生成逐句剪辑建议。

## 主要功能

- 以视频画面为主，读取右侧标注、功能名称、字体、音效、时间线和关键帧信息
- 区分“画面明示”“口播明示”和“视觉推断”，不把猜测写成确定功能
- 学习模式先输出候选知识，只有用户确认后才写入知识库
- 根据文案生成逐句分镜剪辑方案，默认整理成 Word（`.docx`）文件，不使用一个大表格塞入全部内容
- 支持记录已确认的字体、动画、画面处理、节奏和音效知识，后续按场景检索使用
- 提供 FFmpeg/FFprobe 抽帧脚本，辅助提取固定帧和场景切换帧

## 文件结构

```text
SKILL.md                              # Skill 主规则
references/                           # 输出模板、功能参考和已确认知识
  learned-editing-knowledge.md        # 用户确认后写入的知识库
scripts/extract_video_keyframes.py    # FFmpeg/FFprobe 视频抽帧脚本
```

## 安装

将整个文件夹复制到 Codex 的 skills 目录，例如：

```text
~/.codex/skills/video-editing-analyzer/
```

安装后重启或刷新 Codex，使其重新读取 `SKILL.md`。

## FFmpeg 抽帧脚本

脚本用于从教程视频中提取固定间隔帧和场景切换帧，方便重点查看右侧的文字标注、时间线和参数。

需要先安装并确保 `ffmpeg`、`ffprobe` 在系统 PATH 中：

```bash
python3 scripts/extract_video_keyframes.py input.mp4
```

常用选项：

```bash
python3 scripts/extract_video_keyframes.py input.mp4 --interval 1
python3 scripts/extract_video_keyframes.py input.mp4 --no-scenes
```

输出目录默认为 `input.mp4.keyframes/`，包含 `metadata.json`、`fixed/`、`scene/` 和 `frames/index.json`。

## 知识库规则

`references/learned-editing-knowledge.md` 只保存用户明确确认写入的知识。教程中看不清、只能推断或尚未验证的平台功能，会保留为待验证信息，不会自动当成确定规则。

## 适用范围

本 skill 主要用于剪辑教程和剪辑拆解知识整理。它不能仅凭成片可靠反推出唯一的剪映按钮、版本路径或原作者的具体操作步骤；无法确认时会明确标注限制和备选实现。

根据文案生成剪辑建议时，默认交付 Word 文档；若运行 skill 的平台不支持创建或附加 `.docx`，会在聊天中提供完整备用稿并说明限制。
