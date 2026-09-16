# gpt-image-2.5-skill

基于 OpenAI **GPT Image 2 / 2.5** API 的图片生成 / 编辑技能（Agent Skill），核心是一个**纯标准库、零第三方依赖**的 Python CLI，任意 Python 3.9+ 直接可跑。

## 功能

- **文生图 / 图生图**：最多 16 张参考图（本地路径或 URL 混用）
- **三个模型**：
  - `gpt-image-2.5-sunburst` — 精准与质量优先，复杂精细编辑首选（CLI 默认）
  - `gpt-image-2.5-flare` — 速度优先，延迟相比 Images 2.0 最高降低 50%
  - `gpt-image-2` — 均衡可靠
- **参数齐全**：质量档（medium/xhigh/max）、尺寸、png/jpeg/webp + 压缩率、透明底
- **费用透明**：按 API 实际 usage 换算人民币输出（汇率每日自动拉取并缓存）
- **草稿画板**：自带浏览器画板 + 零依赖接收服务，在图上圈注即可转为生图参考
- **动图流水线**：链式编辑逐帧生成主体渐变序列，ffmpeg/Pillow 合成 GIF/MP4/WebP

## 快速开始

```bash
# 设置密钥（环境变量，不落盘）
export OPENAI_API_KEY=sk-...

# 文生图（默认 sunburst + medium）
python scripts/create_image_cli.py --prompt "一只熊猫啃竹子"

# 图生图：把背景换成雪山
python scripts/create_image_cli.py --prompt "把背景换成雪山" --image ref.png

# 指定模型、尺寸、保存路径
python scripts/create_image_cli.py --prompt "赛博朋克城市夜景" \
  --model gpt-image-2.5-flare --size 2048x2048 --save city.png
```

生成耗时 10~260 秒，属正常现象。

## 作为 Agent Skill 安装

把整个目录复制到你的 Agent 技能目录即可（如 ZCode/Claude Code 的 `.agents/skills/gpt-image-2.5/`），`SKILL.md` 含完整触发说明与调用规范。

## 目录结构

```
gpt-image-2.5/
├── SKILL.md                    # Agent 技能说明（触发条件 + 调用规范）
├── README.md
├── scripts/
│   ├── create_image_cli.py     # 核心 CLI（纯标准库）
│   └── gen_gif.py              # 宫格帧 GIF 生成器（依赖本机 ffmpeg）
├── server.py                   # 草稿画板接收服务（纯标准库，127.0.0.1:17841）
└── sketch_pad.html             # 浏览器画板
```

## 说明

- 密钥只认环境变量 `OPENAI_API_KEY`，代码不存储、不传输密钥到任何第三方
- `scripts/.env` 仅为本机汇率缓存（自动生成），已加入 `.gitignore`
