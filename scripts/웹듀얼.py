"""브라우저로 두는 뉴 네오 듀얼 — 혼자서도, 둘이서도.

    python scripts/웹듀얼.py                      # 나 vs AI(필터), 브라우저가 열린다
    python scripts/웹듀얼.py --공개               # 같은 네트워크의 다른 사람도 들어온다
    python scripts/웹듀얼.py --포트 8777 --최대인원 5

**규칙은 여기 없다.** 합법수는 `engine/legalmoves.py`, 적용은 `engine/turn.py`, 효과는
`engine/effects.py`, 방·자리는 `engine/room.py`, 보드 스냅샷은 `engine/view.py` 가 한다 —
이 파일은 HTTP 로 주고받고 HTML 을 내놓을 뿐이다. 로직을 자바스크립트로 옮기면 정본이
둘이 되므로 옮기지 않았다.

화면 배치는 **룰지 0장 「자신 쪽 필드의 배치 예시」 그대로**다.

    [스킬존] [유닛1][유닛2][유닛3][유닛4][유닛5] [아카이브][공허]
      (빈)   [이펙1][이펙2][이펙3][이펙4][이펙5] [메인덱][상급덱]

필드 존(0-7) · 공유 존(0-5)은 두 플레이어 사이 가운데 줄에 한 칸씩 놓인다.

**인원 상한 5명** — 한 방에 플레이어 2 + 관전 3, 서버 전체도 5다(사용자 지시).
`--공개` 는 0.0.0.0 에 바인딩한다. 인터넷 너머 사람을 부르려면 Tailscale 같은 터널을
쓰고, 이 서버를 공인 IP 에 그냥 열지는 마라 — 인증이 없다.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.room import 덱목록, 방장부, 카드목록

쪽_HTML = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>뉴 네오 듀얼</title>
<style>
:root{
  --바탕:#efe9dd; --판:#fffdf7; --글:#231e18; --흐림:#6d6358; --선:#d9cfbe;
  --매트:#2b4a3a; --매트선:#3f6550; --내쪽:#2f6f4f; --상대쪽:#8c3b3b;
  --강조:#b07d2b; --카운터:#d2a03c; --그림자:0 1px 2px rgba(0,0,0,.07),0 6px 18px rgba(0,0,0,.06);
  --적:#b4453c; --녹:#3f8a52; --황:#c39a2a; --청:#3a6ea8; --자:#7b4a9c; --백:#8d8578; --흑:#3b3a40;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --바탕:#14131a; --판:#1e1c24; --글:#ebe6df; --흐림:#978d83; --선:#38333f;
  --매트:#17302a; --매트선:#27483c; --내쪽:#5fbd8c; --상대쪽:#d8766f;
  --강조:#e0b05a; --카운터:#e0b05a; --그림자:0 1px 2px rgba(0,0,0,.5),0 6px 20px rgba(0,0,0,.35);
  --적:#e0675c; --녹:#5fbd8c; --황:#e0b05a; --청:#6fa3dd; --자:#ab7ccc; --백:#b5aca0; --흑:#8a8895;
}}
*{box-sizing:border-box}
body{margin:0;background:var(--바탕);color:var(--글);font-size:14px;line-height:1.5;
 font-family:"Pretendard","Apple SD Gothic Neo","Malgun Gothic",system-ui,sans-serif}
button{font:inherit;color:inherit;background:var(--판);border:1px solid var(--선);
 border-radius:8px;padding:7px 11px;cursor:pointer;transition:.12s;text-align:left}
button:hover{border-color:var(--강조)}
button.주{background:var(--강조);color:#1a1510;border-color:transparent;font-weight:700}
button.위험{color:var(--상대쪽)}
input,select{font:inherit;color:inherit;background:var(--판);border:1px solid var(--선);
 border-radius:8px;padding:7px 9px}
.숨김{display:none!important}

/* ---------- 바깥 화면(메인 · 시작 · 열람 · 설정) ---------- */
.바깥{max-width:660px;margin:6vh auto;padding:0 18px}
.바깥.넓게{max-width:1200px;margin:3vh auto}
.바깥 h1{font-size:28px;margin:0 0 4px;letter-spacing:.01em}
.바깥 h1::after{content:"";display:block;width:44px;height:3px;border-radius:2px;
 background:var(--강조);margin-top:8px}
.바깥 p{color:var(--흐림);margin:10px 0 22px}
.바깥 h2{font-size:17px;margin:0}
.머리줄{display:flex;align-items:center;gap:12px;margin-bottom:14px}
.큰메뉴{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;
 margin-bottom:16px}
.메뉴쪽{display:flex;flex-direction:column;gap:3px;align-items:flex-start;
 padding:15px 16px;border-radius:12px;background:var(--판);box-shadow:var(--그림자)}
.메뉴쪽 b{font-size:15px} .메뉴쪽 span{font-size:11.5px;color:var(--흐림)}
.메뉴쪽:hover{border-color:var(--강조);transform:translateY(-1px)}
.두쪽{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media (max-width:620px){.두쪽{grid-template-columns:1fr}}
.칸이름{display:block;font-size:12px;color:var(--흐림);margin-bottom:8px;letter-spacing:.03em}
button.큼{padding:10px 18px;font-size:14px}
.켜기{display:flex;align-items:center;gap:6px;font-size:12.5px;color:var(--흐림);min-width:0}
.열람틀{display:grid;grid-template-columns:200px minmax(0,1fr) 300px;gap:12px;
 align-items:start}
.편집틀{display:grid;grid-template-columns:minmax(0,1fr) 280px;gap:12px;align-items:start}
@media (max-width:900px){.편집틀{grid-template-columns:1fr}}
.넣줄{display:flex;align-items:center;gap:8px;padding:4px 7px;border-radius:7px;
 font-size:12.5px;cursor:pointer}
.넣줄:hover{background:var(--바탕)}
.넣줄.담음{background:rgba(176,125,43,.14)}
.넣줄 .작게{font-size:10.5px;color:var(--흐림);margin-left:auto;white-space:nowrap}
.매수{display:flex;align-items:center;gap:3px}
.매수 button{padding:1px 7px;font-size:12px;line-height:1.3;border-radius:6px}
.매수 b{min-width:14px;text-align:center;font-variant-numeric:tabular-nums}
.셈줄{display:flex;justify-content:space-between;font-size:12.5px;padding:3px 0}
.셈줄 b{font-variant-numeric:tabular-nums}
.셈줄.벗어남 b{color:var(--상대쪽)}
.저장줄{display:flex;gap:6px;align-items:center;font-size:12px;padding:4px 0;
 border-top:1px solid var(--선)}
.저장줄 span{flex:1}
@media (max-width:900px){.열람틀{grid-template-columns:1fr}}
.덱칸,.목록칸,.상세칸{max-height:72vh;overflow:auto}
.덱줄{display:flex;justify-content:space-between;align-items:baseline;gap:6px;
 padding:6px 8px;border-radius:7px;cursor:pointer;font-size:12.5px}
.덱줄:hover{background:var(--바탕)}
.덱줄.켬{background:var(--강조);color:#1a1510;font-weight:700}
.덱줄 .잔수{font-size:10.5px;opacity:.75;font-variant-numeric:tabular-nums}
.덱표{font-size:9.5px;padding:0 5px;border-radius:999px;border:1px solid var(--선);
 color:var(--흐림);margin-left:4px}
.목록줄{display:flex;gap:8px;align-items:baseline;padding:5px 7px;border-radius:7px;
 cursor:pointer;font-size:12.5px;border-left:3px solid transparent}
.목록줄:hover{background:var(--바탕)}
.목록줄.켬{background:var(--바탕);border-left-color:var(--강조)}
.목록줄 .작게{font-size:10.5px;color:var(--흐림);margin-left:auto;white-space:nowrap}
.상세칸 pre{white-space:pre-wrap;word-break:break-word;font:inherit;font-size:12px;
 line-height:1.55;margin:6px 0 0}
.상자{background:var(--판);border:1px solid var(--선);border-radius:12px;padding:16px;
 box-shadow:var(--그림자);margin-bottom:12px}
.줄{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:9px}
.줄 label{min-width:68px;color:var(--흐림);font-size:13px}
.방줄{display:flex;justify-content:space-between;align-items:center;gap:10px;
 padding:8px 0;border-top:1px solid var(--선)}

/* ---------- 대국 화면 ---------- */
/* 한 화면에 다 들어오게 — 세로 스크롤 없이 판·패·옆패널이 같이 보여야 한다.
   칸 크기는 화면 높이를 따라간다(--칸폭). 좁아지면 옆패널이 아래로 내려간다. */
.틀{display:grid;grid-template-columns:minmax(0,1fr) 330px;
 grid-template-rows:auto minmax(0,1fr);gap:10px 14px;
 height:100dvh;max-width:1500px;margin:0 auto;padding:10px 12px 12px}
@media (max-width:1040px),(max-height:620px){
  .틀{grid-template-columns:minmax(0,1fr);height:auto}
}
.윗띠{grid-column:1/-1;display:flex;align-items:center;gap:12px;flex-wrap:wrap;
 padding-bottom:7px;border-bottom:1px solid var(--선)}
.윗띠 b{font-size:15px}
.판판{display:flex;flex-direction:column;gap:8px;min-height:0;min-width:0;
 align-items:center;justify-content:center;overflow:auto}
.덱경고{font-size:11px;color:var(--상대쪽)}
.조절{display:flex;gap:4px;align-items:center;margin-left:auto}
.조절 button{padding:4px 9px;font-size:12px;border-radius:7px}
.조절 .켬{background:var(--강조);color:#1a1510;border-color:transparent;font-weight:700}
.조절 .칸막이{width:1px;height:18px;background:var(--선);margin:0 3px}
.단계띠{display:flex;gap:4px}
.단계알{font-size:11px;padding:2px 9px;border-radius:999px;border:1px solid var(--선);
 color:var(--흐림)}
.단계알.켬{background:var(--강조);color:#1a1510;border-color:transparent;font-weight:700}

.매트{position:relative;background:var(--매트);border:1px solid var(--매트선);border-radius:12px;
 padding:9px 10px;box-shadow:var(--그림자);display:flex;flex-direction:column;gap:6px;
 width:fit-content;max-width:100%}
.쪽머리{display:flex;align-items:center;gap:10px;flex-wrap:wrap;color:#eee}
.딱지{font-weight:700;font-size:12px;padding:2px 9px;border-radius:999px;color:#fff}
.나쪽 .딱지{background:var(--내쪽)} .적쪽 .딱지{background:var(--상대쪽)}
.hp{font-size:21px;font-weight:700;font-variant-numeric:tabular-nums;color:#fff}
.hp바{flex:1;min-width:80px;height:6px;border-radius:3px;background:rgba(255,255,255,.18);
 overflow:hidden}
.hp바 i{display:block;height:100%;transition:width .35s}
.나쪽 .hp바 i{background:var(--내쪽)} .적쪽 .hp바 i{background:var(--상대쪽)}
.잔{color:rgba(255,255,255,.65);font-size:12px;font-variant-numeric:tabular-nums}

/* 룰지 0장 배치: 8칸 × 2줄. 칸 크기는 화면 높이에 맞춰 줄었다 늘었다 한다. */
:root{--칸폭:clamp(46px,min(6.4vw,10.2vh),88px)}
.필드{display:grid;grid-template-columns:repeat(8,var(--칸폭));gap:5px;justify-content:center}
.가운데자리{display:flex;justify-content:center}
.가운데줄{display:flex;align-items:center;gap:6px;
 background:var(--판);border:1px solid var(--선);border-radius:10px;padding:5px 10px;
 box-shadow:var(--그림자)}
.가운데줄 .라벨{font-size:10.5px;color:var(--흐림);letter-spacing:.03em}
.가운데줄 .칸{width:calc(var(--칸폭) * .8)}
.칸{aspect-ratio:59/86;border:1px dashed var(--매트선);border-radius:7px;position:relative;
 display:flex;flex-direction:column;justify-content:center;align-items:center;
 font-size:9.5px;color:rgba(255,255,255,.38);text-align:center;padding:3px;overflow:hidden}
.칸.빈{opacity:.5}
.칸.빈:empty{opacity:.3}
.칸.더미{border-style:solid;background:rgba(0,0,0,.18);color:rgba(255,255,255,.72);
 cursor:pointer;justify-content:center;gap:2px}
.칸.더미 .수{font-size:17px;font-weight:700;font-variant-numeric:tabular-nums}
.칸.더미 .이{font-size:9.5px;letter-spacing:.04em}
.카드{border-style:solid;border-width:1px;background:var(--판);color:var(--글);
 justify-content:space-between;align-items:stretch;cursor:pointer;
 border-left-width:4px}
.카드 .명{font-size:10px;font-weight:600;line-height:1.22;text-align:left;
 overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical}
.카드 .밑{display:flex;justify-content:space-between;font-size:9.5px;color:var(--흐림);
 font-variant-numeric:tabular-nums}
.카드.뒤{background:repeating-linear-gradient(45deg,#3a3f52,#3a3f52 5px,#2f3344 5px,#2f3344 10px);
 border-color:#4a506a}
.카드.수비{transform:rotate(0deg)} .카드.수비 .밑::after{content:"수비"}
.카드.고름{outline:2px solid var(--강조);outline-offset:1px}

/* 카드게임다운 움직임 둘 — 카드가 판에 놓일 때, 그리고 맞을 때.
   수를 가리거나 늦추지 않는다(애니메이션은 0.4초 안에 끝나고 판정과 무관하다). */
@keyframes 내려놓기{
  0%  {transform:translateY(-14px) scale(.86) rotate(-4deg);opacity:0}
  60% {transform:translateY(2px)   scale(1.04) rotate(0);   opacity:1}
  100%{transform:none;opacity:1}
}
.카드.갓놓임{animation:내려놓기 .34s cubic-bezier(.2,.9,.3,1.2)}
@keyframes 맞음{
  0%,100%{transform:none}
  18%{transform:translateX(-5px)} 38%{transform:translateX(5px)}
  58%{transform:translateX(-3px)} 78%{transform:translateX(2px)}
}
.매트.맞음{animation:맞음 .42s ease-in-out}
.매트.맞음 .hp{color:var(--상대쪽);text-shadow:0 0 12px rgba(216,118,111,.7)}
@keyframes 피튀김{
  0%{opacity:0;transform:translate(-50%,-6px) scale(.9)}
  25%{opacity:1;transform:translate(-50%,-14px) scale(1)}
  100%{opacity:0;transform:translate(-50%,-34px) scale(1)}
}
.깎임{position:fixed;z-index:70;pointer-events:none;
 font-weight:800;font-size:17px;color:var(--상대쪽);text-shadow:0 1px 6px rgba(0,0,0,.6);
 animation:피튀김 1.1s ease-out forwards}
@media (prefers-reduced-motion:reduce){
  .카드.갓놓임,.매트.맞음,.깎임{animation:none}
}
.카드.할수있음{box-shadow:0 0 0 1px var(--강조) inset}
.카드[draggable="true"]{cursor:grab}
.카드.끌림{opacity:.45}
.칸.놓을수있음{border-style:solid;border-color:var(--강조);
 background:rgba(176,125,43,.22);box-shadow:0 0 0 2px rgba(176,125,43,.35)}
.쪽머리.놓을수있음{outline:2px dashed var(--강조);outline-offset:3px;border-radius:8px}
.카드.고를수있음{outline:2px solid var(--내쪽);outline-offset:1px;cursor:pointer}
.할수{position:absolute;top:3px;left:3px;background:var(--강조);color:#1a1510;
 font-size:9px;font-weight:800;border-radius:999px;padding:0 5px;line-height:1.5}
.할수 + .명{text-indent:17px}   /* 뱃지와 첫 줄이 겹치지 않게 */
.카드메뉴{position:fixed;z-index:60;background:var(--판);border:1px solid var(--선);
 border-radius:10px;padding:6px;box-shadow:0 8px 28px rgba(0,0,0,.28);
 display:flex;flex-direction:column;gap:4px;min-width:210px;max-width:320px}
.카드메뉴 .메뉴머리{font-size:11px;color:var(--흐림);padding:2px 4px 4px}
.카드메뉴 button{width:100%}
.귀띔{font-size:11px;color:var(--흐림);margin:2px 0 1px;white-space:pre-line}
.메모칸{display:flex;flex-direction:column;gap:7px;min-height:0;flex:1}
.메모머리{display:flex;justify-content:space-between;align-items:baseline}
.갈래줄{display:flex;gap:4px;flex-wrap:wrap}
.갈래줄 .갈래{padding:3px 9px;font-size:11.5px;border-radius:999px}
.갈래줄 .갈래.켬{background:var(--강조);color:#1a1510;border-color:transparent;font-weight:700}
.메모칸 textarea{font:inherit;font-size:12.5px;color:inherit;background:var(--바탕);
 border:1px solid var(--선);border-radius:8px;padding:7px 9px;resize:vertical;width:100%}
.메모들{display:flex;flex-direction:column;gap:5px;flex:1;min-height:0;overflow:auto}
.메모한줄{font-size:11.5px;border-left:3px solid var(--강조);padding:3px 0 3px 8px;
 color:var(--흐림)}
.메모한줄 b{color:var(--글);font-weight:600}
.메모한줄.고침{border-left-color:var(--내쪽)}
.메모한줄.안함{border-left-color:var(--상대쪽)}
.메모한줄.보류{border-left-color:var(--청)}
.메모한줄.대기{border-left-color:var(--선)}
.판정{font-size:11px;margin-top:2px;color:var(--흐림)}
.판정.고침{color:var(--내쪽)} .판정.안함{color:var(--상대쪽)} .판정.보류{color:var(--청)}
.판정 code{font-size:10.5px;opacity:.8}
.모든수{margin-top:4px}
.모든수 summary{font-size:11.5px;color:var(--흐림);cursor:pointer;padding:3px 0}
.모든수 button{width:100%;margin-top:4px}
.뱃지{position:absolute;top:3px;right:3px;background:var(--카운터);color:#1a1510;
 font-size:9.5px;font-weight:800;border-radius:999px;padding:0 5px;line-height:1.45}
.적{border-left-color:var(--적)} .녹{border-left-color:var(--녹)}
.황{border-left-color:var(--황)} .청{border-left-color:var(--청)}
.자{border-left-color:var(--자)} .백{border-left-color:var(--백)}
.흑{border-left-color:var(--흑)} .무색{border-left-color:var(--선)}
.존표{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:6px;
 font-size:9.5px;color:rgba(255,255,255,.4);margin:3px 0 1px;letter-spacing:.03em}
/* 내 패 — 마트 아래에 붙여 늘 보이게. 올리면 살짝 떠오른다. */
.패줄{display:flex;gap:5px;overflow-x:auto;overflow-y:hidden;padding:7px 2px 2px;
 border-top:1px solid var(--매트선);justify-content:center}
.패줄 .칸{min-width:var(--칸폭);width:var(--칸폭);flex:0 0 auto;transition:transform .1s}
.패줄 .칸.카드:hover{transform:translateY(-5px)}
.패줄:empty{display:none}

/* 옆 패널 — 카드 미리보기는 늘 보이고, 나머지는 탭 하나만 띄운다.
   상자 넷을 세로로 쌓으니 화면 밖으로 밀렸다(2026-10-28 정리). */
.옆{display:flex;flex-direction:column;gap:9px;min-width:0;min-height:0}
.상세{background:var(--판);border:1px solid var(--선);border-radius:10px;padding:10px 12px;
 box-shadow:var(--그림자);flex:0 0 auto;max-height:28vh;overflow:auto}
.상세 h3{margin:0 0 2px;font-size:13.5px} .상세 .메타{color:var(--흐림);font-size:11.5px;margin-bottom:6px}
.상세 pre{white-space:pre-wrap;word-break:break-word;font:inherit;margin:0;font-size:12px;
 line-height:1.5}
.탭줄{display:flex;gap:4px}
.탭줄 .탭{flex:1;padding:6px 4px;font-size:12px;text-align:center;border-radius:8px 8px 0 0;
 border-bottom-color:transparent;color:var(--흐림)}
.탭줄 .탭.켬{background:var(--판);color:var(--글);font-weight:700;border-color:var(--선);
 border-bottom-color:var(--판)}
.탭줄 .탭 .알{display:inline-block;min-width:15px;padding:0 4px;margin-left:3px;
 background:var(--강조);color:#1a1510;border-radius:999px;font-size:10px;font-weight:800}
.탭칸{display:none;background:var(--판);border:1px solid var(--선);border-radius:0 10px 10px 10px;
 padding:11px;box-shadow:var(--그림자);min-height:0;flex:1;overflow:auto;margin-top:-5px}
.탭칸.켬{display:flex;flex-direction:column;gap:8px}
.물음{font-size:12.5px;color:var(--흐림)}
.수들{display:flex;flex-direction:column;gap:5px}
.기보{font-family:ui-monospace,Consolas,monospace;font-size:11.5px;
 line-height:1.6;flex:1;min-height:0;overflow:auto;white-space:pre-wrap;color:var(--흐림)}
.기보 b{color:var(--글)}
.기보 .효과문{color:var(--강조);opacity:.8}
button .효과문{display:block;margin-top:3px;font-size:11.5px;color:var(--흐림);
 line-height:1.45;white-space:normal}
button:hover .효과문{color:var(--글)}
.끝판{grid-column:1/-1;background:var(--강조);color:#1a1510;border-radius:10px;
 padding:11px 15px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.끝말{font-weight:700}
.끝말 .사람들{color:rgba(26,21,16,.7);font-weight:400}
.끝단추{display:flex;gap:6px;margin-left:auto;flex-wrap:wrap}
.끝단추 button{background:rgba(255,255,255,.75);border-color:transparent;color:#1a1510}
.끝단추 button.주{background:#1a1510;color:var(--강조)}
.끝단추 .사람들{color:rgba(26,21,16,.75);align-self:center}
body.움직임끔 .카드.갓놓임,body.움직임끔 .매트.맞음,body.움직임끔 .깎임{animation:none}
.사람들{font-size:12px;color:var(--흐림)}

/* ---------- 재정 질문 ---------- */
.질문상자{padding:0;overflow:hidden}
.질문머리{display:flex;align-items:center;gap:9px;padding:12px 16px;cursor:pointer}
.질문머리:hover{background:var(--바탕)}
.질문머리 b{font-size:13.5px;flex:1;line-height:1.4}
.상태알{font-size:10.5px;font-weight:800;padding:2px 9px;border-radius:999px;white-space:nowrap}
.상태알.열림{background:rgba(176,125,43,.18);color:var(--강조);border:1px solid var(--강조)}
.상태알.답변됨{background:rgba(58,110,168,.15);color:var(--청);border:1px solid var(--청)}
.상태알.반영됨{background:rgba(63,138,82,.15);color:var(--녹);border:1px solid var(--녹)}
.질문몸{padding:0 16px 14px;border-top:1px solid var(--선)}
.질문글{white-space:pre-wrap;word-break:break-word;font:inherit;font-size:12.5px;
 line-height:1.6;margin:10px 0 6px}
.확답{border-left:3px solid var(--청);padding:2px 0 2px 10px;margin:8px 0}
.확답 b{font-size:12px;color:var(--청)}
.확답 .질문글{margin:4px 0 2px}
.질문몸 textarea{font:inherit;font-size:12.5px;color:inherit;background:var(--바탕);
 border:1px solid var(--선);border-radius:8px;padding:7px 9px;resize:vertical}
</style></head><body>

<div id="메인" class="바깥">
  <h1>뉴 네오</h1>
  <p>자작 TCG 「뉴 네오」 대전 환경. 규칙 판정은 전부 파이썬 엔진이 한다.</p>
  <div class="큰메뉴">
    <button class="메뉴쪽" onclick="화면('시작')">
      <b>게임 시작</b><span>혼자 두기 · AI끼리 구경 · 사람 둘</span></button>
    <button class="메뉴쪽" onclick="화면('편집')">
      <b>덱 편집</b><span>쓸 카드를 골라 내 덱으로</span></button>
    <button class="메뉴쪽" onclick="화면('열람')">
      <b>카드 열람</b><span>덱 구성과 카드 200장</span></button>
    <button class="메뉴쪽" onclick="화면('설정')">
      <b>설정</b><span>별명 · 기본 배속 · 움직임</span></button>
    <button class="메뉴쪽" onclick="화면('재정')">
      <b>재정 질문</b><span id="재정맛보기">룰 해석이 막힌 곳 — 의견·답변 받기</span></button>
  </div>
  <div class="상자">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <b style="font-size:13px">열려 있는 방</b>
      <span class="사람들" id="정원말"></span>
    </div>
    <div id="방목록"></div>
  </div>
</div>

<div id="시작" class="바깥 숨김">
  <div class="머리줄"><button onclick="화면('메인')">← 메인</button><h2>게임 시작</h2></div>
  <div class="상자">
    <div class="줄"><label>별명</label><input id="별명" placeholder="아무거나" style="flex:1"></div>
  </div>
  <div class="두쪽">
    <div class="상자">
      <b class="칸이름">내 쪽</b>
      <div class="줄"><label>덱</label><select id="내덱" style="flex:1"></select></div>
      <div class="줄"><label>누가</label><select id="내역할" style="flex:1">
        <option value="사람">내가 둔다</option>
        <option value="헤아림">AI (헤아림 — 수를 재어 둔다)</option>
        <option value="필터">AI (1층 필터)</option>
        <option value="무작위">AI (무작위)</option>
      </select></div>
      <div class="귀띔" id="내덱말"></div>
    </div>
    <div class="상자">
      <b class="칸이름">상대 쪽</b>
      <div class="줄"><label>덱</label><select id="상대덱" style="flex:1"></select></div>
      <div class="줄"><label>누가</label><select id="상대역할" style="flex:1">
        <option value="헤아림">AI (헤아림 — 수를 재어 둔다)</option>
        <option value="필터">AI (1층 필터)</option>
        <option value="무작위">AI (무작위)</option>
        <option value="사람">사람 — 초대 링크로 부른다</option>
      </select></div>
      <div class="귀띔" id="상대덱말"></div>
    </div>
  </div>
  <div class="상자">
    <div class="줄" style="margin:0">
      <button class="주 큼" onclick="방만들기()">이 설정으로 시작</button>
      <span id="로비말" class="사람들"></span>
    </div>
  </div>
</div>

<div id="열람" class="바깥 넓게 숨김">
  <div class="머리줄"><button onclick="화면('메인')">← 메인</button><h2>카드 열람</h2>
    <input id="찾기" placeholder="카드 이름·텍스트로 찾기" oninput="열람그리기()" style="flex:1;max-width:280px">
  </div>
  <div class="열람틀">
    <div class="상자 덱칸"><b class="칸이름">덱 구성</b><div id="덱목록"></div></div>
    <div class="상자 목록칸"><div class="사람들" id="열람셈"></div><div id="카드목록"></div></div>
    <div class="상자 상세칸" id="열람상세"><div class="메타">카드를 누르면 원문이 여기 뜬다.</div></div>
  </div>
</div>

<div id="편집" class="바깥 넓게 숨김">
  <div class="머리줄"><button onclick="화면('메인')">← 메인</button><h2>덱 편집</h2>
    <select id="편집덱" onchange="편집덱바꾸기()"></select>
    <span class="귀띔">룰지 0-1·0-2 — 메인 20~40장 · 상급 0~20장</span>
  </div>
  <div class="편집틀">
    <div class="상자 목록칸">
      <div class="줄" style="margin-bottom:8px">
        <button class="주" onclick="편집추천()">추천 구성</button>
        <button onclick="편집전체(true)">전부 한 장씩</button>
        <button onclick="편집전체(false)">전부 빼기</button>
        <input id="편집찾기" placeholder="찾기" oninput="편집그리기()" style="flex:1;min-width:90px">
      </div>
      <div id="편집목록"></div>
    </div>
    <div class="상자 덱칸">
      <b class="칸이름">이 덱</b>
      <div id="편집셈"></div>
      <div id="편집경고" class="귀띔"></div>
      <div class="줄" style="margin-top:10px">
        <input id="편집이름" placeholder="저장할 이름" style="flex:1">
        <button class="주" onclick="편집저장()">저장</button>
      </div>
      <div id="편집저장목록" style="margin-top:8px"></div>
    </div>
  </div>
</div>

<div id="설정" class="바깥 숨김">
  <div class="머리줄"><button onclick="화면('메인')">← 메인</button><h2>설정</h2></div>
  <div class="상자">
    <div class="줄"><label>별명</label><input id="설정별명" placeholder="아무거나" style="flex:1"></div>
    <div class="줄"><label>기본 배속</label>
      <select id="설정배속">
        <option value="0.5">0.5×</option><option value="1" selected>1×</option>
        <option value="2">2×</option><option value="4">4×</option><option value="0">최대</option>
      </select>
      <span class="귀띔">AI끼리 두는 판을 열 때 처음 속도</span>
    </div>
    <div class="줄"><label>움직임</label>
      <label class="켜기"><input type="checkbox" id="설정애니" checked> 카드 내려놓기·타격 효과를 쓴다</label>
    </div>
    <div class="줄" style="margin:0"><button class="주" onclick="설정저장()">저장</button>
      <span id="설정말" class="사람들"></span></div>
  </div>
  <div class="상자">
    <b class="칸이름">이 프로그램에 대해</b>
    <div class="귀띔">규칙 판정은 전부 파이썬 엔진이 한다 — 화면은 결과를 그리고 누른 것을 돌려줄 뿐이다.
      이상한 점은 판 안에서 <b>메모</b> 탭에 남겨 주면 턴·단계가 자동으로 붙는다.</div>
  </div>
</div>

<div id="재정" class="바깥 숨김">
  <div class="머리줄"><button onclick="화면('메인')">← 메인</button><h2>재정 질문</h2>
    <span class="사람들" id="재정셈"></span></div>
  <div class="상자">
    <div class="귀띔">룰 해석이 막혀 <b>개발자 판정</b>을 기다리는 질문들이다. 의견은 누구나
      남길 수 있고(판정의 참고 자료가 된다), 확정 답변은 개발자 서버에서만 적힌다.
      답변되면 야간 루틴이 다음 회차에 반영하고, 반영 커밋이 여기 다시 표시된다.</div>
  </div>
  <div id="재정목록"><div class="사람들">불러오는 중…</div></div>
</div>

<div id="판" class="틀 숨김">
  <div class="윗띠">
    <b>뉴 네오</b>
    <span id="머리말" class="사람들"></span>
    <span class="사람들" id="사람말"></span>
    <span class="덱경고 숨김" id="덱경고"></span>
    <div class="조절 숨김" id="조절"></div>
    <div class="단계띠" id="단계띠"></div>
  </div>

  <div class="판판">
    <div class="매트 적쪽" id="적매트"></div>
    <div class="가운데자리" id="가운데"></div>
    <div class="매트 나쪽" id="나매트"></div>
  </div>

  <div class="옆">
    <div class="상세" id="상세"><h3>카드</h3><div class="메타">카드를 누르면 원문이 여기 뜬다.</div></div>
    <div class="탭줄" id="탭줄">
      <button class="탭 켬" data-탭="수">할 것</button>
      <button class="탭" data-탭="메모">메모<span class="알" id="메모알">0</span></button>
      <button class="탭" data-탭="기보">기보</button>
    </div>

    <div class="탭칸 켬" data-칸="수">
      <div class="물음" id="물음">…</div>
      <div class="수들" id="수들"></div>
    </div>

    <div class="탭칸" data-칸="메모">
      <div class="메모칸">
        <div class="사람들" id="메모자리">지금 어느 턴·단계인지는 서버가 자동으로 붙인다.</div>
        <div class="갈래줄" id="갈래줄">
          <button class="갈래 켬" data-갈래="버그">버그</button>
          <button class="갈래" data-갈래="헷갈림">헷갈림</button>
          <button class="갈래" data-갈래="제안">제안</button>
          <button class="갈래" data-갈래="그냥">그냥</button>
        </div>
        <textarea id="메모글" rows="3" placeholder="이 장면에서 느낀 것 — 예: 공격 대상을 어디로 끌어야 하는지 모르겠다"></textarea>
        <div class="줄" style="margin:0">
          <button class="주" onclick="메모보내기()">메모 남기기</button>
          <button onclick="메모내려받기()">파일로</button>
          <button onclick="메모이슈()">깃허브 이슈</button>
        </div>
        <div class="사람들" id="메모말"></div>
        <div class="메모머리"><b style="font-size:12px">남긴 메모</b><span id="메모셈" class="사람들"></span></div>
        <div class="메모들" id="메모들"></div>
      </div>
    </div>

    <div class="탭칸" data-칸="기보"><div class="기보" id="기보"></div></div>
  </div>

  <div id="끝자리"></div>
</div>

<script>
const $ = (i)=>document.getElementById(i);
let 방=null, 토큰=null, 고른카드=null;

async function 보내기(길, 몸){
  const r = await fetch(길,{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify(몸||{})});
  return r.json();
}
async function 받기(길){ const r = await fetch(길); return r.json(); }

/* ---------- 로비 ---------- */
async function 방목록(){
  const d = await 받기('/api/rooms');
  $('정원말').textContent = `서버 ${d.총인원}/${d.최대인원}명`;
  $('방목록').innerHTML = d.방들.length ? d.방들.map(r=>`
    <div class="방줄"><span>${r.방} · ${r.덱['나']} vs ${r.덱['상대']}
      <span class="사람들">(${r.사람수}/${r.정원}${r.끝남?' · 끝남':''})</span></span>
    <button onclick="참가('${r.방}')">${r.빈자리?'자리 앉기':'관전'}</button></div>`).join('')
    : '<div class="사람들" style="padding-top:8px">아직 없다.</div>';
}
async function 방만들기(){
  const 나=고른덱풀기($('내덱').value), 적=고른덱풀기($('상대덱').value);
  const d = await 보내기('/api/create',{별명:$('별명').value,
    내덱:나.덱, 상대덱:적.덱, 내카드:나.카드, 상대카드:적.카드,
    내역할:$('내역할').value, 상대역할:$('상대역할').value});
  if(d.오류){ $('로비말').textContent = d.오류; return; }
  들어가기(d.방, d.토큰);
}
async function 참가(이름){
  const d = await 보내기('/api/join',{방:이름,별명:$('별명').value});
  if(d.오류){ $('로비말').textContent = d.오류; return; }
  들어가기(d.방, d.토큰);
}
function 들어가기(이름, 표){
  방=이름; 토큰=표; 마지막그림=''; 현재진행={}; 마지막판정수=0; 지난판=null; 갓놓인것=new Set();
  $('끝자리').innerHTML='';
  history.replaceState(null,'',`?방=${이름}`);
  화면('판');
  뽑기();
}

/* ---------- 판 상태 ---------- */
let 현재보드=null, 수표=null, 끄는중=null, 메뉴=null, 마지막그림='', 리포주소=null;
let 지난판=null, 갓놓인것=new Set();   /* 애니메이션용 — 규칙과 무관하다 */
let 현재덱={나:'호박옥',상대:'던전마스터'};
let 내자리='나', 적자리='상대', 지금질문=null;

/* 합법수를 제스처별로 묶는다. 색인이 그대로 답할 번호다. */
function 수표만들기(q){
  const t={소환:{},로드:{},발동:{},표시:{},직접:{},공격:{},기타:[]};
  if(!q || q.종류!=='수') return t;
  (q.갈래||[]).forEach((g,i)=>{
    if(!g.동작 || g.곁다리){ t.기타.push(i); return; }
    const n=g.카드;
    if(g.동작==='소환') t.소환[n]=i;
    else if(g.동작==='로드') t.로드[n]=i;
    else if(g.동작==='발동') (t.발동[n]=t.발동[n]||[]).push({i,번호:g.번호,효과문:g.효과문});
    else if(g.동작==='표시변경') (t.표시[n]=t.표시[n]||[]).push({i,표시:g.표시});
    else if(g.동작==='공격선언'){
      if(g.대상) (t.공격[n]=t.공격[n]||{})[g.대상]=i; else t.직접[n]=i;
    } else t.기타.push(i);
  });
  return t;
}

/* 그 카드를 눌렀을 때 뜰 수들 */
function 카드수들(이름, ㅇ){
  if(!수표 || !이름) return [];
  const 목=[];
  (수표.발동[이름]||[]).forEach(e=>목.push({i:e.i,라벨:`${e.번호}번 효과 발동`,설명:e.효과문}));
  (수표.표시[이름]||[]).forEach(e=>목.push({i:e.i,라벨:`${e.표시} 표시로 바꾸기`}));
  if(수표.직접[이름]!==undefined) 목.push({i:수표.직접[이름],라벨:'직접 공격',설명:'상대 유닛이 없을 때만 — 상대 HP 로 끌어도 된다'});
  Object.entries(수표.공격[이름]||{}).forEach(([대상,i])=>목.push({i,라벨:`${대상} 공격`,설명:'상대 유닛 위로 끌어도 된다'}));
  if(수표.소환[이름]!==undefined) 목.push({i:수표.소환[이름],라벨:'소환',설명:'내 유닛 존으로 끌어도 된다'});
  if(수표.로드[이름]!==undefined) 목.push({i:수표.로드[이름],라벨:'로드 (뒷면으로 놓기)',설명:'내 이펙트 존으로 끌어도 된다'});
  return 목;
}

/* 끌어서 놓을 수 있는 수와, 그 수가 받는 자리.
   패에서 이펙트 존으로 끄는 것은 **마법 카드만**이다 — 몬스터의 패 발동([신속] 특수소환
   등)은 이펙트 존에 놓는 일이 아니므로 끌기로 받지 않고 카드를 눌러 고른다. */
function 끌기갈래(c, ㅇ){
  const 이름 = c && c.이름;
  if(!수표 || !이름 || !ㅇ || ㅇ.쪽!==내자리) return [];
  const 목=[];
  if(ㅇ.존==='패'){
    if(수표.소환[이름]!==undefined) 목.push({i:수표.소환[이름],곳:'유닛',라벨:'소환'});
    if(수표.로드[이름]!==undefined) 목.push({i:수표.로드[이름],곳:'이펙트',라벨:'로드 (뒷면으로 놓기)'});
    if(c.종류==='마법')
      (수표.발동[이름]||[]).forEach(e=>목.push({i:e.i,곳:'이펙트',라벨:`${e.번호}번 효과 발동`,설명:e.효과문}));
  }else if(ㅇ.존==='유닛'){
    if(수표.직접[이름]!==undefined) 목.push({i:수표.직접[이름],곳:'직접',라벨:'직접 공격'});
    Object.entries(수표.공격[이름]||{}).forEach(([대상,i])=>목.push({i,곳:'적유닛',대상,라벨:`${대상} 공격`}));
  }
  return 목;
}

/* ---------- 카드 ---------- */
function 벗기기(글){ const d=document.createElement('div'); d.textContent=글==null?'':글; return d.innerHTML; }
function 위치표(ㅇ){ return ㅇ?`data-쪽="${ㅇ.쪽}" data-존="${ㅇ.존}" data-i="${ㅇ.i}"`:''; }
function 위치읽기(el){
  if(!el || !el.dataset || !el.dataset.존) return null;
  return {쪽:el.dataset.쪽, 존:el.dataset.존, i:parseInt(el.dataset.i,10)};
}
function 카드찾기(ㅇ){
  const b=현재보드; if(!b||!ㅇ) return null;
  if(ㅇ.존==='필드') return b.필드존;
  if(ㅇ.존==='공유') return b.공유존;
  const p=b.쪽[ㅇ.쪽]; if(!p) return null;
  if(ㅇ.존==='스킬') return p.스킬;
  if(ㅇ.존==='패') return p.패[ㅇ.i];
  if(ㅇ.존==='유닛') return p.유닛[ㅇ.i];
  if(ㅇ.존==='이펙트') return p.이펙트[ㅇ.i];
  return null;
}

function 카드칸(c, 자리글, ㅇ){
  if(!c) return `<div class="칸 빈" ${위치표(ㅇ)}>${자리글||''}</div>`;
  if(c.뒷면 && !c.이름) return `<div class="칸 카드 뒤" ${위치표(ㅇ)} title="뒷면"></div>`;
  const 색=c.색||'무색';
  const 수치=(c.공!==null&&c.공!==undefined)?`${c.공}/${c.수}`:(c.종류||'');
  const 뱃=c.카운터?`<span class="뱃지">${c.카운터}</span>`:'';
  const 뒤=c.뒷면?' 뒤':'';
  const 고름=(고른카드===c.이름)?' 고름':'';
  const 갓=(ㅇ&&갓놓인것.has(`${ㅇ.쪽}/${ㅇ.존}/${ㅇ.i}/${c.이름}`))?' 갓놓임':'';
  const 표시=c.표시==='수비'?'수':(c.표시==='공격'?'공':'');
  const 쓸수=ㅇ&&ㅇ.쪽===내자리?카드수들(c.이름,ㅇ):[];
  const 끌것=끌기갈래(c,ㅇ);
  const 고를수있나=지금질문&&지금질문.종류==='고르기'&&(지금질문.후보||[]).includes(c.이름);
  const 표딱지=쓸수.length?`<span class="할수">${쓸수.length}</span>`:'';
  return `<div class="칸 카드 ${색}${뒤}${고름}${갓}${쓸수.length?' 할수있음':''}${고를수있나?' 고를수있음':''}"
    ${위치표(ㅇ)} ${끌것.length?'draggable="true"':''} title="${벗기기(c.이름)}">
    ${뱃}${표딱지}<div class="명">${벗기기(c.이름)}</div>
    <div class="밑"><span>${수치}</span><span>${표시}</span></div></div>`;
}
function 더미칸(이름, 수){
  return `<div class="칸 더미"><span class="수">${수}</span><span class="이">${이름}</span></div>`;
}
function 상세보기(c){
  if(!c||!c.이름) return;
  고른카드=c.이름;
  const 메타=[c.종류,c.레벨!=null?`레벨 ${c.레벨}`:null,c.공!=null?`${c.공} / ${c.수}`:null,
    c.색?`${c.색}색`:null,c.카운터?`봉인 ${c.카운터}`:null,c.표시].filter(Boolean).join(' · ');
  $('상세').innerHTML=`<h3>${벗기기(c.이름)}</h3><div class="메타">${벗기기(메타)}</div>
    <pre>${벗기기(c.텍스트||'(텍스트 없음)')}</pre>
    ${c.표지&&c.표지.length?`<div class="메타" style="margin-top:8px">표지: ${벗기기(c.표지.join(', '))}</div>`:''}`;
}

/* ---------- 카드 메뉴 ---------- */
function 메뉴닫기(){ if(메뉴){ 메뉴.remove(); 메뉴=null; } }
function 메뉴열기(목, x, y, 머리){
  메뉴닫기();
  if(!목.length) return;
  const d=document.createElement('div');
  d.className='카드메뉴';
  d.innerHTML=(머리?`<div class="메뉴머리">${벗기기(머리)}</div>`:'')
    + 목.map(m=>`<button data-수="${m.i}">${벗기기(m.라벨)}`
        +(m.설명?`<span class="효과문">${벗기기(m.설명)}</span>`:'')+`</button>`).join('');
  document.body.appendChild(d);
  const 너비=d.offsetWidth, 높이=d.offsetHeight;
  d.style.left=Math.max(6,Math.min(window.innerWidth-너비-6,x))+'px';
  d.style.top=Math.max(6,Math.min(window.innerHeight-높이-6,y))+'px';
  d.addEventListener('click',e=>{
    const b=e.target.closest('button'); if(!b) return;
    메뉴닫기(); 답(parseInt(b.dataset.수,10));
  });
  메뉴=d;
}

/* ---------- 매트 ---------- */
function 매트그리기(자리, 이름, p, 턴인가, 뒤집을까){
  const 비=Math.max(0,Math.min(100,p.hp/5000*100));
  const 유닛=p.유닛.map((c,i)=>카드칸(c,`유닛 ${i+1}`,{쪽:이름,존:'유닛',i}));
  const 이펙=p.이펙트.map((c,i)=>카드칸(c,`이펙트 ${i+1}`,{쪽:이름,존:'이펙트',i}));
  const 윗줄=[카드칸(p.스킬,'스킬 존',{쪽:이름,존:'스킬',i:0}),...유닛,
    더미칸('아카이브',p.아카이브.length),더미칸('공허',p.공허.length)];
  const 아랫줄=['<div class="칸 빈"></div>',...이펙,
    더미칸('메인 덱',p.메인덱),더미칸('상급 덱',p.상급덱)];
  const 줄들=뒤집을까?[아랫줄,윗줄]:[윗줄,아랫줄];
  자리.innerHTML=`
    <div class="쪽머리" data-쪽머리="${이름}">
      <span class="딱지">${이름}${턴인가?' ◂턴':''}</span>
      <span class="hp">${p.hp}</span><span class="hp바"><i style="width:${비}%"></i></span>
      <span class="잔">패 ${p.패수}</span>
    </div>
    <div class="필드">${줄들[0].join('')}</div>
    <div class="필드" style="margin-top:6px">${줄들[1].join('')}</div>
    ${p.패.length?`<div class="패줄">${p.패.map((c,i)=>카드칸(c,'',{쪽:이름,존:'패',i})).join('')}</div>`:''}`;
}

function 가운데(b){
  /* 룰지 0-5·0-7 — 두 플레이어가 함께 쓰는 칸이라 매트 사이에 둔다. */
  return `<div class="가운데줄">
    <span class="라벨">공유 줄</span>
    ${카드칸(b.필드존,'필드 존',{쪽:'공용',존:'필드',i:0})}
    ${카드칸(b.공유존,'공유 존'+(b.공유존주인?` (${b.공유존주인})`:''),{쪽:'공용',존:'공유',i:0})}
  </div>`;
}

function 단계띠(지금){
  $('단계띠').innerHTML=['준비','진행','전투','정비','종료']
    .map(s=>`<span class="단계알${s===지금?' 켬':''}">${s}</span>`).join('');
}

/* ---------- 끌어다 놓기 ---------- */
function 놓을곳표시(갈래들){
  지우기();
  const 곳들=new Set(갈래들.map(g=>g.곳));
  if(곳들.has('유닛')) document.querySelectorAll(`.칸.빈[data-쪽="${내자리}"][data-존="유닛"]`)
    .forEach(e=>e.classList.add('놓을수있음'));
  if(곳들.has('이펙트')) document.querySelectorAll(`.칸.빈[data-쪽="${내자리}"][data-존="이펙트"]`)
    .forEach(e=>e.classList.add('놓을수있음'));
  if(곳들.has('직접')) document.querySelectorAll(`.쪽머리[data-쪽머리="${적자리}"]`)
    .forEach(e=>e.classList.add('놓을수있음'));
  갈래들.filter(g=>g.곳==='적유닛').forEach(g=>{
    document.querySelectorAll(`.칸.카드[data-쪽="${적자리}"][data-존="유닛"]`).forEach(e=>{
      const c=카드찾기(위치읽기(e));
      if(c && c.이름===g.대상) e.classList.add('놓을수있음');
    });
  });
}
function 지우기(){
  document.querySelectorAll('.놓을수있음').forEach(e=>e.classList.remove('놓을수있음'));
  document.querySelectorAll('.끌림').forEach(e=>e.classList.remove('끌림'));
}
function 놓는곳갈래(el){
  if(!끄는중) return [];
  const 자 = el.closest('.쪽머리');
  if(자 && 자.dataset.쪽머리===적자리) return 끄는중.갈래.filter(g=>g.곳==='직접');
  const 칸 = el.closest('.칸'); if(!칸) return [];
  const ㅇ = 위치읽기(칸); if(!ㅇ) return [];
  if(ㅇ.쪽===내자리 && !칸.classList.contains('카드'))
    return 끄는중.갈래.filter(g=>g.곳===(ㅇ.존==='유닛'?'유닛':ㅇ.존==='이펙트'?'이펙트':'없음'));
  if(ㅇ.쪽===적자리 && ㅇ.존==='유닛'){
    const c=카드찾기(ㅇ);
    return 끄는중.갈래.filter(g=>g.곳==='적유닛' && c && g.대상===c.이름);
  }
  return [];
}

/* ---------- 이벤트(한 번만 건다 — 판은 0.9초마다 다시 그려진다) ---------- */
function 손길걸기(){
  const 판=$('판');
  판.addEventListener('dragstart',e=>{
    const 칸=e.target.closest('.칸.카드'); if(!칸) return;
    const ㅇ=위치읽기(칸), c=카드찾기(ㅇ);
    const 갈래=끌기갈래(c,ㅇ);
    if(!갈래.length){ e.preventDefault(); return; }
    끄는중={위치:ㅇ,이름:c.이름,갈래};
    e.dataTransfer.effectAllowed='move';
    e.dataTransfer.setData('text/plain',c.이름);
    메뉴닫기(); 놓을곳표시(갈래);
    칸.classList.add('끌림');   /* 놓을곳표시 가 지우기() 를 먼저 부르므로 그 뒤에 켠다 */
  });
  판.addEventListener('dragend',()=>{ 끄는중=null; 지우기(); });
  판.addEventListener('dragover',e=>{
    if(!끄는중) return;
    if(놓는곳갈래(e.target).length){ e.preventDefault(); e.dataTransfer.dropEffect='move'; }
  });
  판.addEventListener('drop',e=>{
    if(!끄는중) return;
    const 갈래=놓는곳갈래(e.target);
    if(!갈래.length) return;
    e.preventDefault();
    const 이름=끄는중.이름;
    끄는중=null; 지우기();
    if(갈래.length===1) 답(갈래[0].i);
    else 메뉴열기(갈래.map(g=>({i:g.i,라벨:g.라벨,설명:g.설명})),e.clientX,e.clientY,이름);
  });
  판.addEventListener('click',e=>{
    const 칸=e.target.closest('.칸.카드'); if(!칸){ 메뉴닫기(); return; }
    const ㅇ=위치읽기(칸), c=카드찾기(ㅇ);
    if(!c) return;
    상세보기(c);
    /* 대상을 고르는 중이면 판에서 바로 집는다 */
    if(지금질문 && 지금질문.종류==='고르기'){
      const 자리=(지금질문.후보||[]).indexOf(c.이름);
      if(자리>=0){ 메뉴닫기(); 답(자리); return; }
    }
    const 목=ㅇ&&ㅇ.쪽===내자리?카드수들(c.이름,ㅇ):[];
    if(목.length){ const r=칸.getBoundingClientRect(); 메뉴열기(목,r.right+6,r.top,c.이름); }
    else 메뉴닫기();
  });
  document.addEventListener('click',e=>{
    if(메뉴 && !e.target.closest('.카드메뉴') && !e.target.closest('.칸.카드')) 메뉴닫기();
  });
  document.addEventListener('keydown',e=>{ if(e.key==='Escape') 메뉴닫기(); });
}

/* ---------- 수 ---------- */
async function 답(값){ 메뉴닫기(); await 보내기('/api/answer',{방,토큰,값}); 마지막그림=''; 뽑기(); }

function 수그리기(d){
  const q=d.질문, 목록=$('수들');
  if(d.끝){ $('물음').textContent='판이 끝났다.'; 목록.innerHTML=''; return; }
  if(!d.나의자리){ $('물음').textContent='관전 중'; 목록.innerHTML=''; return; }
  if(!q){
    $('물음').textContent=d.기다리는자리.length
      ?`${d.기다리는자리.join(', ')} 쪽이 두는 중…`:'상대가 두는 중…';
    목록.innerHTML=''; return;
  }
  if(q.종류==='수'){
    const 할것=Object.keys(수표.소환).length+Object.keys(수표.로드).length
      +Object.keys(수표.발동).length+Object.keys(수표.표시).length
      +Object.keys(수표.직접).length+Object.keys(수표.공격).length;
    $('물음').innerHTML=`<b>${벗기기(q.질문)}</b> — 패를 끌어다 놓거나, 카드를 눌러 수를 고른다.`
      +(할것?'':' <span class="효과문">둘 수 있는 게 없다 — 다음 단계로.</span>');
    const 묶음=(수표.기타||[]).map(i=>
      `<button data-수="${i}">${벗기기(q.후보[i])}`
      +(q.효과문&&q.효과문[i]?`<span class="효과문">${벗기기(q.효과문[i])}</span>`:'')+`</button>`).join('');
    목록.innerHTML=(묶음?`<div class="귀띔">제스처로 못 줄이는 수</div>${묶음}`:'')
      +`<button class="주" data-답="넘김">다음 단계로</button>
        <button class="위험" data-답="기권">기권</button>
        <details class="모든수"><summary>모든 수 (${q.후보.length})</summary>
        ${q.후보.map((하나,i)=>`<button data-수="${i}">${벗기기(하나)}`
          +(q.효과문&&q.효과문[i]?`<span class="효과문">${벗기기(q.효과문[i])}</span>`:'')
          +`</button>`).join('')}</details>`;
  }else{
    const 판위=(q.후보||[]).some(이름=>판에있나(이름));
    $('물음').innerHTML=`<b>${벗기기(q.질문)}</b>`
      +(판위?' — 판에서 바로 눌러도 된다.':'');
    목록.innerHTML=q.후보.map((하나,i)=>`<button data-수="${i}">${벗기기(하나)}</button>`).join('');
  }
  목록.onclick=e=>{
    const b=e.target.closest('button'); if(!b) return;
    if(b.dataset.답) 답(b.dataset.답);
    else if(b.dataset.수!==undefined) 답(parseInt(b.dataset.수,10));
  };
}
function 판에있나(이름){
  const b=현재보드; if(!b) return false;
  for(const 쪽 of ['나','상대']){
    const p=b.쪽[쪽];
    for(const 더미 of [p.유닛,p.이펙트,p.패]) if((더미||[]).some(c=>c&&c.이름===이름)) return true;
    if(p.스킬&&p.스킬.이름===이름) return true;
  }
  return false;
}

async function 뽑기(){
  if(!방) return;
  if(끄는중) return;
  try{
    const d=await 받기(`/api/state?room=${방}&token=${토큰}`);
    if(d.오류){ $('물음').textContent=d.오류; return; }
    const 지문=JSON.stringify(d);
    if(지문===마지막그림) return;
    마지막그림=지문;
    움직임보기(d.보드);
    현재보드=d.보드; 지금질문=d.질문; 수표=수표만들기(d.질문);
    내자리=d.나의자리==='상대'?'상대':'나';
    적자리=내자리==='나'?'상대':'나';
    const b=d.보드;
    $('머리말').textContent=`방 ${d.방} · 턴 ${b.턴} · ${b.턴플레이어} 차례 · 내 자리: ${d.나의자리||'관전'}`;
    $('사람말').textContent=d.사람들.map(s=>`${s.별명}${s.자리?`(${s.자리})`:'(관전)'}`)
      .join(' · ')+` — ${d.사람들.length}/${d.정원}`;
    단계띠(b.단계);
    매트그리기($('적매트'),적자리,b.쪽[적자리],b.턴플레이어===적자리,true);
    매트그리기($('나매트'),내자리,b.쪽[내자리],b.턴플레이어===내자리,false);
    $('가운데').innerHTML=가운데(b);
    const g=$('기보');
    const 바닥=g.scrollTop+g.clientHeight>=g.scrollHeight-30;
    g.innerHTML=d.기보.map(l=>{
      const t=벗기기(l);
      if(l.startsWith('[')) return `<b>${t}</b>`;
      if(l.trimStart().startsWith('「')) return `<span class="효과문">${t}</span>`;
      return t;
    }).join('\n');
    if(바닥) g.scrollTop=g.scrollHeight;
    현재진행=d.진행||{};
    조절그리기(d);
    수그리기(d);
    메모그리기(d);
    if(d.리포) 리포주소=d.리포;
    현재덱 = d.덱 || 현재덱;
    덱경고그리기(d);
    끝그리기(d);
  }catch(e){ $('물음').textContent='서버와 끊겼다.'; }
}

/* ---------- 메모(피드백) ---------- */
let 메모갈래='버그', 마지막판정수=0, 현재진행={};
document.getElementById('갈래줄').addEventListener('click',e=>{
  const b=e.target.closest('.갈래'); if(!b) return;
  메모갈래=b.dataset.갈래;
  document.querySelectorAll('#갈래줄 .갈래').forEach(x=>x.classList.toggle('켬',x===b));
});
async function 메모보내기(){
  const 글=$('메모글').value.trim();
  if(!글){ $('메모말').textContent='쓸 말을 먼저 적어라.'; return; }
  const d=await 보내기('/api/memo',{방,토큰,글,갈래:메모갈래});
  if(d.오류){ $('메모말').textContent=d.오류; return; }
  $('메모글').value='';
  $('메모말').textContent=`남겼다 (${d.개수}개)`+(d.올림?` · ${d.올림}`:'');
  마지막그림=''; 뽑기();
}
function 메모내려받기(){ location.href=`/api/memo.md?room=${encodeURIComponent(방)}`; }
async function 메모이슈(){
  const r=await fetch(`/api/memo.md?room=${encodeURIComponent(방)}`);
  const 본문=await r.text();
  if(!리포주소){ $('메모말').textContent='리포 주소를 모른다 — 「파일로」 를 써라.'; return; }
  const 길=`${리포주소}/issues/new?title=`+encodeURIComponent(`플레이 피드백 — 방 ${방}`)
    +'&body='+encodeURIComponent(본문);
  if(길.length>7500){
    await navigator.clipboard.writeText(본문).catch(()=>{});
    $('메모말').textContent='메모가 길어 주소에 안 담긴다 — 본문을 복사했으니 이슈에 붙여라.';
    window.open(`${리포주소}/issues/new`,'_blank');
    return;
  }
  window.open(길,'_blank');
}
const 판정꼴={고침:['✅','고침','고침'],안함:['⛔','안 고침','안함'],보류:['⏸','보류','보류']};
function 메모그리기(d){
  const 목=d.메모들||[];
  const 센것={고침:0,안함:0,보류:0,대기:0};
  목.forEach(m=>센것[m.판정?m.판정.상태:'대기']++);
  $('메모셈').textContent=`${목.length}개`
    +(목.length?` · ✅${센것.고침} ⛔${센것.안함} ⏸${센것.보류} ⏳${센것.대기}`:'');
  const 알=$('메모알');
  알.textContent=목.length;
  알.style.display=목.length?'':'none';
  /* 판정이 새로 떴으면 메모 탭에 표가 난다 */
  const 본것=센것.고침+센것.안함+센것.보류;
  if(본것>마지막판정수){ 마지막판정수=본것; 알.textContent=`${목.length}·새`; }
  const b=d.보드;
  $('메모자리').textContent=b?`지금: 턴 ${b.턴} · ${b.단계} 단계 — 남기면 이 자리가 같이 붙는다`
    :'지금 어느 턴·단계인지는 서버가 자동으로 붙인다.';
  $('메모들').innerHTML=목.slice().reverse().map(m=>{
    const p=m.판정, 꼴=p?판정꼴[p.상태]:['⏳','아직 안 봤다','대기'];
    return `<div class="메모한줄 ${꼴[2]}">
      <b>[${벗기기(m.갈래)}] 턴 ${m.턴} · ${벗기기(m.단계)}</b> ${벗기기(m.글)}
      <div class="판정 ${꼴[2]}">${꼴[0]} ${꼴[1]}`
      +(p&&p.말?` — ${벗기기(p.말)}`:'')
      +(p&&p.커밋?` <code>${벗기기(p.커밋)}</code>`:'')+`</div></div>`;
  }).join('');
}

/* ---------- 재정 질문 ---------- */
let 재정들=[], 재정답변가능=false, 재정펼침=null, 재정쪽지={};
async function 재정맛보기(){
  try{
    const d=await 받기('/api/questions');
    const 열림=(d.질문들||[]).filter(q=>q.상태==='열림').length;
    $('재정맛보기').textContent = 열림?`답을 기다리는 질문 ${열림}건`:'룰 해석이 막힌 곳 — 지금은 다 답변됨';
  }catch(e){}
}
async function 재정그리기(){
  const d=await 받기('/api/questions');
  재정들=d.질문들||[]; 재정답변가능=!!d.답변가능;
  const 셈={열림:0,답변됨:0,반영됨:0};
  재정들.forEach(q=>{ 셈[q.상태]=(셈[q.상태]||0)+1; });
  $('재정셈').textContent=`열림 ${셈.열림} · 답변됨 ${셈.답변됨} · 반영됨 ${셈.반영됨}`;
  const 차례={열림:0,답변됨:1,반영됨:2};
  const 줄서기=[...재정들].sort((a,b)=>(차례[a.상태]??9)-(차례[b.상태]??9)||(a.번호-b.번호));
  $('재정목록').innerHTML = 줄서기.map(q=>{
    const 몸 = 재정펼침!==q.번호 ? '' : `<div class="질문몸">
      <pre class="질문글">${벗기기(q.질문)}</pre>
      <div class="귀띔">출처 — ${벗기기(q.출처||'')}</div>
      ${q.답변?`<div class="확답"><b>확정 답변${q.답변때?' · '+new Date(q.답변때*1000).toLocaleDateString('ko-KR'):''}</b>
        <pre class="질문글">${벗기기(q.답변)}</pre>
        ${q.반영커밋?`<div class="귀띔">반영 커밋 <code>${벗기기(q.반영커밋)}</code>${q.반영메모?' — '+벗기기(q.반영메모):''}</div>`:''}
      </div>`:''}
      ${(q.의견들&&q.의견들.length)?`<div class="메모머리" style="margin-top:6px"><b style="font-size:12px">의견</b>
        <span class="사람들">${q.의견들.length}개</span></div>`
        +q.의견들.map(m=>`<div class="메모한줄"><b>${벗기기(m.별명||'손님')}</b> ${벗기기(m.글)}</div>`).join(''):''}
      ${q.상태!=='반영됨'?`
      <div class="줄" style="margin:9px 0 0">
        <textarea id="재정글${q.번호}" rows="2" style="flex:1"
          placeholder="${재정답변가능?'답변 또는 의견 — 보기가 있으면 번호로 짧게':'의견 — 예: ②가 자연스럽다, 실제로 이런 판이 있었다'}"></textarea>
      </div>
      <div class="줄" style="margin:5px 0 0">
        <button onclick="재정의견(${q.번호})">의견 남기기</button>
        ${재정답변가능?`<button class="주" onclick="재정답변(${q.번호})">확정 답변으로 올리기</button>`:''}
        <span class="사람들">${벗기기(재정쪽지[q.번호]||'')}</span>
      </div>`:''}
    </div>`;
    return `<div class="상자 질문상자">
      <div class="질문머리" onclick="재정펼치기(${q.번호})">
        <span class="상태알 ${q.상태}">${q.상태}</span>
        <b>${q.번호}. ${벗기기(q.제목)}</b>
      </div>${몸}</div>`;
  }).join('') || '<div class="사람들">질문이 없다.</div>';
}
function 재정펼치기(번호){ 재정펼침 = 재정펼침===번호?null:번호; 재정그리기(); }
async function 재정의견(번호){
  const 칸=$('재정글'+번호), 글=(칸?칸.value:'').trim();
  if(!글){ 재정쪽지[번호]='글이 비었다'; 재정그리기(); return; }
  const d=await 보내기('/api/question_memo',{번호,별명:설정.별명||$('별명')?.value||'손님',글});
  재정쪽지[번호]=d.오류||d.올림||'남겼다';
  재정그리기();
}
async function 재정답변(번호){
  const 칸=$('재정글'+번호), 글=(칸?칸.value:'').trim();
  if(!글){ 재정쪽지[번호]='글이 비었다'; 재정그리기(); return; }
  const d=await 보내기('/api/question_answer',{번호,답변:글});
  재정쪽지[번호]=d.오류||('확정 답변으로 올렸다 — '+(d.올림||''));
  재정그리기();
}

/* ---------- 화면 전환 ---------- */
const 화면들={메인:'메인',시작:'시작',편집:'편집',열람:'열람',설정:'설정',재정:'재정',판:'판'};
function 화면(어디){
  Object.values(화면들).forEach(i=>$(i).classList.toggle('숨김', i!==화면들[어디]));
  if(어디==='열람') 열람열기();
  if(어디==='편집') 편집열기();
  if(어디==='재정') 재정그리기();
  if(어디==='메인'){ 방목록(); 재정맛보기(); }
}
function 메인으로(){
  /* 자리를 비운다고 서버에 알린다 — 안 그러면 참가자가 남아 서버 정원을 잡아먹는다 */
  if(방 && 토큰) 보내기('/api/leave',{방,토큰}).catch(()=>{});
  방=null; 토큰=null; 지난판=null; 마지막그림=''; 현재진행={};
  history.replaceState(null,'','/');
  화면('메인');
}

/* ---------- 설정(이 브라우저에만 저장) ---------- */
const 설정기본={별명:'',기본배속:1,애니:true};
let 설정=Object.assign({},설정기본);
function 설정읽기(){
  try{ 설정=Object.assign({},설정기본,JSON.parse(localStorage.getItem('뉴네오설정')||'{}')); }
  catch(e){ 설정=Object.assign({},설정기본); }
  $('설정별명').value=설정.별명; $('별명').value=설정.별명;
  $('설정배속').value=String(설정.기본배속);
  $('설정애니').checked=!!설정.애니;
  document.body.classList.toggle('움직임끔', !설정.애니);
}
function 설정저장(){
  설정={별명:$('설정별명').value.trim(), 기본배속:parseFloat($('설정배속').value), 애니:$('설정애니').checked};
  localStorage.setItem('뉴네오설정', JSON.stringify(설정));
  $('별명').value=설정.별명;
  document.body.classList.toggle('움직임끔', !설정.애니);
  $('설정말').textContent='저장했다.';
  setTimeout(()=>{ $('설정말').textContent=''; },1600);
}

/* ---------- 덱 목록 ---------- */
let 덱들=[], 카드들=[], 열람보임=[], 고른덱=null, 고른카드이름=null;
async function 덱받기(){
  if(덱들.length) return 덱들;
  덱들=(await 받기('/api/decks')).덱들||[];
  return 덱들;
}
function 덱설명(d){
  if(!d) return '';
  const 쪽=[`메인 ${d.메인}장 · 상급 ${d.상급}장`, `스킬 「${d.스킬||'없음'}」`];
  if(!d.효과있음) 쪽.push('⚠ 효과 미구현 — 카드를 내고 전투까지는 되지만 효과는 안 걸린다');
  if(!d.필터가능) 쪽.push('1층 필터 맵 없음 — 헤아림·무작위 AI 로 둔다');
  return 쪽.join(' · ');
}
async function 덱고르개채우기(){
  const 목=await 덱받기();
  저장덱읽기();
  const 저장키=Object.keys(저장덱들);
  const 보기=목.map(d=>`<option value="추천:${벗기기(d.이름)}">${벗기기(d.이름)} — 추천 구성`
      +`${d.효과있음?'':' (효과 미구현)'}</option>`).join('')
    + `<optgroup label="테마 카드를 한 장씩">`
    + 목.map(d=>`<option value="테마:${벗기기(d.이름)}">${벗기기(d.이름)} (한 장씩)</option>`).join('')
    + `</optgroup>`
    + (저장키.length?`<optgroup label="저장한 덱">`
        + 저장키.map(k=>`<option value="저장:${벗기기(k)}">${벗기기(k)}</option>`).join('')
        + `</optgroup>`:'');
  ['내덱','상대덱'].forEach((아이디,자리)=>{
    const sel=$(아이디), 전=sel.value;
    sel.innerHTML=보기;
    sel.value = [...sel.options].some(o=>o.value===전) ? 전
              : (자리===0 ? '추천:호박옥' : '추천:던전마스터');
    sel.onchange=()=>덱말갱신();
  });
  덱말갱신();
}
/* 고르개 값 → {덱, 카드} — 「저장:이름」이면 저장해 둔 카드 목록을 쓴다 */
function 고른덱풀기(값){
  if(!값) return {덱:'호박옥', 카드:null};
  if(값.startsWith('저장:')){
    const 하나=저장덱들[값.slice(3)];
    if(하나) return {덱:하나.덱, 카드:하나.카드};
  }
  if(값.startsWith('추천:')){
    const 이름=값.slice(3), d=덱들.find(x=>x.이름===이름);
    return {덱:이름, 카드:(d&&d.추천카드&&d.추천카드.length)?d.추천카드:null, 추천:true};
  }
  return {덱:값.replace(/^테마:/,''), 카드:null};
}
function 덱말갱신(){
  const 쓰기=(고르개,말자리)=>{
    const 푼것=고른덱풀기($(고르개).value);
    const d=덱들.find(x=>x.이름===푼것.덱);
    const 덧=푼것.카드?` · ${푼것.추천?'추천 구성':'고른 카드'} ${푼것.카드.length}장`:'';
    $(말자리).textContent=덱설명(d)+덧+((푼것.추천&&d&&d.추천)?`
${d.추천}`:'');
  };
  쓰기('내덱','내덱말'); 쓰기('상대덱','상대덱말');
}


/* ---------- 덱 편집 ---------- */
/* 저장한 덱은 이 브라우저에만 둔다. 룰지 0-1·0-2 범위를 **알려 주되 막지 않는다** —
   테마 카드를 전부 써도 메인 20장에 못 미치는 덱이 여럿이라(같은 카드를 여러 장 넣을
   수 있는지가 룰지에 없다) 지금 막으면 못 쓰는 덱이 생긴다. */
let 편집중덱=null, 담은것=new Map(), 저장덱들={};   /* 이름 → 매수 */
function 담은장수(){ let n=0; for(const v of 담은것.values()) n+=v; return n; }
function 담긴목록(){ const 목=[]; 담은것.forEach((수,이름)=>{ for(let i=0;i<수;i++) 목.push(이름); }); return 목; }
function 저장덱읽기(){
  try{ 저장덱들=JSON.parse(localStorage.getItem('뉴네오덱')||'{}'); }catch(e){ 저장덱들={}; }
}
async function 편집열기(){
  await 덱받기();
  if(!카드들.length) 카드들=(await 받기('/api/cards')).카드들||[];
  저장덱읽기();
  const sel=$('편집덱');
  if(!sel.options.length){
    sel.innerHTML=덱들.map(d=>`<option>${벗기기(d.이름)}</option>`).join('');
    sel.value='호박옥';
  }
  if(!편집중덱) 편집덱바꾸기(); else { 편집그리기(); 저장목록그리기(); }
}
function 편집후보(){
  const 이름=편집중덱;
  return 카드들.filter(c=>(c.덱===이름||c.덱==='공용') && c.종류!=='스킬');
}
function 편집덱바꾸기(){
  편집중덱=$('편집덱').value;
  담은것=new Map(편집후보().map(c=>[c.이름,1]));   /* 처음엔 한 장씩 = 지금까지의 기본 덱 */
  편집그리기(); 저장목록그리기();
}
function 편집더(이름, 만큼){
  const 지금=담은것.get(이름)||0;
  const 새것=Math.max(0, Math.min(40, 지금+만큼));
  새것 ? 담은것.set(이름,새것) : 담은것.delete(이름);
  편집그리기();
}
function 편집추천(){
  const d=덱들.find(x=>x.이름===편집중덱);
  const 카드=(d&&d.추천카드)||[];
  담은것=new Map();
  카드.forEach(n=>담은것.set(n,(담은것.get(n)||0)+1));
  편집그리기();
}
function 편집전체(넣나){
  담은것 = 넣나 ? new Map(편집후보().map(c=>[c.이름,1])) : new Map();
  편집그리기();
}
function 편집그리기(){
  const 글=($('편집찾기').value||'').trim().toLowerCase();
  const 후보=편집후보();
  const 보임=후보.filter(c=>!글||c.이름.toLowerCase().includes(글)||(c.텍스트||'').toLowerCase().includes(글));
  $('편집목록').innerHTML=보임.map(c=>{
    const 상급=(c.레벨!=null&&c.레벨>=5), 수=담은것.get(c.이름)||0;
    const 키=벗기기(c.이름).replace(/'/g,"&#39;");
    return `<div class="넣줄${수?' 담음':''}">
      <span class="매수">
        <button onclick="편집더('${키}',-1)">−</button>
        <b>${수}</b>
        <button onclick="편집더('${키}',1)">+</button>
      </span>
      <span>${벗기기(c.이름)}</span>
      <span class="작게">${상급?'상급':'메인'}${c.레벨!=null?' Lv'+c.레벨:''} · ${벗기기(c.덱)}</span></div>`;
  }).join('') || '<div class="귀띔">없다.</div>';
  let 메인=0, 상급=0;
  후보.forEach(c=>{
    const 수=담은것.get(c.이름)||0;
    if(!수) return;
    if(c.레벨!=null&&c.레벨>=5) 상급+=수; else 메인+=수;
  });
  const 벗1=(메인<20||메인>40), 벗2=(상급>20);
  $('편집셈').innerHTML=`<div class="셈줄${벗1?' 벗어남':''}"><span>메인 덱</span><b>${메인} / 20~40</b></div>`
    +`<div class="셈줄${벗2?' 벗어남':''}"><span>상급 덱</span><b>${상급} / 0~20</b></div>`
    +`<div class="셈줄"><span>스킬</span><b>${벗기기((덱들.find(d=>d.이름===편집중덱)||{}).스킬||'')}</b></div>`;
  $('편집경고').textContent = (벗1||벗2)
    ? '룰지 0-1·0-2 범위를 벗어난다 — 쓸 수는 있지만 정식 구성은 아니다.' : '';
}
function 편집저장(){
  const 이름=($('편집이름').value||'').trim() || `${편집중덱} 사용자덱`;
  저장덱들[이름]={덱:편집중덱, 카드:담긴목록()};
  localStorage.setItem('뉴네오덱', JSON.stringify(저장덱들));
  $('편집이름').value='';
  저장목록그리기();
  덱고르개채우기();
}
function 저장불러오기(이름){
  const 하나=저장덱들[이름]; if(!하나) return;
  $('편집덱').value=하나.덱; 편집중덱=하나.덱;
  담은것=new Map();
  (하나.카드||[]).forEach(n=>담은것.set(n,(담은것.get(n)||0)+1));
  편집그리기();
}
function 저장지우기(이름){
  delete 저장덱들[이름];
  localStorage.setItem('뉴네오덱', JSON.stringify(저장덱들));
  저장목록그리기(); 덱고르개채우기();
}
function 저장목록그리기(){
  const 키들=Object.keys(저장덱들);
  $('편집저장목록').innerHTML = 키들.length
    ? `<b class="칸이름" style="margin-top:6px">저장한 덱</b>` + 키들.map(k=>
        `<div class="저장줄"><span>${벗기기(k)} <span class="귀띔">(${벗기기(저장덱들[k].덱)} · ${저장덱들[k].카드.length}장)</span></span>
         <button onclick="저장불러오기('${벗기기(k).replace(/'/g,"&#39;")}')">불러오기</button>
         <button onclick="저장지우기('${벗기기(k).replace(/'/g,"&#39;")}')">지움</button></div>`).join('')
    : '<div class="귀띔" style="margin-top:6px">저장한 덱이 없다. 전부 담긴 상태가 기본이다.</div>';
}

/* ---------- 카드 열람 ---------- */
async function 열람열기(){
  await 덱받기();
  if(!카드들.length) 카드들=(await 받기('/api/cards')).카드들||[];
  덱목록그리기(); 열람그리기();
}
function 덱목록그리기(){
  $('덱목록').innerHTML=`<div class="덱줄${고른덱===null?' 켬':''}" onclick="덱고르기(null)">
      <span>전체</span><span class="잔수">${카드들.length}</span></div>`
    + 덱들.map(d=>`<div class="덱줄${고른덱===d.이름?' 켬':''}" onclick="덱고르기('${벗기기(d.이름)}')">
        <span>${벗기기(d.이름)}${d.효과있음?'':'<span class="덱표">효과 미구현</span>'}</span>
        <span class="잔수">${d.메인+d.상급+1}</span></div>`).join('');
}
function 덱고르기(이름){ 고른덱=이름; 덱목록그리기(); 열람그리기(); }
function 열람그리기(){
  const 글=($('찾기').value||'').trim().toLowerCase();
  const 걸린것=카드들.filter(c=>
    (고른덱===null || c.덱===고른덱 || c.덱==='공용') &&
    (!글 || c.이름.toLowerCase().includes(글) || (c.텍스트||'').toLowerCase().includes(글)));
  $('열람셈').textContent=`${걸린것.length}장`
    + (고른덱?` · ${고른덱}(공용 포함)`:'')+(글?` · "${글}"`:'');
  열람보임=걸린것;      /* 눌렀을 때 찾을 수 있게 — JSON 을 onclick 에 끼우면 따옴표가 깨진다 */
  $('카드목록').innerHTML=걸린것.map((c,i)=>{
    const 수치=c.공!=null?`${c.공}/${c.수}`:(c.종류||'');
    return `<div class="목록줄${고른카드이름===c.이름?' 켬':''}" onclick="열람상세(${i})">
      <span>${벗기기(c.이름)}</span>
      <span class="작게">${벗기기(c.덱)} · ${벗기기(수치)}${c.레벨!=null?' · Lv'+c.레벨:''}</span></div>`;
  }).join('') || '<div class="귀띔">없다.</div>';
}
function 열람상세(자리){
  const c=열람보임[자리]; if(!c) return;
  고른카드이름=c.이름;
  const 메타=[c.덱,c.종류,c.레벨!=null?`레벨 ${c.레벨}`:null,
    c.공!=null?`${c.공} / ${c.수}`:null,c.색].filter(Boolean).join(' · ');
  $('열람상세').innerHTML=`<h3 style="margin:0 0 2px;font-size:14px">${벗기기(c.이름)}</h3>
    <div class="메타">${벗기기(메타)}</div><pre>${벗기기(c.텍스트||'(텍스트 없음)')}</pre>`;
  열람그리기();
}

/* ---------- 판이 끝났을 때 ---------- */
function 덱경고그리기(d){
  const 말=[];
  for(const 자리 of ['나','상대'])
    ((d.덱점검||{})[자리]||[]).forEach(하나=>말.push(`${자리}: ${하나}`));
  $('덱경고').textContent = 말.join(' · ');
  $('덱경고').classList.toggle('숨김', !말.length);
}
function 끝그리기(d){
  const 자리=$('끝자리');
  if(!d.끝){ 자리.innerHTML=''; return; }
  const 덱=d.덱, 설정글=`${덱['나']} vs ${덱['상대']}`;
  자리.innerHTML=`<div class="끝판">
      <div class="끝말"><b>${벗기기(d.끝.승자)} 승</b> — ${벗기기(d.끝.근거)}
        <span class="사람들">(${벗기기(설정글)})</span></div>
      <div class="끝단추">`
    + (d.방장인가
        ? `<button class="주" onclick="다시하기()">같은 설정으로 다시</button>
           <button onclick="덱바꿔다시()">덱 바꿔서 다시</button>`
        : `<span class="사람들">방장이 다시 시작하기를 기다리는 중…</span>`)
    + `<button onclick="메인으로()">메인으로</button></div></div>`;
}
async function 다시하기(){
  const d=await 보내기('/api/rematch',{방,토큰});
  if(d.오류){ $('물음').textContent=d.오류; return; }
  지난판=null; 마지막그림=''; $('끝자리').innerHTML=''; 뽑기();
}
async function 덱바꿔다시(){
  await 덱받기();
  const 목=덱들.map(d=>d.이름);
  const 내=prompt(`내 덱 (${목.join(' / ')})`, 현재덱.나);
  if(!내) return;
  const 상대=prompt(`상대 덱 (${목.join(' / ')})`, 현재덱.상대);
  if(!상대) return;
  if(!목.includes(내) || !목.includes(상대)){ $('물음').textContent='그런 덱이 없다.'; return; }
  const d=await 보내기('/api/rematch',{방,토큰,내덱:내,상대덱:상대});
  if(d.오류){ $('물음').textContent=d.오류; return; }
  지난판=null; 마지막그림=''; $('끝자리').innerHTML=''; 뽑기();
}

/* ---------- 움직임 (판이 바뀐 자리만 짚는다) ---------- */
function 자리쇠(쪽,존,i,c){ return c?`${쪽}/${존}/${i}/${c.이름}`:null; }
function 놓인자리들(b){
  const 모음=new Set();
  if(!b) return 모음;
  for(const 쪽 of ['나','상대']){
    const p=b.쪽[쪽]; if(!p) continue;
    ['유닛','이펙트'].forEach(존=>(p[존]||[]).forEach((c,i)=>{
      const 쇠=자리쇠(쪽,존,i,c); if(쇠) 모음.add(쇠);
    }));
  }
  return 모음;
}
function 움직임보기(b){
  if(!지난판){ 지난판=b; return; }
  /* 새로 생긴 카드 자리 — 소환·로드·특수소환이 전부 여기로 들어온다 */
  const 전=놓인자리들(지난판), 후=놓인자리들(b);
  const 새것=[...후].filter(x=>!전.has(x));
  if(새것.length){
    갓놓인것=new Set(새것);
    setTimeout(()=>{ 갓놓인것=new Set(); }, 500);
  }
  /* HP 가 깎인 쪽을 흔든다 */
  for(const 쪽 of ['나','상대']){
    const 전HP=지난판.쪽[쪽]?.hp, 후HP=b.쪽[쪽]?.hp;
    if(전HP!=null && 후HP!=null && 후HP<전HP) 맞는모습(쪽, 전HP-후HP);
  }
  지난판=b;
}
function 맞는모습(쪽, 깎인양){
  const 매트=document.getElementById(쪽===내자리?'나매트':'적매트');
  if(!매트) return;
  매트.classList.remove('맞음'); void 매트.offsetWidth; 매트.classList.add('맞음');
  setTimeout(()=>매트.classList.remove('맞음'), 500);
  /* 매트는 0.9초마다 통째로 다시 그려진다 — 몸통에 붙여야 숫자가 안 지워진다 */
  const 네모=매트.getBoundingClientRect();
  const 글=document.createElement('div');
  글.className='깎임';
  글.textContent=`-${깎인양}`;
  글.style.left=(네모.left+네모.width/2)+'px';
  글.style.top=(네모.top+10)+'px';
  document.body.appendChild(글);
  setTimeout(()=>글.remove(), 1200);
}

/* ---------- 진행 조절 (AI끼리 두는 판을 보면서) ---------- */
const 배속들=[0.5,1,2,4,0];
async function 진행(몸){ await 보내기('/api/진행',Object.assign({방,토큰},몸)); 마지막그림=''; 뽑기(); }
function 조절그리기(d){
  const 자리=$('조절'), p=d.진행;
  /* 사람이 둘 차례가 아닌 판(AI끼리 두거나 내가 관전)에서만 쓴다 */
  const 보일까 = p && (p.AI끼리 || !d.나의자리) && !d.끝;
  자리.classList.toggle('숨김', !보일까);
  if(!보일까) return;
  자리.innerHTML = `<button class="주" data-짓="멈춤">${p.멈춤?'▶ 이어서':'⏸ 멈춤'}</button>`
    + (p.멈춤?`<button data-짓="한걸음" title="수를 고르는 자리 하나만큼 나간다 — 둘 수가 없어 단계만 넘어가는 자리도 한 걸음이다">한 걸음</button>`:'')
    + `<span class="칸막이"></span>`
    + 배속들.map(v=>`<button data-배속="${v}" class="${p.배속===v?'켬':''}">${v?v+'×':'최대'}</button>`).join('');
}
$('조절').addEventListener('click',e=>{
  const b=e.target.closest('button'); if(!b) return;
  if(b.dataset.배속!==undefined) 진행({배속:parseFloat(b.dataset.배속)});
  else if(b.dataset.짓==='한걸음') 진행({한걸음:true});
  else if(b.dataset.짓==='멈춤') 진행({멈춤:!현재진행.멈춤});
});

/* ---------- 탭 ---------- */
document.getElementById('탭줄').addEventListener('click',e=>{
  const b=e.target.closest('.탭'); if(!b) return;
  document.querySelectorAll('#탭줄 .탭').forEach(x=>x.classList.toggle('켬',x===b));
  document.querySelectorAll('.탭칸').forEach(x=>x.classList.toggle('켬',x.dataset.칸===b.dataset.탭));
});
function 탭열기(이름){
  const b=document.querySelector(`#탭줄 .탭[data-탭="${이름}"]`);
  if(b && !b.classList.contains('켬')) b.click();
}

손길걸기();

설정읽기();
덱고르개채우기();
const 들어온방 = new URLSearchParams(location.search).get('방');
if(들어온방){ if(!$('별명').value) $('별명').value='손님'; 참가(들어온방); }
setInterval(()=>{ 방 ? 뽑기() : (!$('메인').classList.contains('숨김') && 방목록()); }, 900);
방목록();
</script></body></html>
"""


