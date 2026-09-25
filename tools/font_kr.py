# -*- coding: utf-8 -*-
"""한글 글리프 슬롯 배정 + 인코더.

**뱅크C(제2수준 한자, 3,390슬롯)를 한글에 쓴다.** 게임이 실제로 쓰는 건 11자뿐이라
매핑표를 손대지 않고 «코드 그대로» 한글을 넣을 수 있다.

글리프 소스 = Galmuri11 **BDF 직독**([[feedback_pixel_font_use_bdf_not_ttf]]).
"""
import os, sys, csv, io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
from font_test_kr import GameFont, KrFont, MOD2, CELL, next_sjis
from fit_ko import BR

BANK_C = 2
FREE_START = 0x179BA        # 뱅크A 인덱스 209(ぁ) — 여기부터 뱅크B 끝까지가 여유 공간
FREE_END = 0x293C6          # (영문팀이 실증한 구역을 «내 폰트 해독으로» 다시 계산한 값)
MAX_A_INDEX = 208           # ｚ. 이보다 큰 뱅크A 인덱스나 뱅크B 글자를 쓰면 안 된다


def code_of(gf, bank, index):
    """인덱스 → SJIS 코드 (index_of 의 역함수)."""
    fp, recs = gf.banks[bank]
    rec = None
    for c, i in recs:
        if i <= index:
            rec = (c, i)
        else:
            break
    c, i = rec
    while i < index:
        c = next_sjis(c)
        i += 1
    return c


def used_c_indices(gf):
    """원본 텍스트가 실제로 쓰는 뱅크C 인덱스 — 덮어쓰지 않는다."""
    used = set()
    for r in csv.DictReader(io.StringIO(open(os.path.join(
            common.WORK, 'trans', 'text_jp.tsv'), encoding='utf-8').read()),
            delimiter='\t'):
        for ch in r['jp']:
            try:
                sj = ch.encode('cp932')
            except UnicodeEncodeError:
                continue
            if len(sj) != 2:
                continue
            code = (sj[0] << 8) | sj[1]
            if code >= 0x989F:
                idx = gf.index_of(BANK_C, code)
                if idx is not None:
                    used.add(idx)
    return used


def build_map(gf, syllables):
    """음절 → (뱅크C 인덱스, SJIS 코드). 쓰는 슬롯을 피해 앞에서부터 채운다."""
    skip = used_c_indices(gf)
    # ★인덱스 0(코드 0x989F)은 **뱅크B/C 경계**라 쓰지 않는다.
    #   게임이 이 코드를 뱅크B 끝(인덱스 2965)으로 읽으면 글리프를 2바이트 앞에서
    #   집어 «한 행 밀린 그림»이 나온다 — 2026-08-09 실기에서 「가」만 깨졌다.
    skip.add(0)
    nslot = 3390
    free = (i for i in range(nslot) if i not in skip)
    m = {}
    for ch in sorted(syllables):
        i = next(free)
        m[ch] = (i, code_of(gf, BANK_C, i))
    return m


def load_ko():
    return dict(list(csv.reader(io.StringIO(open(os.path.join(
        common.WORK, 'trans', 'ko_fit.tsv'), encoding='utf-8').read()),
        delimiter='\t'))[1:])


def syllables_of(texts):
    s = set()
    for t in texts:
        for ch in t.replace(BR, ''):
            if '가' <= ch <= '힣':
                s.add(ch)
    return s


def encode(text, kmap, gf):
    """번역문 → 삽입 바이트열. 토큰 `{0A}{0B}` 는 0x0A 0x0B 로."""
    out = bytearray()
    i = 0
    while i < len(text):
        if text.startswith(BR, i):
            out += b'\x0a\x0b'
            i += len(BR)
            continue
        ch = text[i]
        i += 1
        if ch in kmap:
            code = kmap[ch][1]
            out += bytes([code >> 8, code & 0xFF])
        else:
            sj = ch.encode('cp932')
            if len(sj) != 2:
                raise ValueError('2바이트가 아닌 글자: %r' % ch)
            code = (sj[0] << 8) | sj[1]
            # ⛔ 덮어쓸 구역(뱅크A 209~ / 뱅크B)의 글자는 쓰면 안 된다
            if code >= 0x889F:
                raise ValueError('한자/가나를 썼다: %r' % ch)
            idx = gf.index_of(0, code)
            if idx is None or idx > MAX_A_INDEX:
                raise ValueError('뱅크A 인덱스 %s 초과: %r' % (idx, ch))
            out += sj
    return bytes(out)


def bake(data, gf, kmap, kf):
    """뱅크C 폰트 자리에 한글 글리프(11×11 / 22B)를 굽는다."""
    fp = gf.banks[BANK_C][0]
    n = 0
    for ch, (idx, _code) in kmap.items():
        rows, clipped = kf.glyph(ch)
        if clipped:
            raise ValueError('셀 밖으로 나가는 글리프: %r' % ch)
        g = bytearray()
        for y in range(CELL):
            w = 0
            for x in range(CELL):
                if rows[y][x]:
                    w |= 1 << (15 - x)
            g += bytes([w >> 8, w & 0xFF])
        off = fp + idx * 22
        data[off:off + 22] = g
        n += 1
    return n
