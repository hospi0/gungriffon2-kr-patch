# -*- coding: utf-8 -*-
"""건그리폰 II (새턴 JP) 한글화 — 경로·상수.

⚠️ **무수정 원본은 «중첩 폴더»** 다(1편과 같은 배치).
   바깥 폴더에는 Track 02~44 와 cue 만 있고 Track 01 이 없다 → 패치 트랙 출력 자리.
"""
import os

BASE = 'Gungriffon II (Japan)'
SS_ROOT = os.path.join('F:' + os.sep, 'hospi', 'roms', 'ss roms')

# ★2026-10-13: 원본이 중첩 없이 `F:\…\Gungriffon II (Japan)\` 에 그대로 있다(사용자가 다시 넣음) → 거기서 읽기만,
#   패치 트랙은 프로젝트 work/out 으로(원본 덮어쓰기 방지).
ROM_DIR = os.path.join(SS_ROOT, BASE)          # 무수정 원본(트랙 전부 + cue)
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'work', 'out')
TRACK1 = os.path.join(ROM_DIR, '%s (Track 01).bin' % BASE)
# ★F: 의 Track 01 은 한글판으로 덮어쓴다(사용자 «덮어써», 2026-10-13) → 원본은 프로젝트에 백업해 두고 거기서 읽는다
_BK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'work', 'orig_track', '%s (Track 01).bin' % BASE)
if os.path.exists(_BK):
    TRACK1 = _BK

# 영문 팬패치(오라클). 트랙이 한 .bin 에 다 들어간 통짜 이미지 — Track 01 은 앞부분.
EN_DIR = os.path.join('C:' + os.sep, 'claude', 'roms', 'ss',
                      '%s (T-En by Gungriffon II Localization Team v0.97.5) (i)' % BASE)
EN_BIN = os.path.join(EN_DIR, os.path.basename(EN_DIR) + '.bin')

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(PROJ, 'work')
ORIG = os.path.join(WORK, 'orig')              # Track 01 에서 뽑은 파일 사본
MYFILES = os.path.join(PROJ, 'my files')       # 사용자가 준 스테이트·스크린샷

SECTOR = 2352
MODE1_USER = 2048
