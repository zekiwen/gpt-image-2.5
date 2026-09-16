---
name: gpt-image-2.5
description: "通过 OpenAI GPT Image 2 / 2.5 API 生成或编辑图片。当用户要求生成图片、画图、AI 绘图、图片编辑、风格转换、背景替换等图像创作任务时触发此技能。"
agent_created: true
---

# GPT Image 图片生成

通过本技能目录下的 `scripts/create_image_cli.py` 生成或编辑图片，支持文生图与图生图（最多 16 张参考图）。

**模型说明**：GPT-Image-2.5 是 OpenAI 新一代图像生成与编辑模型，主打更高画质、更精准的编辑、更稳定的多轮修改和更快的生成速度。

- `gpt-image-2.5-sunburst`：精准与质量优先，生成时间更长，适合复杂、精细的图像编辑与创作（参考图合成、改图首选），**CLI 默认**
- `gpt-image-2.5-flare`：速度与效率优先，兼顾高质量生成与编辑，延迟相比 Images 2.0 最高降低 50%，适合大多数日常图像生成场景
- `gpt-image-2`：画质与编辑能力均衡可靠，但速度和 token 效率不及 2.5（实测 high 档 1024 约 90s / ¥1.5）；质量档最高 `high`，透明底属 preview 特性

## 调用

```bash
PYTHON="python"
SCRIPT="<本技能目录绝对路径>/scripts/create_image_cli.py"

"$PYTHON" "$SCRIPT" --prompt "提示词" [参数]
```

| 参数 | 默认 | 说明 |
|------|------|------|
| `--prompt` | 必填 | 提示词 |
| `--image` | — | 参考图（本地路径或 URL），可重复传，最多 16 张；传入即图生图 |
| `--model` | `gpt-image-2.5-sunburst` | 可选模型共 3 个，见上方模型说明 |
| `--quality` | `medium` | 档位随模型：gpt-image-2 最高 `high`，2.5 系列另有 `xhigh`/`max`；`high` 及以上仅限用户明确要求时传（见「质量档限制」） |
| `--size` | `auto` | 如 `1024x1024` |
| `--format` / `--compression` | png | `jpeg`/`webp` 时可加压缩率 0-100 |
| `--background` | — | `transparent`（需 png/webp）/ `opaque` / `auto` |
| `--save` | `GPT-Image/` | 保存路径（相对当前工作目录），目录自动创建 |

### 示例

```bash
# 1. 文生图（最小调用：全默认 = sunburst + medium + auto 尺寸）
"$PYTHON" "$SCRIPT" --prompt "一只熊猫啃竹子"

# 2. 文生图：指定模型、尺寸、质量与保存路径
"$PYTHON" "$SCRIPT" --prompt "赛博朋克城市夜景" \
  --model gpt-image-2.5-flare --size 2048x2048 --quality medium \
  --save "/path/to/city.png"

# 3. 图生图：单张本地参考图
"$PYTHON" "$SCRIPT" --prompt "把背景换成雪山" --image ref.png

# 4. 图生图：多参考图，本地与 URL 混用
"$PYTHON" "$SCRIPT" --prompt "图1改成动漫风格, 图2的衣服加进去" \
  --image 1.png --image https://example.com/2.png

# 5. 2.5 最高质量透明底 webp（仅当用户明确要求 xhigh 档时才这样传）
"$PYTHON" "$SCRIPT" --prompt "产品吉祥物立绘" \
  --model gpt-image-2.5-flare --quality xhigh \
  --format webp --compression 90 --background transparent
```

## 生成耗时

10~260 秒，期间无输出正常，**不要中断或重试**；Bash 执行时 timeout 设 300000 以上

## 质量档限制

`high` / `xhigh` / `max` 仅在明确提出"高质量 / high / 最高质量"等要求时才可传入；未明确说明质量时一律用默认 `medium`（草稿可用 `low`），**不得擅自升级**

## 费用输出

成功标志 `✅ 图片已保存: <路径>`；费用按实际 usage 输出 `💰 本次费用: ¥<金额>`