class 듀얼서버(ThreadingHTTPServer):
    """브라우저가 끊고 간 연결을 조용히 넘긴다.

    화면이 0.9초마다 폴링하므로 탭을 닫거나 새로고침하면 그 순간의 요청이 중간에 끊긴다
    (`ConnectionResetError` WinError 10054 · `ConnectionAbortedError` · `BrokenPipeError`).
    서버에는 아무 문제가 없는데 기본 동작이 트레이스백을 통째로 찍어 창을 덮어 버린다 —
    **연결이 끊긴 경우만** 삼키고, 다른 예외는 평소대로 올린다(진짜 버그를 가리면 안 된다).
    """

    def handle_error(self, request, client_address):
        종류 = sys.exc_info()[0]
        if 종류 is not None and issubclass(
            종류, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)
        ):
            return
        super().handle_error(request, client_address)


# ---------------------------------------------------------------------------
# 피드백을 깃허브로 — 사람 손이 중간에 끼지 않게
#
# 사용자 설계(2026-10-28): 테스터 메모가 리포에 쌓이면 야간 루틴이 그걸 보고 스스로
# 고친다. 그러려면 메모가 **저절로** 올라가야 한다. 다만 아무 것이나 올리면 안 된다 —
# `피드백/` 밑만 담고, 다른 변경은 손대지 않는다(작업 트리가 더러워도 그대로 둔다).
# 실패해도 판은 계속 간다. 올리기 전에 rebase pull 로 매시간 도는 루틴 커밋과 겹치는
# 것을 피한다.
# ---------------------------------------------------------------------------

