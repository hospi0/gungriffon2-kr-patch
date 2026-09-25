# -*- coding: utf-8 -*-
"""빌드 검증 — **패치된 트랙에서 되읽어** 화면을 그린다.

빌더가 만든 비트맵을 그대로 그리는 건 자기 확인이라 검증이 아니다
([[feedback_preview_must_match_screen]]). 여기서는 패치 ISO 에서
  포인터 → 문자열 바이트 → 뱅크C 글리프 → 픽셀
전 경로를 다시 밟는다.
"""
import os, sys, csv, io, struct
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common, iso9660
from font_test_kr import GameFont, CELL, blit, FONT_DIR, FG, BG, ACC
from render_sim import layout, ADV, LINE
from fit_ko import BR

LOAD_BASE = 0x0600E800
PATCHED = os.path.join(common.OUT_DIR, os.path.basename(common.TRACK1))
Z = 3


class PatchedFont(GameFont):
    """패치본 바이트로 만든 폰트 — 글리프를 «디스크에서» 되읽는다."""
    def __init__(self, data):
        self.data = data
        self.banks = []
        for i in range(3):
            fp = struct.unpack_from('>I', data, 0x6280 + i * 8)[0] - LOAD_BASE
            tp = struct.unpack_from('>I', data, 0x6284 + i * 8)[0] - LOAD_BASE
            n = struct.unpack_from('>H', data, tp)[0]
            recs = [struct.unpack_from('>HH', data, tp + 2 + j * 4)
                    for j in range(n)]
            self.banks.append((fp, recs))


def read_string(data, addr):
    off = addr - LOAD_BASE
    end = data.index(b'\x00', off)
    return data[off:end]


def main():
    buf = iso9660.load_track(PATCHED)
    data = iso9660.read_file(buf, '/2')
    print('패치 트랙에서 /2 읽음: %d B' % len(data))

    font = PatchedFont(data)
    inv = {}
    for r in csv.DictReader(io.StringIO(open(os.path.join(
            common.WORK, 'trans', 'kr_map.tsv'), encoding='utf-8').read()),
            delimiter='\t'):
        inv[int(r['sjis'], 16)] = r['syllable']
    jp = {r['id']: r for r in csv.DictReader(io.StringIO(open(os.path.join(
        common.WORK, 'trans', 'text_jp.tsv'), encoding='utf-8').read()),
        delimiter='\t')}
    ko = dict(list(csv.reader(io.StringIO(open(os.path.join(
        common.WORK, 'trans', 'ko_fit.tsv'), encoding='utf-8').read()),
        delimiter='\t'))[1:])

    # ── 전 항목: 포인터를 따라가 문자열을 되읽고 번역문과 대조 ──
    def decode(b):
        out, i = [], 0
        while i < len(b):
            if b[i] == 0x0A and b[i + 1] == 0x0B:
                out.append(BR); i += 2; continue
            c = (b[i] << 8) | b[i + 1]
            out.append(inv[c] if c in inv else bytes(b[i:i + 2]).decode('cp932'))
            i += 2
        return ''.join(out)

    bad = 0
    for rid, text in ko.items():
        ref = jp[rid]['refs'].split(',')[0]
        addr = struct.unpack_from('>I', data, int(ref, 16))[0]
        if decode(read_string(data, addr)) != text:
            bad += 1
            print('  ✗ id=%s' % rid)
    print('포인터 되읽기 대조: %d/%d 일치' % (len(ko) - bad, len(ko)))

    # ── 글리프도 디스크에서 되읽어 그린다 ──
    ids = sys.argv[1:] or ['117', '62', '215', '201']
    rows = []
    for rid in ids:
        ref = jp[rid]['refs'].split(',')[0]
        addr = struct.unpack_from('>I', data, int(ref, 16))[0]
        rows.append((rid, addr, layout(decode(read_string(data, addr)))))

    W = 23 * ADV * Z + 40
    H = 40 + sum(30 + len(l) * LINE * Z + 20 for _, _, l in rows)
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(os.path.join(FONT_DIR, 'Galmuri11.ttf'), 20)
    d.fontmode = '1'
    y = 12
    for rid, addr, lines in rows:
        d.text((16, y), 'id=%s  ← 포인터가 가리키는 0x%08X' % (rid, addr),
               font=f, fill=ACC)
        y += 26
        fwd = {v: k for k, v in inv.items()}        # 음절 → 뱅크C 코드
        for r, ln in enumerate(lines):
            for c, ch in enumerate(ln):
                code = fwd.get(ch)
                if code is None:
                    sj = ch.encode('cp932')
                    code = (sj[0] << 8) | sj[1]
                blit(img, _glyph_by_code(font, code),
                     16 + c * ADV * Z, y + r * LINE * Z, Z)
        y += len(lines) * LINE * Z + 20
    out = os.path.join(common.WORK, 'png', 'verify_kr.png')
    img.save(out)
    print('→', out)


def _glyph_by_code(font, code):
    bank = 0 if code < 0x889F else (1 if code < 0x989F else 2)
    idx = font.index_of(bank, code)
    fp = font.banks[bank][0]
    raw = font.data[fp + idx * 22:fp + idx * 22 + 22]
    return [[((raw[y * 2] << 8 | raw[y * 2 + 1]) >> (15 - x)) & 1
             for x in range(CELL)] for y in range(CELL)]


if __name__ == '__main__':
    main()
