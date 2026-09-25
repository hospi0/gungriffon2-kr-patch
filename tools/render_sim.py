# -*- coding: utf-8 -*-
"""텍스트 렌더 시뮬레이터 — 규명한 조판 규칙을 «실기 스크린샷과 대조»해 검증한다.

규칙 (2026-08-09 규명):
  · 제어토큰은 **`0A 0B` 쌍 하나뿐**. 항상 붙어 다니며 = 줄바꿈.
  · 그 밖엔 **23자 고정폭 강제 줄바꿈**(단어·문장 경계 무시, 전각 스페이스도 그냥 넘김).
  · `{01}` `{06}` 은 토큰이 아니라 **BE32 포인터의 상위 바이트**를 추출기가 오독한 것.
"""
import os, sys, csv
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from font_test_kr import GameFont, KrFont, MOD2, CELL, blit, FONT_DIR, FG, BG, ACC

COLS = 23          # 실측 확정 (id=117 두 줄이 각각 정확히 23자에서 잘림)
ADV = 12           # 글리프 11px + 1px 간격 = BDF DWIDTH 와 일치
LINE = 16          # 줄 간격 (스크린샷 세로 실측 92.7px / 5.786 = 16.0)


def layout(s, cols=COLS):
    """{0A}{0B} = 명시 줄바꿈, 그 외 cols 자에서 강제 줄바꿈."""
    lines, cur = [], ''
    i = 0
    while i < len(s):
        if s.startswith('{0A}{0B}', i):
            lines.append(cur); cur = ''; i += 8
            continue
        cur += s[i]; i += 1
        if len(cur) == cols:
            lines.append(cur); cur = ''
    lines.append(cur)
    return lines


def render(lines, gf, kf=None, z=4, cols=COLS):
    w = (cols * ADV + 2) * z
    h = (len(lines) * LINE + 4) * z
    img = Image.new('RGB', (w, h), BG)
    for r, ln in enumerate(lines):
        for c, ch in enumerate(ln):
            g = None
            if kf and '가' <= ch <= '힣':
                g = kf.glyph(ch)[0]
            else:
                g = gf.glyph(ch)
            if g:
                blit(img, g, (1 + c * ADV) * z, (2 + r * LINE) * z, z)
    return img


def label(d, x, y, s, size=20, fill=FG):
    f = ImageFont.truetype(os.path.join(FONT_DIR, 'Galmuri11.ttf'), size)
    d.fontmode = '1'
    d.text((x, y), s, font=f, fill=fill)


def main():
    gf = GameFont(MOD2)
    rows = {r['id']: r for r in csv.DictReader(
        open(os.path.join(common.WORK, 'trans', 'text_jp.tsv'), encoding='utf-8'),
        delimiter='\t')}

    jp = rows['117']['jp']
    lines = layout(jp)
    print('id=117 조판 결과')
    for i, l in enumerate(lines):
        print('  %d줄 (%2d자) %s' % (i + 1, len(l), l))

    sim = render(lines, gf, z=4)

    # 실기 스크린샷 — 같은 글자 피치로 맞춰 나란히
    sc = Image.open(os.path.join(common.MYFILES, '미션브리핑', '2.png')).convert('RGB')
    sc = sc.crop((100, 900, 1660, 1280))
    k = (ADV * 4) / 63.8                      # 스샷 실측 글자 피치 63.8px
    sc = sc.resize((int(sc.width * k), int(sc.height * k)), Image.LANCZOS)

    W = max(sim.width, sc.width) + 40
    img = Image.new('RGB', (W, sim.height + sc.height + 130), BG)
    d = ImageDraw.Draw(img)
    label(d, 20, 14, '조판 규칙 검증 — id=117 (23자 강제 줄바꿈 + {0A}{0B})', 24, ACC)
    label(d, 20, 50, '① 시뮬레이터', 20, (120, 200, 255))
    img.paste(sim, (20, 76))
    label(d, 20, 86 + sim.height, '② 실기 스크린샷 (같은 배율로 축척)', 20, (255, 190, 120))
    img.paste(sc, (20, 112 + sim.height))
    out = os.path.join(common.WORK, 'png', 'wrap_verify.png')
    img.save(out)
    print('→', out)


if __name__ == '__main__':
    main()