## 动图生成

用 GPT-Image 链式生成「主体逐渐变化」的系列帧，合成为循环 GIF。

支持生成格式：
- MP4:高保真 + 到处能播——「照片」应用、Media Player、手机、微信(以视频形式发)全支持，发群聊用它；
- GIF:任何查看器都动，但 256 色上限，保真度不如 MP4;
- WebP:只在浏览器里动，系统照片应用不认它的动图，留作网页用途即可。


### 第一步：定主题 + 澄清

生成前必须向用户澄清：

- **主题内容**：什么主体、什么变化过程（如「一盆花从播种到枯萎」）
- **帧表**：几帧、每帧画什么（逐帧列出来清单）
- **时间间隔**：每帧停留多长（默认 1 秒/帧）

未澄清不动手。

### 第二步：质量档确认

- **默认 `low` 质量测试验证！**（省钱、快速看效果）
- 测试效果好 → 切换高质量（`medium` 及以上）正式生成
- **具体默认使用模式先跟用户确认！**

### 第三步：生成首图 → 用户确认基图

- 用 **low** 质量生成第 1 帧后**立即停下**，交给用户过目
- ⛔ **第一帧未经用户明确确认前，禁止生成后续任何帧！绝对不允许跳过这一步！**
- 用户确认后即为**全链基准图**，之后所有帧以它为起点

### 第四步：串行生成其余帧

- 帧 N = 帧 N-1 作 `--image` 参考图 + 提示词模板：

  > 以参考图为基础做局部编辑：只修改【本轮增量】，其余一切与参考图像素级一致——严禁缩小、压扁、拉远或重新构图。

### 第五步：合成与交付

> 具体生成类型需要向用户确认GIF,MP4,WebP其中一种类型

GIF示例 目录结构：

```
GPT-Image/GIF/<主题名称>/
├── frame_01.png ~ frame_NN.png   # 两位序号
└── <主题名称>.gif            # 成品(支持GIF,MP4,WebP)
```

ffmpeg 合成（按第二步澄清的间隔设 framerate，1 秒/帧 = 1）：

```bash
ffmpeg -framerate <1/间隔秒> -i frame_%02d.png -vf "split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" -loop 0 <主体名称>.gif
```

ffmpeg 不在 → 回退 Pillow：

```python
from PIL import Image
frames = [Image.open(f"frame_{i:02d}.png").convert("RGB") for i in range(1, N + 1)]
frames[0].save("<主体名称>.gif", save_all=True, append_images=frames[1:],
               duration=<间隔毫秒>, loop=0)  # loop=0 无限循环
```

可选增值：程序叠文字（**文字绝不进生图提示词**，中文必崩）、压缩档、MP4 导出。





## 草稿绘制

在图片上绘制/圈注内容或者把白板上绘制的草稿转换成图片再生成时使用。

### 启动画板

先在项目根启动接收服务再打开画板（服务+画板均随本技能目录携带）：

```bash
python <本技能目录绝对路径>/server.py     # 零依赖 Python 接收服务（纯标准库），127.0.0.1:17841，须在项目根运行
start http://127.0.0.1:17841/            # 任意浏览器打开画板
```

### 导出与拾取

- 点「导出」即直写 `GPT-Image/sketch_io/<yyyy-MM-dd-HH-mm-ss>/`（内含 `sketch.png` + 从元数据解析出的 `prompt.txt`，零弹窗），随后画板页自动关闭、接收服务自动退出，整条链路一次导出后自动收摊；服务未启动时导出退回浏览器下载
- 后台任务监听 `GPT-Image/sketch_io/` 新目录，拾取后读 `prompt.txt` 取效果描述（为空则按"圈选区域精修/去除圈线"语义理解）；已存在 `sketch_io/<yyyy-MM-dd-HH-mm-ss>/` 的交付不重复处理
- 以草图作 `--image` 参考图生成，结果按任务起简短名称存 `GPT-Image/<简短任务名称>.png`；其他保存位置用 `--save`
