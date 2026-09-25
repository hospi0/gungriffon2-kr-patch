# -*- coding: utf-8 -*-
"""COMBAT RESULT 화면 라벨 한글화.

규명 (2026-08-09):
  · 라벨은 **VDP1 스프라이트**(4bpp). 텍스처가 `2_1` 의 LZSS 블록 `0xCC8A8` 안에 있다.
  · 해제 77,152 B 가 통째로 VDP1 VRAM `0x62000` 에 올라간다
    → **블록 출력 오프셋 + 0x62000 = VRAM 주소**
  · 코덱 = 오쿠무라 LZSS (`tools/lzss.py`, `/2` 0x153C8 해제 루틴에서 역공학)
  · 글자 = `/2` 의 11x11 폰트를 advance 12 로 찍고 **외곽선 = 값 1**,
    내부는 **세로 그라데이션**(행별 값). 글자 시작 = (x=1, y=1)
  · 스프라이트 폭은 8배수라 **최대 글자수 = floor(w/12)**
  ⚠ 블록이 `2_1` 의 **파일 끝**이라 되압축 결과가 33,708 B 를 넘으면 안 된다.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import lzss
from font_test_kr import GameFont, KrFont, MOD2

BLOCK_OFF = 0xCC8A8
VRAM_BASE = 0x62000
ADV = 12
GRAD = {1: 11, 2: 11, 3: 10, 4: 10, 5: 10, 6: 10, 7: 11, 8: 11,
        9: 12, 10: 15, 11: 15}          # 원본 행별 최빈 내부값

# (VRAM 주소, 폭, 높이, 원문, 한글) — 한글 None 이면 그대로 둔다
LABELS = [
    (0x62000, 176, 24, 'COMBAT RESULT', None),
    (0x62840,  56, 14, '戦闘区域',            '전투구역'),
    (0x62AE0,  56, 14, '作戦時間',            '작전시간'),
    (0x62C68, 112, 14, '装甲歩行戦闘車両数',  '장갑보행전투차량수'),
    (0x62F78,  64, 14, '各種車両数',          '각종차량수'),
    (0x63138,  64, 14, '航空兵器数',          '항공병기수'),
    (0x632F8,  64, 14, '敵総撃破数',          '적총격파수'),
    (0x634B8,  40, 14, '撃破率',              '격파율'),
    (0x635D0,  56, 14, '戦闘得点',            '전투점수'),
    (0x63758,  72, 14, '自機破損失点',        '자기파손감점'),
    (0x63950,  80, 14, '僚機破損失点',        '아군파손감점'),
    (0x63B80,  56, 14, '特別得点',            '특별점수'),
    (0x63D08,  56, 14, '総合得点',            '종합점수'),
    (0x63E80,  16, 12, '％',                  None),
    (0x63EE0,  16, 14, '機',                  '기'),
    (0x63F50,  72, 12, 'AWJILAH',             None),
]


def read_spr(blob, off, w, h):
    a = np.zeros((h, w), np.uint8)
    rb = w // 2
    for y in range(h):
        r = np.frombuffer(blob[off + y*rb: off + y*rb + rb], dtype=np.uint8)
        a[y, 0::2] = r >> 4
        a[y, 1::2] = r & 15
    return a


def write_spr(blob, off, a):
    h, w = a.shape
    rb = w // 2
    for y in range(h):
        row = ((a[y, 0::2] << 4) | a[y, 1::2]).astype(np.uint8).tobytes()
        blob[off + y*rb: off + y*rb + rb] = row


def render(text, w, h, gf, kf):
    """11x11 글리프 + 외곽선(1) + 세로 그라데이션"""
    mask = np.zeros((h, w), bool)
    for i, ch in enumerate(text):
        g = kf.glyph(ch)[0] if '가' <= ch <= '힣' else gf.glyph(ch)
        if not g:
            raise SystemExit(f'글리프 없음: {ch}')
        for y in range(11):
            for x in range(11):
                if g[y][x]:
                    px, py = 1 + i*ADV + x, 1 + y
                    if 0 <= px < w and 0 <= py < h:
                        mask[py][px] = True
    a = np.zeros((h, w), np.uint8)
    for y in range(h):
        for x in range(w):
            if mask[y][x]:
                a[y][x] = GRAD.get(y, 15)
    # 외곽선 = 잉크의 8이웃 중 빈 칸
    for y in range(h):
        for x in range(w):
            if a[y][x]:
                continue
            hit = False
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < h and 0 <= nx < w and mask[ny][nx]:
                        hit = True
            if hit:
                a[y][x] = 1
    return a


def main():
    src = os.path.join(common.WORK, 'orig', '2_1')
    raw = bytearray(open(src, 'rb').read())
    blob, end = lzss.decompress(bytes(raw), BLOCK_OFF)
    orig_clen = end - BLOCK_OFF
    blob = bytearray(blob)
    print(f'블록 0x{BLOCK_OFF:X}~0x{end:X} ({orig_clen} B) → 해제 {len(blob)} B')

    gf = GameFont(MOD2)
    kf = KrFont('Galmuri11', 'Galmuri11.ttf', 11)
    n = 0
    for addr, w, h, jp, ko in LABELS:
        if ko is None:
            continue
        maxc = w // ADV
        if len(ko) > maxc:
            raise SystemExit(f'{jp}: 「{ko}」 {len(ko)}자 > 최대 {maxc}자 (폭 {w})')
        write_spr(blob, addr - VRAM_BASE, render(ko, w, h, gf, kf))
        n += 1
    print(f'라벨 {n}개 다시 그림')

    packed = lzss.compress(bytes(blob))
    print(f'되압축 {len(packed)} B / 상한 {orig_clen} B')
    if len(packed) > orig_clen:
        raise SystemExit('★압축 결과가 원본보다 크다 — 축약 필요')
    back, _ = lzss.decompress(packed)
    assert back == bytes(blob), '왕복 불일치'
    raw[BLOCK_OFF:BLOCK_OFF + orig_clen] = packed + b'\x00' * (orig_clen - len(packed))
    out = os.path.join(common.WORK, 'ingame_build', '2_1')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, 'wb').write(bytes(raw))
    print(f'→ {out}  ({len(raw)} B, 크기 불변 {len(raw) == os.path.getsize(src)})')


if __name__ == '__main__':
    main()