리포뿌리 = Path(__file__).resolve().parent.parent
자동올리기 = False
_올리기자물쇠 = threading.Lock()


def _깃(*인수: str, 시간: int = 60) -> tuple[int, str]:
    된것 = subprocess.run(
        ["git", *인수], cwd=리포뿌리, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=시간,
    )
    return 된것.returncode, (된것.stdout or "") + (된것.stderr or "")


_리포주소캐시: list = []


# 배포본은 이 공개 리포의 DuelModel 가지에서 받는다. git 없이 zip 으로 받은 사람은
# `git remote` 가 없으므로, 화면의 「깃허브 이슈」 가 갈 곳을 여기서 알려 준다.
배포리포 = "https://github.com/somlon/card_simulation_model"


def 리포웹주소() -> str | None:
    """`git remote` 에서 깃허브 웹 주소를 뽑는다. 없으면 배포 리포로 떨어진다."""
    if _리포주소캐시:
        return _리포주소캐시[0]
    주소 = None
    try:
        낌, 글 = _깃("config", "--get", "remote.origin.url", 시간=10)
        값 = 글.strip()
        if 낌 == 0 and 값:
            if 값.startswith("git@"):            # git@github.com:x/y.git
                값 = "https://" + 값[4:].replace(":", "/", 1)
            주소 = 값[:-4] if 값.endswith(".git") else 값
    except (OSError, subprocess.SubprocessError):
        주소 = None
    _리포주소캐시.append(주소 or os.environ.get("뉴네오_리포") or 배포리포)
    return _리포주소캐시[0]


