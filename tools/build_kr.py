# -*- coding: utf-8 -*-
"""건그리폰 II 한글 패치 빌드.

  1. `/2` 를 원본 트랙에서 읽는다
  2. **뱅크C** 자리에 한글 글리프를 굽는다 (11×11 / 22B)
  3. 번역문을 인코딩해 **여유 구역(뱅크A 209~ + 뱅크B, 72KB)** 에 전부 재배치
  4. 문자열마다 **모든 BE32 참조**를 새 주소로 고쳐 쓴다
  5. `/2` 를 제자리 기록(EDC/ECC 재계산) → 되읽기 검증 → 패치 트랙 + xdelta

⚠️ 원본 일본어 문자열은 «그대로 둔다». 내가 못 찾은 참조가 남아 있어도
   쓰레기가 아니라 원문이 나오게 하려는 것이다.
"""
import os, sys, csv, io, struct, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common, iso9660
from font_test_kr import GameFont, KrFont, MOD2
from font_kr import (build_map, load_ko, syllables_of, encode, bake,
                     FREE_START, FREE_END, code_of, BANK_C)
from fit_ko import BR

LOAD_BASE = 0x0600E800


def main():
    buf = iso9660.load_track(common.TRACK1)
    data = bytearray(iso9660.read_file(buf, '/2'))
    orig = bytes(data)

    gf = GameFont(MOD2)
    kf = KrFont('Galmuri11', 'Galmuri11.ttf', 11)
    ko = load_ko()
    jp = {r['id']: r for r in csv.DictReader(io.StringIO(open(os.path.join(
        common.WORK, 'trans', 'text_jp.tsv'), encoding='utf-8').read()),
        delimiter='\t')}

    # ── 1) 글리프 ────────────────────────────────────────────────
    kmap = build_map(gf, syllables_of(ko.values()))
    nglyph = bake(data, gf, kmap, kf)
    print('글리프 %d자 구움 (뱅크C 인덱스 %d~%d)'
          % (nglyph, min(v[0] for v in kmap.values()),
             max(v[0] for v in kmap.values())))
    with open(os.path.join(common.WORK, 'trans', 'kr_map.tsv'), 'w',
              encoding='utf-8', newline='') as f:
        f.write('syllable\tindex\tsjis\n')
        for ch, (i, c) in sorted(kmap.items()):
            f.write('%s\t%d\t0x%04X\n' % (ch, i, c))

    # ── 2) 문자열 재배치 ─────────────────────────────────────────
    # ★★종단자는 «두 개» 다. 원본이 전부 `00 00` 으로 끊어 놨다(실측).
    #   렌더러는 널 하나 뒤에 또 널이 와야 멈춘다 — 하나만 쓰면 **다음 문자열까지
    #   줄줄이 이어 그린다**(2026-08-09 실기에서 무기 설명이 다음 항목까지 흘렀다).
    cur = FREE_START
    npat = nref = 0
    for rid, text in ko.items():
        blob = encode(text, kmap, gf) + b'\x00\x00'
        assert len(blob) % 2 == 0, '문자열이 2바이트 정렬이 아니다'
        if cur + len(blob) > FREE_END:
            raise RuntimeError('여유 구역 초과')
        data[cur:cur + len(blob)] = blob
        addr = LOAD_BASE + cur
        for r in jp[rid]['refs'].split(','):
            if not r:
                continue
            o = int(r, 16)
            assert struct.unpack_from('>I', orig, o)[0] == LOAD_BASE + int(
                jp[rid]['off'], 16), 'id=%s 참조 %s 가 원본과 다르다' % (rid, r)
            struct.pack_into('>I', data, o, addr)
            nref += 1
        cur += len(blob)
        npat += 1
    print('문자열 %d개 재배치 / 포인터 %d개 갱신' % (npat, nref))
    print('사용 %d B / 여유 %d B (남은 %d B)'
          % (cur - FREE_START, FREE_END - FREE_START, FREE_END - cur))

    # ── 3) 안전 점검 ─────────────────────────────────────────────
    assert len(data) == len(orig), '모듈 크기가 바뀌었다'
    for a, b, name in ((0, gf.banks[0][0] + 209 * 22, '코드·텍스트 구역'),
                       (gf.banks[2][0] + 3390 * 22, len(orig), '뱅크C 뒤')):
        diff = [o for o in range(a, b) if data[o] != orig[o]]
        touched = set()
        for o in diff:
            touched.add(o)
        if name == '코드·텍스트 구역':
            # 이 구역에서 바뀌어도 되는 건 «포인터 4바이트» 뿐이다
            allowed = set()
            for rid in ko:
                for r in jp[rid]['refs'].split(','):
                    if r:
                        allowed |= set(range(int(r, 16), int(r, 16) + 4))
            bad = touched - allowed
            assert not bad, '허용 안 된 변경 %d B (예: %s)' % (
                len(bad), [hex(x) for x in sorted(bad)[:8]])
            print('코드·텍스트 구역 변경 = 포인터 %d B 뿐 ✅' % len(touched))
        else:
            assert not touched, '%s 가 바뀌었다' % name

    # ── 4) 기록 ──────────────────────────────────────────────────
    iso9660.write_file(buf, '/2', bytes(data))
    back = iso9660.read_file(buf, '/2')
    assert back == bytes(data), '/2 되읽기 불일치'
    print('되읽기 검증 통과 (%d B)' % len(back))

    # ── 4b) 인게임 메시지(HUD·DLS) — `tools/build_ingame_kr.py` 산출물 ──
    #   S*_PACK.NBG(글리프 풀) + S*_PACK.DAT(셀번호 표). 크기 불변이 전제다.
    igdir = os.path.join(common.WORK, 'ingame_build')
    nig = 0
    if os.path.isdir(igdir):
        for name in sorted(os.listdir(igdir)):
            blob = open(os.path.join(igdir, name), 'rb').read()
            src = os.path.join(common.WORK, 'orig', name)
            assert len(blob) == os.path.getsize(src), '%s 크기가 바뀌었다' % name
            iso9660.write_file(buf, '/' + name, blob)
            assert iso9660.read_file(buf, '/' + name) == blob, \
                '%s 되읽기 불일치' % name
            nig += 1
        print('인게임 메시지 파일 %d개 기록·되읽기 일치 ✅' % nig)

    outbin = os.path.join(common.OUT_DIR, os.path.basename(common.TRACK1))
    with open(outbin, 'wb') as f:
        f.write(buf)
    print('패치 트랙 →', outbin, len(buf), 'B')

    dist = os.path.join(common.PROJ, 'dist')
    os.makedirs(dist, exist_ok=True)
    xd = os.path.join(dist, 'gungriffon2_kr.xdelta')
    for exe in (os.path.join(os.path.dirname(common.PROJ), 'terra-kr-patch',
                             'xdelta.exe'), 'xdelta3', 'xdelta'):
        try:
            subprocess.run([exe, '-e', '-f', '-s', common.TRACK1, outbin, xd],
                           check=True)
            print('xdelta →', xd, os.path.getsize(xd), 'B')
            break
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    else:
        print('⚠ xdelta 실행파일을 못 찾음 — 패치 트랙만 생성')


if __name__ == '__main__':
    main()
