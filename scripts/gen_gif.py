"""宫格帧 GIF 生成器：一次生成 sprite sheet → ffmpeg 确定性切帧 → 合成循环 GIF。
纯标准库 + 本机 ffmpeg（无 pip 依赖）。网格生成复用同目录 create_image_cli.py。

用法：
  python gen_gif.py --prompt "一只柴犬摇尾巴打招呼" [--frames 3x4] [--fps 7] [--ref 参考图.png] [--save out.gif]
"""
import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(HERE, 'create_image_cli.py')


def run(cmd, **kw):
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        sys.exit(f'❌ 命令失败: {" ".join(cmd)}')


def main():
    ap = argparse.ArgumentParser(description='宫格帧 GIF 生成（sprite sheet → 切帧 → 循环 GIF）')
    ap.add_argument('--prompt', required=True, help='动画内容描述（主体+动作+风格，宜简单可循环）')
    ap.add_argument('--frames', default='3x4', help='网格 行x列：3x4=12帧 / 4x4=16帧')
    ap.add_argument('--fps', type=float, default=7, help='GIF 帧率，默认 7（约143ms/帧）')
    ap.add_argument('--trim', type=float, default=0.05, help='每帧四周裁掉比例（去网格线），默认 0.05')
    ap.add_argument('--ref', help='参考图（角色定妆/首帧），透传给 --image')
    ap.add_argument('--size', default='', help='宫格图尺寸；默认 3 行用 1024x1536，其余 1024x1024')
    ap.add_argument('--save', default='', help='输出 GIF 路径；默认 GPT-Image/gif_<时间戳>.gif')
    ap.add_argument('--quality', default='medium')
    ap.add_argument('--model', default='gpt-image-2.5-sunburst')
    a = ap.parse_args()

    m = re.match(r'^(\d+)x(\d+)$', a.frames)
    if not m:
        sys.exit('❌ --frames 须为 行x列，如 3x4')
    R, C = int(m.group(1)), int(m.group(2))
    N = R * C
    size = a.size or ('1024x1536' if R == 3 else '1024x1024')

    sheet_prompt = (
        f'一张 {R} 行 {C} 列的网格图（sprite sheet），共 {N} 格，'
        f'每格是同一段动画的连续一帧，帧顺序从左到右、从上到下，首尾帧能自然衔接成循环。'
        f'动画内容：{a.prompt}。'
        f'所有帧中主体外观、比例、视角与背景保持完全一致，仅动作逐帧推进；格子间用细线分隔、不留白边。'
    )

    t0 = time.time()
    workdir = tempfile.mkdtemp(prefix='gifsheet_')
    sheet = os.path.join(workdir, 'sheet.png')
    try:
        print(f'⏳ [1/3] 生成 {R}x{C} 宫格（{N} 帧，{size}）…')
        cmd = [sys.executable, CLI, '--prompt', sheet_prompt, '--model', a.model,
               '--quality', a.quality, '--size', size, '--save', sheet]
        if a.ref:
            cmd += ['--image', a.ref]
        run(cmd)

        print(f'⏳ [2/3] 切帧（每帧去边 {a.trim:.0%}）…')
        for row in range(R):
            for col in range(C):
                vf = (f"crop=iw/{C}:ih/{R}:{col}*iw/{C}:{row}*ih/{R},"
                      f"crop=iw*(1-{2 * a.trim}):ih*(1-{2 * a.trim}):iw*{a.trim}:ih*{a.trim}")
                run(['ffmpeg', '-v', 'error', '-y', '-i', sheet, '-vf', vf,
                     os.path.join(workdir, 'f%02d.png' % (row * C + col + 1))])

        out = a.save or os.path.join('GPT-Image', 'gif_%s.gif' % datetime.datetime.now().strftime('%Y%m%d%H%M%S'))
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        print(f'⏳ [3/3] 合成 GIF（{a.fps} fps，无限循环）…')
        run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(a.fps),
             '-i', os.path.join(workdir, 'f%02d.png'),
             '-vf', 'split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle',
             '-loop', '0', out])

        nb = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                             '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', out],
                            capture_output=True, text=True).stdout.strip()
        kb = os.path.getsize(out) / 1024
        print(f'✅ GIF 已保存: {out}（{nb} 帧 / {a.fps} fps / {kb:.0f} KB / 耗时 {time.time() - t0:.0f}s）')
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == '__main__':
    main()
