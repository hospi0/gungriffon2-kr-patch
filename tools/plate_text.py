# -*- coding: utf-8 -*-
"""빈 판때기 위에 «철판 음각» 한글 새기기.

원본 일본어 판때기의 질감을 따라간다:
  · 명조체(바탕) — 원문이 明朝体라 고딕을 쓰면 결이 다르다
  · 4배 초과표본 → 축소로 **안티에일리어싱 커버리지** 확보
  · 음각 = 커버리지만큼 **어둡게 파고**, 획의 오른쪽아래 가장자리에 **밝은 반사**
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

FONT = os.path.join('C:' + os.sep, 'Windows', 'Fonts', 'batang.ttc')
SS = 4                      # 초과표본 배율
W, H = 152, 24


def coverage(text, size, baseline, ss=SS, tracking=0.0):
    """텍스트의 안티에일리어싱 커버리지(0~1) 152x24"""
    f = ImageFont.truetype(FONT, size * ss)
    widths = [f.getlength(c) + tracking * ss for c in text]
    total = sum(widths)
    img = Image.new('L', (W * ss, H * ss), 0)
    d = ImageDraw.Draw(img)
    x = (W * ss - total) / 2
    for c, w in zip(text, widths):
        d.text((x, baseline * ss), c, font=f, fill=255, anchor='ls')
        x += w
    small = img.resize((W, H), Image.BOX)
    return np.asarray(small).astype(float) / 255.0


def engrave(bg, cov, depth=8.0, shine=6.0, floor=1.0):
    """음각: 커버리지만큼 파이고, 오른쪽아래 가장자리에 반사광."""
    a = bg.astype(float)
    edge = np.zeros_like(cov)
    edge[1:, 1:] = np.clip(cov[:-1, :-1] - cov[1:, 1:], 0, 1)
    a = a + shine * edge
    a = a - depth * cov
    return np.clip(np.rint(a), floor, 15).astype(np.uint8)


def render(bg, text, size=17, baseline=19, depth=8.0, shine=6.0, tracking=0.0):
    return engrave(bg, coverage(text, size, baseline, tracking=tracking),
                   depth, shine)
