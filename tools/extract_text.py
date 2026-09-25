# -*- coding: utf-8 -*-
"""`/2` 모듈에서 텍스트를 «포인터 참조까지 함께» 뽑는다.

  · 적재 베이스 = **0x0600E800** (스테이트 Work RAM 에서 실측 — 0x06010000 아님)
  · 텍스트 = 평문 cp932, 널 종단, 0x0A = 줄바꿈
  · 참조 = BE32 절대주소. 재배치하려면 **가리키는 곳을 전부** 알아야 한다.

산출: work/trans/text_jp.tsv
  id / 오프셋 / 주소 / 바이트 / 글자 / 참조수 / 참조위치들 / 영문(있으면) / 원문
"""
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import WORK

BASE = 0x0600E800


def load(name):
    return open(os.path.join(WORK, name), 'rb').read()


def read_str(d, off, maxlen=4096):   # ★400 이면 418B 교련 브리핑을 통째로 버린다
    """널 종단 cp932. 0x01~0x1F 는 **제어 토큰**으로 보존해 `{XX}` 로 표기한다.

    ⚠️ 0x0A(줄바꿈) 만 허용하면 `ＧＵＮ 0A 0B 00` 같은 항목이 통째로 버려진다 — 겪음.
    """
    out = []
    i = off
    nb = 0
    while i < len(d) and nb < maxlen:
        c = d[i]
        if c == 0:
            break
        if c < 0x20:
            out.append('{%02X}' % c)
            i += 1
            nb += 1
            continue
        if 0x20 <= c < 0x7F:
            out.append(chr(c))
            i += 1
            nb += 1
            continue
        if ((0x81 <= c <= 0x9F) or (0xE0 <= c <= 0xEF)) and i + 1 < len(d):
            t = d[i + 1]
            if (0x40 <= t <= 0x7E) or (0x80 <= t <= 0xFC):
                try:
                    out.append(d[i:i + 2].decode('cp932'))
                except Exception:
                    return None, 0
                i += 2
                nb += 2
                continue
        return None, 0
    if i >= len(d) or d[i] != 0:
        return None, 0
    return ''.join(out), nb


def is_text(s):
    """일본어(가나·한자·전각)를 한 글자라도 담고 있으면 번역 대상."""
    if not s or not s.strip():
        return False
    return any('぀' <= c <= 'ヿ' or '一' <= c <= '鿿'
               or '！' <= c <= '｠' or c in '　、。「」・ー' for c in s)


def main():
    jp = load('mod2_jp.bin')
    en = load('mod2_en.bin') if os.path.exists(os.path.join(WORK, 'mod2_en.bin')) else None

    # ── 1) 포인터 수집 ──────────────────────────────────────────────
    refs = {}          # 문자열 오프셋 → [참조 위치...]
    for o in range(0, len(jp) - 3, 2):
        v = struct.unpack_from('>I', jp, o)[0]
        if not (BASE <= v < BASE + len(jp)):
            continue
        t = v - BASE
        s, n = read_str(jp, t)
        if is_text(s):
            refs.setdefault(t, []).append(o)

    # ── 2) 참조된 문자열의 «앞 널» 을 찾아 진짜 시작으로 정규화 ─────
    #    ⚠️ 포인터가 문자열 «중간»을 가리키는 경우가 흔하다(원본이 그렇게 쓴다).
    #       시작을 앞당기면 다른 문자열과 뭉치므로 **가리키는 곳 그대로**를 항목으로 둔다.
    items = []
    for t in sorted(refs):
        s, n = read_str(jp, t)
        items.append({'off': t, 'text': s, 'nb': n, 'refs': refs[t]})

    # ── 3) 참조 없는 문자열은 «참조된 것을 씨앗으로 구역 확장»해서만 줍는다 ──
    #    ⛔ 맹목 스캔은 안 된다 — 폰트 글리프(0x167C4~0x3B71C)와 SH-2 코드가
    #       우연히 한자로 디코드돼 노이즈가 실제 텍스트보다 많아진다(실측 683 vs 271).
    FONT = (0x0167C4, 0x03B71C)
    have = {i['off'] for i in items}

    def grab(o):
        """o 에서 시작하는 널 종단 문자열이 «진짜 텍스트»면 추가하고 다음 위치 반환."""
        s, n = read_str(jp, o)
        if n < 2 or not is_text(s):
            return None
        if o not in have:
            items.append({'off': o, 'text': s, 'nb': n, 'refs': []})
            have.add(o)
        return o + n + 1

    for seed in sorted(refs):
        if FONT[0] <= seed < FONT[1]:
            continue
        o = seed                                   # 앞으로 확장
        while o is not None and o < FONT[0]:
            nxt = grab(o)
            if nxt is None:
                break
            while nxt < len(jp) and jp[nxt] == 0 and nxt - (o) < 4096:
                nxt += 1                            # 널 패딩 건너뛰기
                if nxt - o > 8:
                    nxt = None
                    break
            o = nxt
        o = seed                                   # 뒤로 확장
        while o is not None and o > 8:
            p = o - 2
            while p > 0 and jp[p] == 0 and o - p <= 8:
                p -= 1
            if o - p > 8:
                break
            while p > 0 and jp[p - 1] != 0:
                p -= 1
            s, n = read_str(jp, p)
            if n < 2 or not is_text(s) or p in have:
                break
            items.append({'off': p, 'text': s, 'nb': n, 'refs': []})
            have.add(p)
            o = p

    items.sort(key=lambda x: x['off'])

    # ── 4) 영문판 대응(같은 참조 위치의 포인터가 가리키는 영문) ─────
    for it in items:
        it['en'] = ''
        if not en or not it['refs']:
            continue
        for r in it['refs']:
            v = struct.unpack_from('>I', en, r)[0]
            if BASE <= v < BASE + len(en):
                s2, _ = read_str(en, v - BASE)
                if s2 and s2 != it['text']:
                    it['en'] = s2
                    break

    out = os.path.join(WORK, 'trans')
    os.makedirs(out, exist_ok=True)
    p = os.path.join(out, 'text_jp.tsv')
    with open(p, 'w', encoding='utf-8') as f:
        f.write('id\toff\taddr\tbytes\tchars\tnrefs\trefs\ten\tjp\n')
        for k, it in enumerate(items):
            f.write('%d\t0x%06X\t0x%08X\t%d\t%d\t%d\t%s\t%s\t%s\n' % (
                k, it['off'], BASE + it['off'], it['nb'], len(it['text']),
                len(it['refs']), ','.join('0x%X' % r for r in it['refs']),
                it['en'].replace('\n', '\\n'), it['text'].replace('\n', '\\n')))

    nb = sum(i['nb'] for i in items)
    nc = sum(len(i['text']) for i in items)
    withref = sum(1 for i in items if i['refs'])
    withen = sum(1 for i in items if i['en'])
    uniq = set()
    for i in items:
        uniq |= set(i['text'])
    print('문자열 %d개 (참조 있음 %d / 영문대응 %d)' % (len(items), withref, withen))
    print('%d B / %d자 / 고유문자 %d종' % (nb, nc, len(uniq)))
    print('→ %s' % p)


if __name__ == '__main__':
    main()
