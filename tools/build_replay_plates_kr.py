# -*- coding: utf-8 -*-
"""리플레이 메뉴 판때기(176x24 VDP1 스프라이트 3장) 한글화 (2026-10-13).

규명: 스테이트 `my files/Gungriffon II (K).state` 의 VDP1 명령표 — 4bpp 176x24 세 장이
  VRAM `0x675B0`(リプレイデータ再生) · `0x67DF0`(リプレイデータ保存) · `0x68630`(終了).
  → COMBAT RESULT 라벨과 **같은 LZSS 블록** `2_1` `0xCC8A8`(해제 → VRAM `0x62000`, 출력 오프셋 + 0x62000 = VRAM).
  그래서 `build_result_kr.py` 가 만든 `ingame_build/2_1` 의 블록을 다시 풀어 판때기만 덧그린다(★순서: result → 이것).
★기존 도구 그대로(실기 통과한 출격 판때기): 빈 판때기 = clean_plate.make(終了 판, 글자 상자)
  · 글자 = plate_text(바탕 명조 음각) + build_plates_kr 의 SIZE·BASELINE·BOOST·DEPTH·SHINE. 폭만 176.
  python tools/build_replay_plates_kr.py --preview   → work/png/replay_plates_ko.png 만
  python tools/build_replay_plates_kr.py             → ingame_build/2_1 에 덧씀
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import lzss
import plate_text
import clean_plate
import build_plates_kr as bp      # 출격 판때기 설정(글꼴·크기·음각) 그대로

BLOCK_OFF = 0xCC8A8
VRAM_BASE = 0x62000
W, H = 176, 24
ROWB = W // 2
PLATES = [  # (VRAM, 원문, 한글)
    (0x675B0, 'リプレイデータ再生', '리플레이 데이터 재생'),
    (0x67DF0, 'リプレイデータ保存', '리플레이 데이터 저장'),
    (0x68630, '終了', '종료'),
]
CLEAN_FROM = 0x68630                 # 終了
BOX = (3, 22, 60, 116)               # 지울 글자 상자(행 y0‥y1, 열 x0‥x1) — 終了 글자 열 69‥100 + 여유


def read_spr(blob, vram):
    o = vram - VRAM_BASE; a = np.zeros((H, W), np.uint8)
    for y in range(H):
        r = np.frombuffer(blob[o + y * ROWB:o + y * ROWB + ROWB], np.uint8)
        a[y, 0::2] = r >> 4; a[y, 1::2] = r & 15
    return a


def write_spr(blob, vram, a):
    o = vram - VRAM_BASE
    for y in range(H):
        blob[o + y * ROWB:o + y * ROWB + ROWB] = ((a[y, 0::2] << 4) | a[y, 1::2]).astype(np.uint8).tobytes()


def compose(bg, text):
    plate_text.W, plate_text.H = W, H                     # 폭만 176 — 글꼴은 plate_text 기본(바탕 명조)
    cov = np.clip(plate_text.coverage(text, bp.SIZE, bp.BASELINE) * bp.BOOST, 0, 1)
    return plate_text.engrave(bg, cov, bp.DEPTH, bp.SHINE)


def main():
    preview = '--preview' in sys.argv
    src = os.path.join(common.WORK, 'orig', '2_1')
    base = os.path.join(common.WORK, 'ingame_build', '2_1')
    orig = open(src, 'rb').read()
    oblob, end = lzss.decompress(orig, BLOCK_OFF)
    limit = end - BLOCK_OFF
    raw = bytearray(open(base, 'rb').read() if os.path.exists(base) else orig)
    blob, _ = lzss.decompress(bytes(raw), BLOCK_OFF)     # 결과 라벨이 이미 들어간 블록
    blob = bytearray(blob)
    bg = clean_plate.make([read_spr(oblob, CLEAN_FROM)], 0, BOX)
    rows = []
    for vram, jp, ko in PLATES:
        a = compose(bg, ko); write_spr(blob, vram, a)
        rows += [read_spr(oblob, vram), a, np.full((2, W), 8, np.uint8)]
    img = (np.vstack(rows) * 17).astype(np.uint8)
    Image.fromarray(img).resize((W * 4, img.shape[0] * 4), Image.NEAREST).save(os.path.join(common.WORK, 'png', 'replay_plates_ko.png'))
    print('미리보기 work/png/replay_plates_ko.png')
    if preview:
        return
    packed = lzss.compress(bytes(blob))
    print(f'되압축 {len(packed)} B / 상한 {limit} B')
    if len(packed) > limit:
        raise SystemExit('★압축 결과가 원본보다 크다')
    assert lzss.decompress(packed)[0] == bytes(blob), '왕복 불일치'
    raw[BLOCK_OFF:BLOCK_OFF + limit] = packed + b'\x00' * (limit - len(packed))
    open(base, 'wb').write(bytes(raw))
    print(f'→ {base}  (크기 불변 {len(raw) == len(orig)})')


if __name__ == '__main__':
    main()