def 피드백올리기(방하나) -> str:
    """`피드백/` 만 커밋해 올린다. 돌려주는 것은 사람이 읽을 한 줄."""
    if not _올리기자물쇠.acquire(blocking=False):
        return "올리는 중 — 다음 메모에 같이 간다"
    try:
        낌, 글 = _깃("add", "--", "피드백")
        if 낌 != 0:
            return "못 올림(add): " + 글.strip()[:120]
        낌, 글 = _깃("diff", "--cached", "--quiet", "--", "피드백")
        if 낌 == 0:
            return "바뀐 게 없다"
        쪽지 = f"피드백 — 방 {방하나.이름} 메모 {len(방하나.메모들)}개"
        낌, 글 = _깃("commit", "-m", 쪽지, "--", "피드백")
        if 낌 != 0:
            return "못 올림(commit): " + 글.strip()[:120]
        _깃("pull", "--rebase", "--quiet", 시간=90)
        낌, 글 = _깃("push", "--quiet", 시간=90)
        if 낌 != 0:
            return "커밋은 됐는데 push 실패 — 다음에 같이 올라간다: " + 글.strip()[:100]
        return "깃허브에 올렸다"
    except (OSError, subprocess.SubprocessError) as 오류:
        return "못 올림: " + str(오류)[:120]
    finally:
        _올리기자물쇠.release()


