# -*- coding: utf-8 -*-
"""인게임 메시지(HUD·DLS) 한글화 빌더.

구조는 `ingame_msgs.py` 참조. 요약:
  · 글리프 풀 = `S*_PACK.NBG` 의 셀 구간(스테이지마다 실측)
  · 한 글자 = 4셀(TL,TR / BL,BR). 레코드는 상단 셀 18개 + 하단 셀 18개
  · 레코드 = **9자 고정**

동작:
  1. 원문 9자 ↔ 레코드 셀쌍 대응으로 «문자 → 원본 글리프» 표를 만든다
     (！。－ＡＢ… 같은 비한글은 원본 픽셀을 그대로 재사용)
  2. 한글 음절은 Galmuri14 BDF 를 16x16 셀에 찍는다
     — 원본과 같은 «본체 15 + 오른쪽 끝 14» 음영 규칙을 적용
  3. 풀 구간을 새로 배치하고 레코드의 셀 번호를 갱신
  4. 번역하지 않는 줄(PAUSE 등)은 원래 셀을 «예약»해 건드리지 않는다
"""
import os
import sys
import csv
import json
import struct

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from ingame_msgs import (W, REC2, REC4, CELL, load_pool, find_tables,
                         read_records, glyph_at)

FONT_DIR = os.path.join('C:' + os.sep, 'claude', 'project', 'conker-kr-patch',
                        'my folder', 'Galmuri-v2.40.3')
BDF = os.path.join(FONT_DIR, 'Galmuri14.bdf')

INK, SHADE = 15, 14          # 원본 규칙: 본체 15, 가로 런 오른쪽 끝 다음 칸 14
SKIP_IDS = {43}              # 반각 라틴 + 그라데이션 — 원문 유지
BAND_ID = 42                 # 「通信エラー」 — 배경 띠가 글리프에 구워진 줄


# ---------------------------------------------------------------- BDF

def load_bdf(path):
    glyphs, cp, bbx, rows, reading = {}, None, None, [], False
    for ln in open(path, encoding='utf-8', errors='replace'):
        ln = ln.strip()
        if ln.startswith('ENCODING'):
            cp = int(ln.split()[1])
        elif ln.startswith('BBX'):
            bbx = [int(v) for v in ln.split()[1:5]]
        elif ln == 'BITMAP':
            rows, reading = [], True
        elif ln == 'ENDCHAR':
            if cp is not None and bbx:
                w, h, xo, yo = bbx
                nib = (w + 7) // 8 * 2
                bm = [[(int(r[:nib] or '0', 16) >> (nib * 4 - 1 - x)) & 1
                       for x in range(w)] for r in rows]
                glyphs[cp] = (w, h, xo, yo, bm)
            reading = False
        elif reading and ln:
            rows.append(ln)
    return glyphs


