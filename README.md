# gpt-image-2.5-skill

基于 OpenAI **GPT Image 2 / 2.5** API 的图片生成 / 编辑技能（Agent Skill）

## 功能

- **文生图 / 图生图**：最多 16 张参考图（本地路径或 URL 混用）
- **三个模型**：
  - `gpt-image-2.5-sunburst` — 精准与质量优先，复杂精细编辑首选（CLI 默认）
  - `gpt-image-2.5-flare` — 速度优先，延迟相比 Images 2.0 最高降低 50%
  - `gpt-image-2` — 均衡可靠
- **参数齐全**：质量档（low/medium/high，2.5 另有 xhigh/max）、尺寸、png/jpeg/webp + 压缩率、透明底
- **费用透明**：按 API 实际 usage 换算人民币输出（汇率每次自动拉取并缓存）
- **草稿画板**：自带浏览器画板 + 零依赖接收服务，在图上圈注即可转为生图参考
- **动图流水线**：链式编辑逐帧生成主体渐变序列，ffmpeg/Pillow 合成 GIF/MP4/WebP

## 作为 Agent Skill 安装

直接把以下内容发给 Agent：

```
安装 gpt-image-2.5 skill：https://github.com/zekiwen/gpt-image-2.5
```

把 `scripts/.env.example` 复制一份改名为 `.env`，填上自己的 OPENAI_API_KEY。

```
OPENAI_API_KEY=sk-你的密钥
USD_TO_CNY=7.0
RATE_UPDATED=2026-09-17
```

也可以直接配系统环境变量，两种方式任选，都兼容。

## 快速开始

发送给 Agent：

- 图片生成

  ```text
  /gpt-image-2.5 生成 电热水壶 的超高精细三维爆炸装配图，尺寸1：1，高质量
  ```

- 画板模式

  ```text
  /gpt-image-2.5 打开画板
  ```

- 动图生成

  ```text
  /gpt-image-2.5
  生成一个GIF
  【主题】：一盆【矮生向日葵】从【播种】到【枯萎结籽】的完整过程。
  【时间间隔】：每帧 1 秒
  【画幅】：16:9
  【帧表】：
  1. Day 1  播种   —— 土面微露一颗种子
  2. Day 4  破土   —— 弯颈嫩芽拱出，子叶未展
  3. Day 7  子叶   —— 两片椭圆形子叶展开
  4. Day 12 真叶   —— 2 片锯齿真叶，茎增高
  5. Day 20 孕蕾   —— 株型饱满，顶端绿豆大小花苞
  6. Day 26 初花   —— 花苞绽开成拳头大花盘
  7. Day 30 盛开   —— 花盘完全展开，花瓣舒展
  8. Day 42 凋谢   —— 花瓣垂头卷曲泛焦褐
  9. Day 50 结籽   —— 花盘结满瓜子，茎叶枯黄
  ```

## 目录结构

```
gpt-image-2.5/
├── SKILL.md                    # Agent 技能说明（触发条件 + 调用规范）
├── README.md
└── scripts/
    ├── create_image_cli.py     # 核心 CLI（纯标准库）
    ├── gen_gif.py              # 宫格帧 GIF 生成器（依赖本机 ffmpeg）
    ├── server.py               # 草稿画板接收服务（纯标准库，127.0.0.1:17841）
    ├── sketch_pad.html         # 浏览器画板
    └── .env.example            # 配置模板（复制为 .env 填入密钥）
```
