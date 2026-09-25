# -*- coding: utf-8 -*-
"""출격 메뉴 판때기(152x24 VDP1 스프라이트 7장) 한글화.

규명 (2026-08-09):
  · `2_1` 의 LZSS 블록 **`0x53C24~0x55571`**(6,477 B) → 해제 12,768 B
    = 152x24 4bpp 스프라이트 **7장**. VDP1 VRAM `0x43000` 에 적재
    (블록 출력 오프셋 + 0x43000 = VRAM 주소).
  · 빈 판때기 = `clean_plate.py` (글자가 가장 짧은 `先攻` 에서 글자만 지우고
    좌우 그라데이션으로 메움). ★7장 중앙값은 가운데에 원문 잔상이 남아 못 쓴다.
  · 글자 = **바탕(명조)** 4배 초과표본 안티에일리어싱 + **음각**(파냄 + 오른쪽아래 반사광).
  ⚠ 다음 블록이 바로 뒤에 붙어 있어 되압축은 6,477 B 이하여야 한다.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import lzss
from clean_plate import make as clean_plate
from plate_text import coverage, engrave

BLOCK_OFF = 0x53C24
W, H = 152, 24
ROWB = W // 2
SZ = ROWB * H
NSPR = 7
SIZE, BASELINE, BOOST, DEPTH, SHINE = 16, 19, 2.5, 10.0, 5.0

TEXTS = [
    'LIVE 카메라 사용',   # LIVEカメラ使用
    '단독 출격',           # 単独出撃
    '협력출격 대장기',     # 協力出撃 隊長機
    '협력출격 호위기',     # 協力出撃　僚機
    '선공',                # 先攻
    '후공',                # 後攻
    '호위기 선택',         # 僚機選択
]


def sprites(blob):
    out = []
    for k in range(NSPR):
        off = k * SZ
        a = np.zeros((H, W), np.uint8)
        for y in range(H):
            r = np.frombuffer(blob[off + y*ROWB: off + y*ROWB + ROWB], dtype=np.uint8)
            a[y, 0::2] = r >> 4
            a[y, 1::2] = r & 15
        out.append(a)
    return np.stack(out)


def pack(blob, k, a):
    off = k * SZ
    for y in range(H):
        blob[off + y*ROWB: off + y*ROWB + ROWB] = \
            ((a[y, 0::2] << 4) | a[y, 1::2]).astype(np.uint8).tobytes()


def compose(bg, text):
    cov = np.clip(coverage(text, SIZE, BASELINE) * BOOST, 0, 1)
    return engrave(bg, cov, DEPTH, SHINE)


def main():
    src = os.path.join(common.WORK, 'orig', '2_1')
    base = os.path.join(common.WORK, 'ingame_build', '2_1')
    # ★블록 내용과 상한은 «항상 무수정 원본»에서 뽑는다.
    #   빌드본을 다시 읽으면 배경을 한글판에서 재추출하고(잔상 누적),
    #   패딩 때문에 상한이 실제보다 작아진다(6477 → 4704).
    orig = open(src, 'rb').read()
    blob, end = lzss.decompress(orig, BLOCK_OFF)
    limit = end - BLOCK_OFF
    raw = bytearray(open(base, 'rb').read() if os.path.exists(base) else orig)
    blob = bytearray(blob)
    A = sprites(blob)
    bg = clean_plate(A)
    for k, t in enumerate(TEXTS):
        pack(blob, k, compose(bg, t))
    print(f'판때기 {NSPR}장 다시 그림 (블록 0x{BLOCK_OFF:X}, 해제 {len(blob)} B)')

    packed = lzss.compress(bytes(blob))
    print(f'되압축 {len(packed)} B / 상한 {limit} B')
    if len(packed) > limit:
        raise SystemExit('★압축 결과가 원본보다 크다')
    back, _ = lzss.decompress(packed)
    assert back == bytes(blob), '왕복 불일치'
    raw[BLOCK_OFF:BLOCK_OFF + limit] = packed + b'\x00' * (limit - len(packed))
    open(base, 'wb').write(bytes(raw))
    print(f'→ {base}  ({len(raw)} B, 크기 불변 {len(raw) == os.path.getsize(src)})')


if __name__ == '__main__':
    main()
