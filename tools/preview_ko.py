# -*- coding: utf-8 -*-
"""번역 미리보기 — 원문(게임 글리프) vs 한글 시안을 같은 조판 규칙으로 그린다.

⚠️ 미리보기 전용. 디스크(ISO/트랙)는 건드리지 않는다.
사용: python tools/preview_ko.py 62 117 174 ...
"""
import os, sys, csv, io
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from font_test_kr import GameFont, KrFont, MOD2, CELL, blit, FONT_DIR, FG, BG, ACC
from render_sim import layout, ADV, LINE

Z = 3


def load(name, key='jp'):
    d = {}
    for r in csv.DictReader(io.StringIO(open(os.path.join(
            common.WORK, 'trans', name), encoding='utf-8').read()), delimiter='\t'):
        d[r['id']] = r[key]
    return d


def draw_block(img, lines, x, y, gf, kf, tint=FG):
    for r, ln in enumerate(lines):
        for c, ch in enumerate(ln):
            g = kf.glyph(ch)[0] if '가' <= ch <= '힣' else gf.glyph(ch)
            if g:
                blit(img, g, x + c * ADV * Z, y + r * LINE * Z, Z, tint)
    return y + len(lines) * LINE * Z


def label(d, x, y, s, size=20, fill=FG):
    f = ImageFont.truetype(os.path.join(FONT_DIR, 'Galmuri11.ttf'), size)
    d.fontmode = '1'
    d.text((x, y), s, font=f, fill=fill)


def main():
    ids = sys.argv[1:] or ['62', '117', '54', '199', '215']
    gf = GameFont(MOD2)
    kf = KrFont('Galmuri11', 'Galmuri11.ttf', 11)
    jp, ko = load('text_jp.tsv'), load('ko_fit.tsv', 'ko')

    blocks = []
    for i in ids:
        blocks.append((i, layout(jp[i]), layout(ko[i])))

    W = COLS_PX = COLS = 23 * ADV * Z + 40
    H = 40
    for i, a, b in blocks:
        H += 34 + len(a) * LINE * Z + 30 + len(b) * LINE * Z + 34
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    y = 14
    for i, a, b in blocks:
        label(d, 16, y, 'id=%s  원문 %d줄 → 한글 %d줄' % (i, len(a), len(b)), 22, ACC)
        y += 28
        label(d, 16, y, 'JP', 16, (120, 170, 255))
        y = draw_block(img, a, 16, y + 20, gf, kf, (150, 200, 255)) + 12
        label(d, 16, y, 'KO', 16, (255, 200, 120))
        y = draw_block(img, b, 16, y + 20, gf, kf) + 26
    out = os.path.join(common.WORK, 'png', 'preview_ko_%s.png' % '_'.join(ids))
    img.save(out)
    print('→', out)


if __name__ == '__main__':
    main()