# ---------------------------------------------------------------------------
# 재정질문 — 룰 해석이 막힌 질문을 개발자에게 직접 묻는 고리 (정본: 재정질문/README.md)
#
# 사용자 설계(2026-10-29): 루틴·세션이 막힌 질문을 `재정질문/<번호>.json` 으로 올리면
# 이 페이지에 뜨고, 테스터는 의견을(데이터), 개발자는 확정 답변을(--재정답변 서버만)
# 남긴다. 서버는 이 폴더만 커밋해 올리고, 야간 루틴이 「답변됨」 을 반영한다.
# ---------------------------------------------------------------------------

재정답변모드 = False
재정뿌리 = 리포뿌리 / "재정질문"
_재정자물쇠 = threading.Lock()


def 질문목록() -> list[dict]:
    목록 = []
    if 재정뿌리.exists():
        for 파일 in sorted(재정뿌리.glob("*.json")):
            try:
                값 = json.loads(파일.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            if isinstance(값, dict) and "번호" in 값:
                목록.append(값)
    return 목록


def _질문쓰기(값: dict) -> None:
    (재정뿌리 / f"{int(값['번호']):03d}.json").write_text(
        json.dumps(값, ensure_ascii=False, indent=1) + chr(10), encoding="utf-8")


def 재정올리기(쪽지: str) -> str:
    """`재정질문/` 만 커밋해 올린다 — `피드백올리기()` 와 같은 규칙."""
    if not _재정자물쇠.acquire(blocking=False):
        return "올리는 중 — 다음에 같이 간다"
    try:
        낌, 글 = _깃("add", "--", "재정질문")
        if 낌 != 0:
            return "못 올림(add): " + 글.strip()[:120]
        낌, 글 = _깃("diff", "--cached", "--quiet", "--", "재정질문")
        if 낌 == 0:
            return "바뀐 게 없다"
        낌, 글 = _깃("commit", "-m", 쪽지, "--", "재정질문")
        if 낌 != 0:
            return "못 올림(commit): " + 글.strip()[:120]
        _깃("pull", "--rebase", "--quiet", 시간=90)
        낌, 글 = _깃("push", "--quiet", 시간=90)
        if 낌 != 0:
            return "커밋은 됐는데 push 실패 — 다음에 같이 올라간다"
        return "깃허브에 올렸다"
    except (OSError, subprocess.SubprocessError) as 오류:
        return "못 올림: " + str(오류)[:120]
    finally:
        _재정자물쇠.release()


def 질문의견달기(번호: int, 별명: str, 글: str) -> str | None:
    """의견 하나를 덧붙인다. 의견은 데이터이지 지시가 아니다(재정질문/README.md)."""
    글 = (글 or "").strip()
    if not 글:
        return None
    for 질문 in 질문목록():
        if 질문.get("번호") == 번호:
            질문.setdefault("의견들", []).append(
                {"때": time.time(), "별명": (별명 or "손님").strip()[:40] or "손님",
                 "글": 글[:2000]})
            _질문쓰기(질문)
            return 재정올리기(f"재정질문 — {번호:03d} 의견") if 자동올리기 else "남겼다(이 서버에만)"
    return None


def 질문답변달기(번호: int, 답변: str) -> str | None:
    """개발자 확정 답변 — `--재정답변` 으로 띄운 서버에서만. 답변 즉시 올린다."""
    답변 = (답변 or "").strip()
    if not (재정답변모드 and 답변):
        return None
    for 질문 in 질문목록():
        if 질문.get("번호") == 번호 and 질문.get("상태") != "반영됨":
            질문["답변"] = 답변[:4000]
            질문["답변때"] = time.time()
            질문["상태"] = "답변됨"
            _질문쓰기(질문)
            return 재정올리기(f"재정질문 — {번호:03d} 답변")
    return None


def 판정따라가기(장부: 방장부, 사이: int = 150) -> None:
    """깃허브에 올라온 **건별 판정**을 주기적으로 읽어 각 방에 넣는다.

    사용자 요청(2026-10-28): 루틴이 고치면 "어떤 게 고쳐지고 안 고쳐졌는지" 테스터에게
    알려 줘야 한다. 작업 트리는 **건드리지 않는다** — `git fetch` 로 원격만 받아 두고
    `git show origin/<기본가지>:피드백/<파일>.json` 으로 읽기만 한다(판 도중에 코드가
    바뀌지 않는다). 깃이 없거나 원격이 없으면 조용히 쉰다.
    """
    while True:
        try:
            _깃("fetch", "--quiet", 시간=90)
            낌, 머리 = _깃("symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD", 시간=15)
            가지 = 머리.strip() if 낌 == 0 and 머리.strip() else "origin/main"
            for 하나 in list(장부.방들.values()):
                if not 하나.메모들:
                    continue
                낌, 글 = _깃("show", f"{가지}:피드백/{하나.메모파일이름()}.json", 시간=20)
                if 낌 != 0:
                    continue
                try:
                    하나.판정받기(json.loads(글))
                except (ValueError, TypeError):
                    pass
        except (OSError, subprocess.SubprocessError):
            pass
        time.sleep(사이)


def 손잡이_만들기(장부: 방장부):
    class 손잡이(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_):
            pass

        def _보내기(self, 몸통: bytes, 종류: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", 종류)
            self.send_header("Content-Length", str(len(몸통)))
            self.end_headers()
            self.wfile.write(몸통)

        def _json(self, 값: dict) -> None:
            self._보내기(
                json.dumps(값, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def do_GET(self):
            쪼갬 = urlparse(self.path)
            if 쪼갬.path == "/api/rooms":
                self._json({
                    "방들": 장부.목록(),
                    "총인원": 장부.총인원(),
                    "최대인원": 장부.최대인원,
                })
                return
            if 쪼갬.path == "/api/state":
                묻기 = parse_qs(쪼갬.query)
                방이름 = (묻기.get("room") or [""])[0]
                토큰 = (묻기.get("token") or [""])[0]
                하나 = 장부.방들.get(방이름)
                if 하나 is None:
                    self._json({"오류": "그런 방이 없다"})
                    return
                try:
                    딕 = 하나.상태딕(토큰)
                    딕["리포"] = 리포웹주소()
                    self._json(딕)
                except KeyError as 오류:
                    self._json({"오류": str(오류)})
                return
            if 쪼갬.path == "/api/questions":
                self._json({"질문들": 질문목록(), "답변가능": 재정답변모드})
                return
            if 쪼갬.path == "/api/decks":
                self._json({"덱들": 덱목록()})
                return
            if 쪼갬.path == "/api/cards":
                self._json({"카드들": 카드목록()})
                return
            if 쪼갬.path == "/api/memo.md":
                묻기 = parse_qs(쪼갬.query)
                하나 = 장부.방들.get((묻기.get("room") or [""])[0])
                if 하나 is None:
                    self._json({"오류": "그런 방이 없다"})
                    return
                몸 = 하나.메모_마크다운().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.send_header("Content-Disposition",
                                 f'attachment; filename="memo-{하나.이름}.md"')
                self.send_header("Content-Length", str(len(몸)))
                self.end_headers()
                self.wfile.write(몸)
                return
            self._보내기(쪽_HTML.encode("utf-8"), "text/html; charset=utf-8")

        def do_POST(self):
            길이 = int(self.headers.get("Content-Length") or 0)
            몸통 = json.loads(self.rfile.read(길이) or b"{}")
            # 길에 한글이 들어가면 브라우저가 퍼센트 인코딩해 보낸다 — 풀어서 본다.
            길 = unquote(urlparse(self.path).path)
            try:
                if 길 == "/api/create":
                    역할 = {"나": 몸통.get("내역할", "사람"),
                            "상대": 몸통.get("상대역할", "헤아림")}
                    고른 = {"나": 몸통.get("내카드") or [],
                            "상대": 몸통.get("상대카드") or []}
                    하나, 사람 = 장부.만들기(
                        몸통.get("별명", ""), 몸통.get("내덱", "호박옥"),
                        몸통.get("상대덱", "던전마스터"), 역할, 고른카드=고른,
                    )
                    self._json({"방": 하나.이름, "토큰": 사람.토큰, "자리": 사람.자리})
                elif 길 == "/api/join":
                    하나, 사람 = 장부.참가(몸통.get("방", ""), 몸통.get("별명", ""))
                    self._json({"방": 하나.이름, "토큰": 사람.토큰, "자리": 사람.자리})
                elif 길 == "/api/answer":
                    하나 = 장부.방들.get(몸통.get("방", ""))
                    됐나 = bool(하나 and 하나.답하기(몸통.get("토큰", ""), 몸통.get("값")))
                    self._json({"됐나": 됐나})
                elif 길 == "/api/leave":
                    됐나 = 장부.나가기(몸통.get("방", ""), 몸통.get("토큰", ""))
                    self._json({"됐나": 됐나})
                elif 길 == "/api/rematch":
                    하나 = 장부.방들.get(몸통.get("방", ""))
                    고른 = None
                    if 몸통.get("내카드") is not None or 몸통.get("상대카드") is not None:
                        고른 = {"나": 몸통.get("내카드") or [],
                                "상대": 몸통.get("상대카드") or []}
                    됐나 = bool(하나 and 하나.다시하기(
                        몸통.get("토큰", ""), 몸통.get("내덱"), 몸통.get("상대덱"),
                        {"나": 몸통.get("내역할"), "상대": 몸통.get("상대역할")},
                        고른카드=고른,
                    ))
                    self._json({"됐나": 됐나} if 됐나
                               else {"오류": "방장만 다시 시작할 수 있다"})
                elif 길 == "/api/진행":
                    하나 = 장부.방들.get(몸통.get("방", ""))
                    if 하나 is None:
                        self._json({"오류": "그런 방이 없다"})
                    else:
                        self._json(하나.대국.진행조절(
                            배속=몸통.get("배속"), 멈춤=몸통.get("멈춤"),
                            한걸음=bool(몸통.get("한걸음")),
                        ))
                elif 길 == "/api/question_memo":
                    결과 = 질문의견달기(int(몸통.get("번호") or 0),
                                   몸통.get("별명", ""), 몸통.get("글", ""))
                    self._json({"올림": 결과} if 결과
                               else {"오류": "그 질문이 없거나 글이 비었다"})
                elif 길 == "/api/question_answer":
                    결과 = 질문답변달기(int(몸통.get("번호") or 0), 몸통.get("답변", ""))
                    self._json({"올림": 결과} if 결과
                               else {"오류": "답변 권한이 없다(--재정답변) 거나 글이 비었다"})
                elif 길 == "/api/memo":
                    하나 = 장부.방들.get(몸통.get("방", ""))
                    메모하나 = 하나 and 하나.메모남기기(
                        몸통.get("토큰", ""), 몸통.get("글", ""), 몸통.get("갈래", "그냥")
                    )
                    if 메모하나 is None:
                        self._json({"오류": "메모를 남길 수 없다 — 방·토큰·글을 확인해라"})
                    else:
                        올림 = 피드백올리기(하나) if 자동올리기 else None
                        self._json({"메모": 메모하나.딕(), "개수": len(하나.메모들),
                                    "올림": 올림})
                else:
                    self._json({"오류": "모르는 길"})
            except (KeyError, ValueError) as 오류:
                self._json({"오류": str(오류)})

    return 손잡이


def _내주소() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as 구멍:
            구멍.connect(("8.8.8.8", 80))
            return 구멍.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def 주문() -> int:
    받기 = argparse.ArgumentParser(description="브라우저로 두는 뉴 네오 듀얼")
    받기.add_argument("--포트", type=int, default=8777)
    받기.add_argument("--최대인원", type=int, default=5, help="서버 전체 동시 인원")
    받기.add_argument("--공개", action="store_true",
                      help="0.0.0.0 에 열어 같은 네트워크의 다른 사람도 들어오게 한다")
    받기.add_argument("--안열기", action="store_true", help="브라우저를 자동으로 안 연다")
    받기.add_argument("--피드백올리기", action="store_true",
                      help="메모가 쌓일 때마다 피드백/ 만 커밋해 깃허브에 올린다")
    받기.add_argument("--재정답변", action="store_true",
                      help="재정 질문에 확정 답변을 적을 수 있게 한다(개발자 전용)")
    인수 = 받기.parse_args()

    global 자동올리기, 재정답변모드
    자동올리기 = 인수.피드백올리기
    재정답변모드 = 인수.재정답변
    장부 = 방장부(인수.최대인원)
    주인 = "0.0.0.0" if 인수.공개 else "127.0.0.1"
    # 배포본은 남의 PC 에서 돈다 — 그 포트를 다른 것이 쓰고 있으면 옆 포트로 비킨다.
    서버 = None
    for 더하기 in range(12):
        try:
            서버 = 듀얼서버((주인, 인수.포트 + 더하기), 손잡이_만들기(장부))
            인수.포트 += 더하기
            break
        except OSError:
            continue
    if 서버 is None:
        print(f"포트 {인수.포트}~{인수.포트 + 11} 가 전부 쓰이고 있다 — --포트 로 다른 번호를 주거라.")
        return 1
    내주소 = f"http://127.0.0.1:{인수.포트}/"
    print(f"듀얼 서버 — 정원 {인수.최대인원}명")
    print(f"  나:        {내주소}")
    if 인수.공개:
        print(f"  다른 사람: http://{_내주소()}:{인수.포트}/   (같은 네트워크)")
        print("  인터넷 너머면 Tailscale 같은 터널을 쓸 것 — 이 서버엔 인증이 없다.")
    if 자동올리기:
        print("  피드백: 메모가 쌓일 때마다 피드백/ 만 커밋해 깃허브로 올린다")
    if 재정답변모드:
        print("  재정: 확정 답변 입력이 켜져 있다 — 답변 즉시 재정질문/ 만 커밋해 올린다")
    if 리포웹주소():
        threading.Thread(target=판정따라가기, args=(장부,), daemon=True).start()
        print("  판정: 루틴이 고친 결과를 2분 30초마다 받아 메모 옆에 표시한다")
    print("Ctrl+C 로 끝낸다.")
    if not 인수.안열기:
        threading.Timer(0.6, lambda: webbrowser.open(내주소)).start()
    try:
        서버.serve_forever()
    except KeyboardInterrupt:
        print("\n끝냄.")
    return 0


if __name__ == "__main__":
    raise SystemExit(주문())