class KrGlyphs:
    """Galmuri14 → 16x16 셀. 원점은 대표 글자군으로 한 번만 고정한다."""
    PROBE = '가힣강논뷁를제한'

    def __init__(self, path):
        self.g = load_bdf(path)
        x0 = y0 = 99
        x1 = y1 = -99
        for ch in self.PROBE:
            e = self.g.get(ord(ch))
            if not e:
                continue
            w, h, xo, yo, _ = e
            x0, x1 = min(x0, xo), max(x1, xo + w - 1)
            y0, y1 = min(y0, yo), max(y1, yo + h - 1)
        iw, ih = x1 - x0 + 1, y1 - y0 + 1
        self.ox = -x0 + max(0, (16 - iw) // 2)
        self.base = min(16, y1 + 1) + max(0, (16 - ih) // 2)

    def bitmap(self, ch):
        e = self.g.get(ord(ch))
        out = np.zeros((16, 16), np.uint8)
        if not e:
            return out, False
        w, h, xo, yo, bm = e
        ok = True
        for j in range(h):
            for i in range(w):
                if not bm[j][i]:
                    continue
                x = xo + i + self.ox
                y = self.base - (yo + h - j)
                if 0 <= x < 16 and 0 <= y < 16:
                    out[y][x] = 1
                else:
                    ok = False
        return out, ok


def shade(mask):
    """1bpp 마스크 → 원본과 같은 음영 규칙의 4bpp 16x16"""
    a = np.zeros((16, 16), np.uint8)
    a[mask > 0] = INK
    for y in range(16):
        for x in range(16):
            if mask[y][x] and (x + 1 < 16) and not mask[y][x + 1] and a[y][x + 1] == 0:
                a[y][x + 1] = SHADE
    return a


# ---------------------------------------------------------------- 표

def load_tsv(path):
    rows = list(csv.DictReader(open(path, encoding='utf-8'), delimiter='\t'))
    return {int(r['id']): (r['jp'], r['ko']) for r in rows}


def char_cellmap(cells, recs, texts):
    """원문 9자 ↔ 셀쌍 → {문자: 16x16 픽셀}. 불일치는 경고."""
    out, seen = {}, {}
    for idx, rec in recs:
        jp = texts.get(idx, ('', ''))[0]
        if not jp:
            continue
        jp = jp.ljust(W // 2, '　')
        if len(jp) != W // 2:
            continue
        for i, ch in enumerate(jp):
            g = glyph_at(cells, rec, i)
            key = g.tobytes()
            if ch in seen and seen[ch] != key:
                out.setdefault('__conflict__', []).append(ch)
            seen[ch] = key
            out[ch] = g
    return out


# ------------------------------------------------- 「通信エラー」 배경 띠 줄

BAND_TEXT = '통신 에러'


def band_tiles(cells, rec, kr):
    """18칸이 통째로 한 그림인 줄. 띠를 재구성하고 한글을 얹어 16x16 9장으로 자른다.

    · 0·14·15행 = 원본 그대로(글자 없음)
    · 1행 = 4픽셀 디더 무늬를 위상 맞춰 다시 깔기
    · 2~13행 = 값 3으로 채우되 좌우 2칸 테두리는 보존
    · 글자 = 값 15, **가로 1px 굵히기**(원본이 2px 획)
    """
    img = np.zeros((16, W * 8), np.uint8)
    for j in range(W):
        img[:8, j*8:(j+1)*8] = cells[rec[j]]
        img[8:, j*8:(j+1)*8] = cells[rec[W + j]]
    band = img.copy()
    pat = band[1, 136:140].copy()
    for x in range(band.shape[1]):
        band[1, x] = pat[x % 4]
    band[2:14, 2:band.shape[1]-2] = 3

    mask = np.zeros_like(band, bool)
    adv = [16 if '가' <= c <= '힣' else (8 if c == ' ' else 10) for c in BAND_TEXT]
    ox = (band.shape[1] - sum(adv)) // 2
    for c, w in zip(BAND_TEXT, adv):
        e = kr.g.get(ord(c))
        if e:
            gw, gh, xo, yo, bm = e
            for j in range(gh):
                for i in range(gw):
                    if not bm[j][i]:
                        continue
                    x = ox + i + (0 if '가' <= c <= '힣' else xo)
                    y = 14 - (yo + gh - j)
                    if 0 <= x < band.shape[1] and 0 <= y < 16:
                        mask[y][x] = True
        ox += w
    mask[:, 1:] |= mask[:, :-1].copy()          # 굵은 획
    band[mask] = 15
    return [band[:, i*16:(i+1)*16] for i in range(W // 2)]


# ---------------------------------------------------------------- 빌드

SHIFT = {7: 1}               # 원문이 가운데 정렬된 줄


def stage_list(orig):
    import glob
    ss = {os.path.basename(f).split('_')[0] for f in glob.glob(os.path.join(orig, 'S*_PACK.DAT'))}
    return sorted(ss, key=lambda s: int(s[1:]))


def build_stage(orig, outdir, st, texts, inv, kr, preview=None):
    nbgp = os.path.join(orig, f'{st}_PACK.NBG')
    datp = os.path.join(orig, f'{st}_PACK.DAT')
    cells, ncell = load_pool(nbgp)
    nbg = bytearray(open(nbgp, 'rb').read())
    dat = bytearray(open(datp, 'rb').read())
    hud, dls = find_tables(bytes(dat), ncell)
    if not (hud and dls):
        return None

    tabs = [('HUD', hud, 4), ('DLS', dls, 2)]
    recs = []                       # (idx, tag, k, tabinfo, cells[])
    for tag, tab, wd in tabs:
        for k, rec in enumerate(read_records(bytes(dat), tab[0], tab[1], wd)):
            idx = inv.get(f'{st}/{tag}/{k}')
            recs.append((idx, tag, k, (tab, wd), rec))

    used = set()
    for _, _, _, _, rec in recs:
        used.update(rec)
    lo, hi = min(used), max(used)

    # 원문 문자 → 원본 글리프 (비한글 재사용용)
    ref = {}
    for idx, _, _, _, rec in recs:
        if idx is None or idx in SKIP_IDS:
            continue
        jp = texts.get(idx, ('', ''))[0]
        sh = SHIFT.get(idx, 0)
        if not jp or len(jp) + sh > W // 2:
            continue
        for i, ch in enumerate(jp):
            ref.setdefault(ch, glyph_at(cells, rec, sh + i))

    # 번역 안 하는 줄이 쓰는 셀은 예약
    reserved = set()
    for idx, _, _, _, rec in recs:
        if idx is None or idx in SKIP_IDS:
            reserved.update(rec)

    # 필요한 문자 집합
    need = []
    band = {}
    for idx, _, _, _, rec in recs:
        if idx is None or idx in SKIP_IDS:
            continue
        if idx == BAND_ID:
            for i, t in enumerate(band_tiles(cells, rec, kr)):
                key = '§B%d' % i
                band[key] = t
                if key not in need:
                    need.append(key)
            continue
        ko = texts[idx][1]
        for ch in ko:
            if ch not in need:
                need.append(ch)
    if '　' not in need:
        need.append('　')

    # 글리프 픽셀 만들기
    pix, missing = {}, []
    for ch in need:
        if ch in band:
            pix[ch] = band[ch]
        elif '가' <= ch <= '힣':
            m, ok = kr.bitmap(ch)
            if not ok or not m.any():
                missing.append(ch)
            pix[ch] = shade(m)
        elif ch in ref:
            pix[ch] = ref[ch]
        elif ch in ('　', ' '):
            pix[ch] = np.zeros((16, 16), np.uint8)
        else:
            m, ok = kr.bitmap(ch)
            if not m.any():
                missing.append(ch)
            pix[ch] = shade(m)

    # 셀 배치 — 예약 셀을 피해 4칸 연속으로
    free = [c for c in range(lo, hi + 1) if c not in reserved]
    slots, i = {}, 0
    for ch in need:
        while i + 3 < len(free) and not (free[i+1] == free[i]+1 and
                                         free[i+2] == free[i]+2 and
                                         free[i+3] == free[i]+3):
            i += 1
        if i + 3 >= len(free):
            raise SystemExit(f'{st}: 셀 부족 (필요 {len(need)*4}, 가용 {len(free)})')
        base = free[i]
        slots[ch] = base
        i += 4

    # NBG 기록
    def put(cellno, block):
        o = cellno * CELL
        b = block.reshape(-1)
        packed = ((b[0::2] << 4) | b[1::2]).astype(np.uint8).tobytes()
        nbg[o:o + CELL] = packed

    for ch, base in slots.items():
        g = pix[ch]
        put(base + 0, g[:8, :8])
        put(base + 1, g[:8, 8:])
        put(base + 2, g[8:, :8])
        put(base + 3, g[8:, 8:])

    # 레코드 갱신
    nrec = 0
    for idx, tag, k, (tab, wd), rec in recs:
        if idx is None or idx in SKIP_IDS:
            continue
        if idx == BAND_ID:
            line = ['§B%d' % i for i in range(W // 2)]
        else:
            ko = texts[idx][1]
            sh = SHIFT.get(idx, 0)
            line = ('　' * sh + ko).ljust(W // 2, '　')[:W // 2]
        base_off = tab[0] + k * (REC4 if wd == 4 else REC2)
        for i, ch in enumerate(line):
            b = slots[ch]
            if wd == 4:
                struct.pack_into('>H', dat, base_off + (i*2)*4 + 2, b)
                struct.pack_into('>H', dat, base_off + (i*2+1)*4 + 2, b + 1)
                struct.pack_into('>H', dat, base_off + (W + i*2)*4 + 2, b + 2)
                struct.pack_into('>H', dat, base_off + (W + i*2+1)*4 + 2, b + 3)
            else:
                struct.pack_into('>H', dat, base_off + (i*2)*2, b)
                struct.pack_into('>H', dat, base_off + (i*2+1)*2, b + 1)
                struct.pack_into('>H', dat, base_off + (W + i*2)*2, b + 2)
                struct.pack_into('>H', dat, base_off + (W + i*2+1)*2, b + 3)
        nrec += 1

    os.makedirs(outdir, exist_ok=True)
    open(os.path.join(outdir, f'{st}_PACK.NBG'), 'wb').write(bytes(nbg))
    open(os.path.join(outdir, f'{st}_PACK.DAT'), 'wb').write(bytes(dat))
    return dict(stage=st, recs=nrec, chars=len(need), cells=len(need)*4,
                free=len(free), missing=missing, lo=lo, hi=hi)


def main():
    orig = os.path.join(common.WORK, 'orig')
    outdir = os.path.join(common.WORK, 'ingame_build')
    texts = load_tsv(os.path.join(common.WORK, 'trans', 'ingame_ko.tsv'))
    use = json.load(open(os.path.join(common.WORK, 'trans', 'ig_lines_use.json'),
                        encoding='utf-8'))
    inv = {}
    for k, v in use.items():
        for s in v:
            inv[s] = int(k)
    kr = KrGlyphs(BDF)
    for st in stage_list(orig):
        r = build_stage(orig, outdir, st, texts, inv, kr)
        if r is None:
            print(f'{st}: 표 없음 — 건너뜀')
            continue
        print(f"{r['stage']:4} 레코드 {r['recs']:3}  문자 {r['chars']:3} "
              f"({r['cells']}셀 / 가용 {r['free']})  "
              f"풀 0x{r['lo']:X}~0x{r['hi']:X}"
              + (f"  ⚠결손 {''.join(r['missing'])}" if r['missing'] else ''))


if __name__ == '__main__':
    main()
