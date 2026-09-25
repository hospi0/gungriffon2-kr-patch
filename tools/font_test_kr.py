# -*- coding: utf-8 -*-
"""11x11 셀에 한글이 읽히는가 — 후보 폰트 렌더 시험 (미리보기 전용, 디스크 안 건드림).

- 게임 원본 글리프(`work/orig/2`)를 되읽어 같은 셀·같은 배율로 나란히 그린다.
- 후보 픽셀폰트를 모노('1') + **고정 원점**으로 11x11 에 굽는다.
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

MOD2 = os.path.join(common.ORIG, '2')
LOAD_BASE = 0x0600E800
DESC = 0x6280          # [BE32 font][BE32 table] x 3
CELL = 11
GLYPH_BYTES = 22

FONT_DIR = os.path.join('C:' + os.sep, 'claude', 'project', 'conker-kr-patch',
                        'my folder', 'Galmuri-v2.40.3')
OUT = os.path.join(common.WORK, 'png')


# ---------------------------------------------------------------- 게임 폰트
def be32(b, o): return int.from_bytes(b[o:o + 4], 'big')
def be16(b, o): return int.from_bytes(b[o:o + 2], 'big')


def next_sjis(code):
    """유효 SJIS 2바이트 코드의 다음 값 (트레일 0x7F 건너뜀, 0xFC 넘으면 리드+1)."""
    lead, trail = code >> 8, code & 0xFF
    trail += 1
    if trail == 0x7F:
        trail += 1
    if trail > 0xFC:
        lead += 1
        trail = 0x40
    return (lead << 8) | trail


class GameFont:
    def __init__(self, path):
        self.data = open(path, 'rb').read()
        self.banks = []
        for i in range(3):
            fp = be32(self.data, DESC + i * 8) - LOAD_BASE
            tp = be32(self.data, DESC + i * 8 + 4) - LOAD_BASE
            n = be16(self.data, tp)
            recs = [(be16(self.data, tp + 2 + j * 4), be16(self.data, tp + 4 + j * 4))
                    for j in range(n)]
            self.banks.append((fp, recs))

    def index_of(self, bank, code):
        fp, recs = self.banks[bank]
        rec = None
        for c, idx in recs:
            if c <= code:
                rec = (c, idx)
            else:
                break
        if rec is None:
            return None
        c, idx = rec
        while c < code:
            c = next_sjis(c)
            idx += 1
        return idx

    def glyph(self, ch):
        """유니코드 문자 -> 11x11 비트맵(리스트[행][열]) 또는 None."""
        try:
            sj = ch.encode('cp932')
        except UnicodeEncodeError:
            return None
        if len(sj) != 2:
            return None
        code = (sj[0] << 8) | sj[1]
        bank = 0 if code < 0x889F else (1 if code < 0x989F else 2)
        idx = self.index_of(bank, code)
        if idx is None:
            return None
        fp = self.banks[bank][0]
        off = fp + idx * GLYPH_BYTES
        raw = self.data[off:off + GLYPH_BYTES]
        rows = []
        for y in range(CELL):
            w = (raw[y * 2] << 8) | raw[y * 2 + 1]
            rows.append([(w >> (15 - x)) & 1 for x in range(CELL)])
        return rows


# ---------------------------------------------------------------- 후보 폰트
CANDIDATES = [
    ('Galmuri11',            'Galmuri11.ttf',            11),
    ('GalmuriMono11',        'GalmuriMono11.ttf',        11),
    ('Galmuri11-Condensed',  'Galmuri11-Condensed.ttf',  11),
    ('Galmuri9',             'Galmuri9.ttf',              9),
    ('Galmuri7',             'Galmuri7.ttf',              7),
]

# 원점 계산용 대표 글자군: 받침 없음/있음/겹받침/모음 형태 전부
PROBE = '가힣뷁왜쓸훑짧앉밝웨긍쥐컴폰프로텍터'


class KrFont:
    """★글리프 소스 = **BDF 원본 픽셀**.

    TTF 를 11px 로 재래스터라이즈하면 픽셀폰트라도 **행·열이 통째로 탈락**한다
    (2026-08-09 실측: `종` 의 ㅈ 다리 3행, `연` 의 ㅇ 왼쪽 테두리).
    BDF 는 디자이너가 찍은 픽셀 그 자체라 재래스터라이즈가 없다.
    """
    def __init__(self, name, file, size):
        self.name, self.size = name, size
        self.glyphs = {}                       # cp -> (w, h, xoff, yoff, rows[])
        path = os.path.join(FONT_DIR, os.path.splitext(file)[0] + '.bdf')
        cp = bbx = None
        rows, reading = [], False
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
                    self.glyphs[cp] = (w, h, xo, yo, bm)
                reading = False
            elif reading and ln:
                rows.append(ln)

        # 대표 글자군으로 **고정 원점**을 한 번만 결정 (글자별 중앙정렬 금지)
        x0 = y0 = 99; x1 = y1 = -99
        for ch in PROBE:
            g = self.glyphs.get(ord(ch))
            if not g:
                continue
            w, h, xo, yo, _ = g
            x0 = min(x0, xo); x1 = max(x1, xo + w - 1)
            y0 = min(y0, yo); y1 = max(y1, yo + h - 1)   # y = 베이스라인 기준 위쪽 +
        self.ink_wh = (x1 - x0 + 1, y1 - y0 + 1)
        self.ink = (x0, y0, x1, y1)
        iw, ih = self.ink_wh
        self.ox = -x0 + max(0, (CELL - iw) // 2)
        # 셀 좌표: 위에서 아래로. 베이스라인 = 셀 상단 + (y1 + oy_pad)
        self.base = min(CELL, y1 + 1) + max(0, (CELL - ih) // 2)

    def glyph(self, ch):
        g = self.glyphs.get(ord(ch))
        out = [[0] * CELL for _ in range(CELL)]
        if not g:
            return out, True
        w, h, xo, yo, bm = g
        clipped = False
        for j in range(h):
            for i in range(w):
                if not bm[j][i]:
                    continue
                x = xo + i + self.ox
                y = self.base - (yo + h - j)      # BDF 는 아래가 +
                if 0 <= x < CELL and 0 <= y < CELL:
                    out[y][x] = 1
                else:
                    clipped = True
        return out, clipped


# ---------------------------------------------------------------- 그리기
FG = (232, 236, 240)
BG = (16, 18, 22)
GRID = (44, 48, 56)
ACC = (255, 190, 60)


def blit(img, rows, cx, cy, z, fg=FG, grid=None):
    d = ImageDraw.Draw(img)
    if grid:
        d.rectangle([cx, cy, cx + CELL * z - 1, cy + CELL * z - 1], outline=grid)
    if rows is None:
        d.line([cx, cy, cx + CELL * z - 1, cy + CELL * z - 1], fill=(140, 60, 60))
        return
    for y in range(CELL):
        for x in range(CELL):
            if rows[y][x]:
                d.rectangle([cx + x * z, cy + y * z,
                             cx + x * z + z - 1, cy + y * z + z - 1], fill=fg)


def text_row(img, glyphs, x, y, z, fg=FG, gap=0):
    for g in glyphs:
        blit(img, g, x, y, z, fg)
        x += (CELL + gap) * z
    return x


HALF2FULL = {chr(c): chr(c - 0x20 + 0xFF00) for c in range(0x21, 0x7F)}
HALF2FULL[' '] = '　'


def line_glyphs(s, gf, kf):
    """한글은 후보 폰트, 나머지는 «게임 원본 글리프»로."""
    out = []
    for ch in s:
        if '가' <= ch <= '힣':
            g, _ = kf.glyph(ch)
        else:
            g = gf.glyph(HALF2FULL.get(ch, ch))
        out.append(g)
    return out


# ---------------------------------------------------------------- 시험 자료
SYLL = ('가나다라마바사아자차카타파하'
        '각논닫릴맘밥샀앙잦찿캌탙팦핳'
        '괴귀뇌뷁쇄쐬왜웨의쥐춰퉤흯희'
        '값넋닭릺맑밟삶앉짧퉔훑읊없')

LINES = [
    # (일본어 원문, 한국어 시안)
    ('本作戦を終了します。',            '본 작전을 종료합니다.'),
    ('サバイバルモード／リレハンメル',  '서바이벌 모드／릴레함메르'),
    ('シナリオモード　ミッション１',    '시나리오 모드　미션１'),
    ('作戦は成功です！更なる進撃を続けましょう。',
     '작전 성공! 계속 진격하겠습니다.'),
    ('リプレイデータを保存する空き容量がありません。',
     '리플레이 데이터를 저장할 빈 용량이 없습니다.'),
    ('標準的火砲威力連射能力装甲',      '표준적 화포 위력 연사 능력 장갑'),
]


def label(d, x, y, s, size=22, fill=FG):
    f = ImageFont.truetype(os.path.join(FONT_DIR, 'Galmuri11.ttf'), size)
    d.fontmode = '1'
    d.text((x, y), s, font=f, fill=fill)


def build():
    os.makedirs(OUT, exist_ok=True)
    gf = GameFont(MOD2)
    kfs = [KrFont(*c) for c in CANDIDATES]

    # ---------- 1) 후보 폰트별 음절 격자
    Z = 6
    cols = 28
    rows_per = (len(SYLL) + cols - 1) // cols
    W = 60 + cols * (CELL + 1) * Z
    blocks = len(kfs) + 1                      # +1 = 게임 원본 한자 비교행
    H = 70 + blocks * (rows_per * (CELL + 2) * Z + 46)
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    label(d, 24, 18, '건그리폰 II — 11×11 셀 한글 렌더 시험 (확대 ×%d)' % Z, 26, ACC)

    y = 66
    for kf in kfs:
        clip = sum(kf.glyph(c)[1] for c in SYLL)
        label(d, 24, y, '%s  @%dpx   잉크 %d×%d   셀밖 잘림 %d자'
              % (kf.name, kf.size, kf.ink_wh[0], kf.ink_wh[1], clip), 20,
              (255, 120, 120) if clip else FG)
        y += 26
        x = 24
        for i, ch in enumerate(SYLL):
            if i and i % cols == 0:
                y += (CELL + 2) * Z
                x = 24
            g, cl = kf.glyph(ch)
            blit(img, g, x + (i % cols) * (CELL + 1) * Z, y, Z,
                 (255, 140, 140) if cl else FG, GRID)
        y += (CELL + 2) * Z + 20

    # 게임 원본 한자 (같은 셀·같은 배율) — 판독성 기준선
    label(d, 24, y, '게임 원본 글리프 (같은 11×11) — 판독성 기준선', 20, ACC)
    y += 26
    ref = '亜火標準的威力連射能装甲砲弾残機体温度速度高度距離目標敵味方全滅'
    for i, ch in enumerate(ref[:cols]):
        blit(img, gf.glyph(ch), 24 + i * (CELL + 1) * Z, y, Z, FG, GRID)
    img.save(os.path.join(OUT, 'font_test_grid.png'))

    # ---------- 2) 실기 배율 문장 대조
    Z2 = 3
    W2 = 1180
    H2 = 70 + len(LINES) * (len(kfs) + 1) * (CELL * Z2 + 8) + len(LINES) * 34 + 40
    img2 = Image.new('RGB', (W2, H2), BG)
    d2 = ImageDraw.Draw(img2)
    label(d2, 24, 18, '문장 대조 — 원문(게임 폰트) vs 한글 시안 (확대 ×%d)' % Z2, 26, ACC)
    y = 64
    for jp, kr in LINES:
        label(d2, 24, y, '원문', 18, (120, 170, 255))
        text_row(img2, [gf.glyph(c) for c in jp], 90, y, Z2, (150, 200, 255))
        y += CELL * Z2 + 8
        for kf in kfs:
            label(d2, 24, y, kf.name.replace('Galmuri', 'G'), 18, (150, 150, 160))
            text_row(img2, line_glyphs(kr, gf, kf), 90, y, Z2)
            y += CELL * Z2 + 8
        y += 26
    img2.save(os.path.join(OUT, 'font_test_lines.png'))

    # ---------- 3) 실물 크기 (×1 / ×2)
    img3 = Image.new('RGB', (720, 60 + len(kfs) * 60 + 40), BG)
    d3 = ImageDraw.Draw(img3)
    label(d3, 20, 14, '실물 크기 (×1 왼쪽 / ×2 오른쪽) — 새턴 320×224 화면 기준', 22, ACC)
    y = 58
    s_kr = '리플레이 데이터를 저장할 빈 용량이 없습니다.'
    for kf in kfs:
        label(d3, 20, y + 6, kf.name.replace('Galmuri', 'G'), 18, (150, 150, 160))
        g = line_glyphs(s_kr, gf, kf)
        text_row(img3, g, 150, y + 4, 1)
        text_row(img3, g, 150, y + 22, 2)
        y += 60
    img3 = img3.resize((img3.width * 2, img3.height * 2), Image.NEAREST)
    img3.save(os.path.join(OUT, 'font_test_actual.png'))
    print('저장:', OUT)


if __name__ == '__main__':
    build()
