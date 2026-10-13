# -*- coding: utf-8 -*-
"""깨끗한 빈 판때기 만들기.

7장 중 **`先攻`(#4)** 이 글자가 가장 짧아 가운데가 제일 깨끗하다 → 이걸 바탕으로 쓴다.
글자 상자(열 56~98, 행 3~21)만 지우고, 그 자리를 **좌우 배경에서 가로로 이어 붙인
그라데이션**으로 채운다. 원본 결(디더)을 살리려고 좌우 참조열의 «잔결»도 섞는다.
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lzss

# ★`build_plates_kr` 에서 가져오면 순환 임포트가 된다 — 여기서 자체 정의한다.
BLOCK_OFF = 0x53C24
_W, _H, _NSPR = 152, 24, 7
_ROWB = _W // 2
_SZ = _ROWB * _H


def sprites(blob):
    out = []
    for k in range(_NSPR):
        off = k * _SZ
        a = np.zeros((_H, _W), np.uint8)
        for y in range(_H):
            r = np.frombuffer(blob[off + y*_ROWB: off + y*_ROWB + _ROWB], dtype=np.uint8)
            a[y, 0::2] = r >> 4
            a[y, 1::2] = r & 15
        out.append(a)
    return np.stack(out)

BOX = (3, 22, 56, 99)          # y0, y1, x0, x1  (반열림)
MARGIN = 8                     # 좌우 참조 폭


def make(A, idx=4, box=None):
    # A[idx] 판때기의 글자 상자 box(기본 先攻)만 지운다 — 리플레이 판때기(176폭)도 이걸로(2026-10-13)
    p = A[idx].astype(float)
    y0, y1, x0, x1 = box or BOX
    out = p.copy()
    for y in range(y0, y1):
        left = p[y, x0 - MARGIN:x0]
        right = p[y, x1:x1 + MARGIN]
        a, b = left.mean(), right.mean()
        n = x1 - x0
        # 좌우 평균을 잇는 선형 그라데이션
        base = a + (b - a) * (np.arange(n) + 0.5) / n
        # 원본 결 = 참조 구간의 평균 대비 편차를 좌우에서 번갈아 빌려온다
        grain = np.concatenate([left - a, right - b])
        g = np.resize(grain, n)
        out[y, x0:x1] = base + g
    # 4x4 오더드 디더로 정수화 (밴딩 방지)
    bayer = np.array([[0, 8, 2, 10], [12, 4, 14, 6],
                      [3, 11, 1, 9], [15, 7, 13, 5]]) / 16.0 - 0.5
    d = np.tile(bayer, (out.shape[0] // 4 + 1, out.shape[1] // 4 + 1))[:out.shape[0], :out.shape[1]]
    q = np.clip(np.rint(out + d), 2, 12).astype(np.uint8)
    # 글자 상자 밖은 원본 그대로 (테두리 손상 방지)
    res = A[idx].astype(np.uint8).copy()
    res[y0:y1, x0:x1] = q[y0:y1, x0:x1]
    return res


def load_plates(path='work/orig/2_1'):
    blob, _ = lzss.decompress(open(path, 'rb').read(), BLOCK_OFF)
    return sprites(blob)


if __name__ == '__main__':
    A = load_plates()
    clean = make(A)
    out = os.path.join('my files', '미리보기', '0_빈판때기.png')
    ims = [A[4], clean]
    sh = np.zeros((len(ims) * 30, 152), np.uint8)
    for i, a in enumerate(ims):
        sh[i*30:i*30+24] = a * 17
    from PIL import Image
    Image.fromarray(sh).resize((152*4, len(ims)*30*4), Image.NEAREST).save(out)
    np.save(os.path.join('work', 'trans', 'plate_bg.npy'), clean)
    print('→', out, '(위 = 원본 先攻, 아래 = 글자 지운 빈 판때기)')
