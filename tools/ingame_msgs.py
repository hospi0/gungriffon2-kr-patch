# -*- coding: utf-8 -*-
"""인게임 메시지(HUD·DLS) 표 추출 — 건그리폰 II.

규명 (2026-08-09):
  · 글리프 풀 = `S*_PACK.NBG` — VDP2 NBG 셀(4bpp 8x8=32B), **파일오프셋 = VRAM오프셋**
  · 한 글자 = 16x16 = 4셀. 메시지 레코드 = **9자(18셀) 고정폭**,
    [상단 셀 18개][하단 셀 18개]
  · 표는 `S*_PACK.DAT` 안:
      HUD (VDP2 NBG1, 패턴네임 2워드) → 셀당 BE32 `0009 xxxx`
      DLS (VDP2 NBG0, 패턴네임 1워드) → 셀당 BE16
  · 글리프는 메시지끼리 **공유**된다(같은 글자면 같은 셀 번호).
"""
import os
import struct
import numpy as np

W = 18                      # 레코드 폭(셀)
REC2 = W * 2 * 2            # BE16 레코드 = 72 B
REC4 = W * 2 * 4            # BE32 레코드 = 144 B
CELL = 0x20


def load_pool(path):
    """NBG 파일 → (셀배열 [n,8,8] 니블, 셀 개수)"""
    d = open(path, 'rb').read()
    n = len(d) // CELL
    b = np.frombuffer(d, dtype=np.uint8)
    nib = np.empty(len(d) * 2, np.uint8)
    nib[0::2] = b >> 4
    nib[1::2] = b & 15
    return nib.reshape(n, 8, 8), n


def _runs(ok, minlen):
    out, i = [], 0
    while i < len(ok):
        if ok[i]:
            j = i
            while j < len(ok) and ok[j]:
                j += 1
            if j - i >= minlen:
                out.append((i, j - i))
            i = j
        else:
            i += 1
    return out


def find_tables(dat, ncell, lo=0x0600):
    """(hud_off, hud_nrec), (dls_off, dls_nrec) — 가장 긴 런 하나씩.
    ★런의 «끝»을 기준으로 정렬한다(선두에 우연히 범위에 든 값이 붙는다)."""
    n4 = len(dat) // 4
    ok4 = np.zeros(n4, bool)
    v4 = np.frombuffer(dat[:n4*4], dtype='>u2').reshape(-1, 2)
    ok4 = (v4[:, 0] == 9) & (v4[:, 1] >= lo) & (v4[:, 1] < ncell)
    r4 = _runs(ok4, W * 2)

    n2 = len(dat) // 2
    v2 = np.frombuffer(dat[:n2*2], dtype='>u2')
    ok2 = (v2 >= lo) & (v2 < ncell)
    r2 = _runs(ok2, W * 2)

    def pick(runs, width, rec):
        if not runs:
            return None
        i, ln = max(runs, key=lambda x: x[1])
        end = (i + ln) * width
        nrec = ln // (W * 2)
        return end - nrec * rec, nrec

    hud = pick(r4, 4, REC4)
    # DLS 후보가 HUD 구역과 겹치면 «버리지 말고» 시작을 HUD 끝으로 자른다.
    # (DLS 표는 HUD 표 바로 뒤에 붙어 있고, 경계 직전 값이 우연히 범위에 들어
    #  런이 2바이트 앞에서 시작한다 — 통째로 버리면 표를 통째로 놓친다.)
    if hud:
        h0, hn = hud
        h1 = h0 + hn * REC4
        trimmed = []
        for i, l in r2:
            s, e = i * 2, (i + l) * 2
            if s < h1 and e > h1:
                s = h1
            elif s < h1:
                continue
            if (e - s) // 2 >= W * 2:
                trimmed.append((s // 2, (e - s) // 2))
        r2 = trimmed
    dls = pick(r2, 2, REC2)
    return hud, dls


def read_records(dat, off, nrec, width):
    """[nrec][36] 셀번호"""
    out = []
    for k in range(nrec):
        base = off + k * (REC4 if width == 4 else REC2)
        if width == 4:
            row = [struct.unpack_from('>HH', dat, base + i*4)[1] for i in range(W*2)]
        else:
            row = [struct.unpack_from('>H', dat, base + i*2)[0] for i in range(W*2)]
        out.append(row)
    return out


def glyph4(cells, tl, tr, bl, br):
    """네 셀 번호로 16x16 조립. ★TR 은 TL+1 이 «아니다» — 레코드의 다음 항목이다
    (붙어 있는 경우가 많아 착각하기 쉽다. Ｃ·。·－ 등에서 실제로 어긋난다)."""
    a = np.zeros((16, 16), np.uint8)
    a[:8, :8] = cells[tl]
    a[:8, 8:] = cells[tr]
    a[8:, :8] = cells[bl]
    a[8:, 8:] = cells[br]
    return a


def glyph_at(cells, rec, i):
    """레코드의 i번째 «글자»(0~8)를 16x16 으로."""
    return glyph4(cells, rec[i*2], rec[i*2 + 1], rec[W + i*2], rec[W + i*2 + 1])


def record_glyphs(cells, rec):
    """레코드 → 9글자의 (topcell, botcell) 쌍"""
    return [(rec[i*2], rec[W + i*2]) for i in range(W // 2)]
