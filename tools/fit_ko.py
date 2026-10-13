# -*- coding: utf-8 -*-
"""번역문 조판 — 전각 변환 + **23자 어절 단위 줄바꿈**.

원본 렌더러는 23자에서 «단어 도중이든 말든» 그냥 자른다([[project_gungriffon2_kr]]).
그래서 미리 어절 경계에 `{0A}{0B}` 를 넣어 두어야 읽을 만한 화면이 나온다.

입력  work/trans/ko.tsv     (ASCII 로 편하게 적은 번역문)
출력  work/trans/ko_fit.tsv (전각 + 줄바꿈 삽입 = 삽입용 최종본)
"""
import os, sys, csv, io, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

COLS = 23      # 렌더러 한계 (실측)
WRAP = 22      # ★조판 폭은 한 칸 낮춘다 — 꽉 찬 23자 줄 뒤에 명시 개행이 오면
               #  즉시개행/지연개행 구현에 따라 «빈 줄»이 낄 수 있어서다(실기 미확인).
BR = '{0A}{0B}'
SP = '　'


def to_fullwidth(s):
    out = []
    for ch in s:
        if ch == ' ':
            out.append(SP)
        elif 0x21 <= ord(ch) <= 0x7E:
            out.append(chr(ord(ch) + 0xFEE0))
        else:
            out.append(ch)
    return ''.join(out)


def wrap(par, cols=WRAP):
    """어절 단위 줄바꿈. 어절 하나가 cols 를 넘으면 그때만 강제 절단.

    ★마지막 줄이 «정확히 cols 자»가 되지 않게 한다 — 뒤에 명시 `{0A}{0B}` 가 오면
      렌더러가 즉시개행이냐 지연개행이냐에 따라 **빈 줄이 하나 낄 수 있다**.
      어느 쪽인지 실기로 확인하기 전까지는 그 상황을 아예 만들지 않는다.
    """
    if len(par) <= cols:
        return [par]
    # 선두 공백(의도적 들여쓰기)은 첫 어절에 붙여 보존
    lead = len(par) - len(par.lstrip(SP))
    words = par[lead:].split(SP)
    if lead:
        words[0] = SP * lead + words[0]
    lines, cur = [], ''
    for w in words:
        while len(w) > cols:                    # 한 어절이 줄보다 길다
            if cur:
                lines.append(cur); cur = ''
            lines.append(w[:cols]); w = w[cols:]
        cand = w if not cur else cur + SP + w
        if len(cand) <= cols:
            cur = cand
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def fit(text):
    """전각 변환만 한다. **줄바꿈은 넣지 않는다.**

    ★★문자열은 런타임에 «이어 붙는다»(브리핑 115+116, 무기 이름+설명 …).
      그래서 문자열마다 따로 줄바꿈을 넣으면 이어 붙은 뒤 엉뚱한 자리에 떨어져
      토막 줄과 빈칸이 생긴다(2026-08-09 실기). 원문처럼 **게임의 23자 자동
      줄바꿈에 맡기고**, 원문에 있던 `{0A}{0B}` 만 그대로 둔다.

    ⚠️ 전각 변환을 문자열 전체에 걸면 토큰까지 `｛０Ａ｝` 가 된다 — 겪음.
    """
    return BR.join(squeeze(to_fullwidth(p)) for p in text.split(BR))


# ★전프로젝트 규칙(표준 목록 전부): 문장부호 뒤 공백 1칸(반각·전각) 삭제 — 블루 시드 tools/build.py squeeze() 그대로(2026-10-13 적용)
PUNCT = (",.!?:;)]}'\"~"
         '、。，．！？：；）］｝」』】〉》”’…‥・·～〜♪♥')


def squeeze(t):
    import re
    return re.sub('([' + re.escape(PUNCT) + '])[ 　](?![ 　])', r'\1', t)


def main():
    src = os.path.join(common.WORK, 'trans', 'ko.tsv')
    rows = list(csv.reader(io.StringIO(open(src, encoding='utf-8').read()),
                           delimiter='\t'))[1:]

    out, hard, syll, bad = [], [], set(), []
    for rid, ko in rows:
        ft = fit(ko)
        out.append((rid, ft))
        for ln in ft.split(BR):
            if len(ln) > COLS:
                bad.append((rid, ln))
        for ch in ft.replace(BR, ''):
            if '가' <= ch <= '힣':
                syll.add(ch)
            else:
                try:
                    ch.encode('cp932')
                except UnicodeEncodeError:
                    hard.append((rid, ch))

    p = os.path.join(common.WORK, 'trans', 'ko_fit.tsv')
    with open(p, 'w', encoding='utf-8', newline='') as f:
        f.write('id\tko\n')
        for rid, t in out:
            f.write('%s\t%s\n' % (rid, t))

    # ★★검산 단위는 문자열이 아니라 **박스**다.
    #   한 박스에 여러 문자열이 이어 그려지므로(포인터 표 한 블록 = 한 박스),
    #   블록 «합계» 줄 수를 원문과 비교해야 한다. 문자열 단위로 비교하면
    #   블록 안에서 서로 상쇄돼 실제 넘침을 못 잡는다(2026-08-09 실기).
    from render_sim import layout
    jr = list(csv.DictReader(io.StringIO(open(
        os.path.join(common.WORK, 'trans', 'text_jp.tsv'),
        encoding='utf-8').read()), delimiter='\t'))
    jp = {r['id']: r['jp'] for r in jr}
    kod = dict(out)
    ent = sorted((int(r['refs'].split(',')[0], 16), r['id'])
                 for r in jr if r['refs'] and r['id'] in kod)
    blocks, cur_b = [], [ent[0]]
    for a, b in zip(ent, ent[1:]):
        if b[0] - a[0] <= 8:            # 표 stride = 8 B
            cur_b.append(b)
        else:
            blocks.append(cur_b); cur_b = [b]
    blocks.append(cur_b)
    over = []
    for blk in blocks:
        ids = [i for _, i in blk]
        a = sum(len(layout(jp[i])) for i in ids)
        b = sum(len(layout(kod[i])) for i in ids)
        if b > a:
            over.append((b - a, a, b, ','.join(ids)))
    over.sort(reverse=True)

    print('항목 %d개 → %s' % (len(out), p))
    print('cp932 불가(한글 외): %s' % (sorted(set(c for _, c in hard)) or '없음'))
    print('고유 한글 음절: %d자  (뱅크C 여유 3,379)' % len(syll))
    print('총 바이트(2B/자 가정): %d' % sum(
        len(t.replace(BR, '')) * 2 for _, t in out))
    print('★원문보다 줄이 늘어난 항목: %d개 (초과 %d줄)'
          % (len(over), sum(d for d, _, _, _ in over)))
    for d, a, b, rid in over[:40]:
        print('   id=%-4s %2d → %2d줄 (+%d)' % (rid, a, b, d))


if __name__ == '__main__':
    main()
