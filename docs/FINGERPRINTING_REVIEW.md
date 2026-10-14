# Tor-iOS privacy review — 2026-10-14

Base: `01e1897f4042961fdada3cf32043f04447fea952`. Reynard:
`ddaacd18b8c5661d495acfc0f3e90a86c484e64d`. Gecko: `FIREFOX_157_0_1_RELEASE`.

## 결과와 증거의 한계

이번 작업은 소스 수정·로컬 테스트이다. 새 IPA 빌드, Gecko 전체 컴파일,
macOS Swift/UIKit 컴파일, 실제 Gecko 페이지 실행, iPhone 설치·패킷 캡처를 하지 않았다.
사용자가 보고한 기존 빌드의 지문 변화는 새 코드의 검증 결과가 아니다.
원본 접속 IP·이미지 Signature·접속 기록은 이 문서와 테스트에 저장하지 않았다.

고정된 Gecko 원본 파일과 Reynard의 실제 패치를 읽고 패치를 적용한 소스로
변환을 검증했다. 최신 Tor Browser GitLab 원문 및 디자인 문서는 접근 오류/403으로
확보하지 못했다. 공식 Tor 문서와 공개 변경 기록에서 전략을 비교했으며,
최신 Tor 전체 소스 감사나 완전한 패치 이식으로 표현하지 않는다.

## 발견 사항과 심각도

| 심각도 | 문제와 근거 | 이번 처리 | 남은 확인 |
|---|---|---|---|
| Critical | 실제 IP가 Tor 실패 시 직접 연결로 샌다는 재현 증거는 이번 작업에서 없음 | 발견하지 못했다고 해서 부재가 증명된 것은 아님 | 실통신 캡처 필요 |
| High | private-only의 실제 탭/확장/다운로드 경로는 Mock으로 입증할 수 없음. 앞선 일반 탭 오분류 이력도 있음 | 기존 fail-closed 라우팅과 잠긴 설정 수정 보존 | 일반/개인 탭, 확장 배경 요청의 실제 출구 비교 |
| High | 일시 정지가 Tor DisableNetwork에 의존. 앱/Gecko 차원의 독립적인 요청 차단 장치가 없어 제어 명령 실패 시 Tor 통신이 계속될 가능성 | 이번에는 변경하지 않음. 직접 연결 fallback 문제와 구분 | 제어 연결 실패를 주입하고 새 요청 및 기존 WebSocket 시험 |
| Medium | RFP 헤더에 XP_IOS 분기가 없어 Linux 데스크톱 UA/oscpu와 iPhone platform이 혼합됨. 실제 패치와 보고값이 일치 | iOS RFP를 Gecko의 기존 Android 모바일 표준값에 맞추고 창·Worker platform 처리 추가 | HTTP 헤더/JS/Worker, CSS/터치, 사이트 호환성 확인 |
| Medium | 세션별 custom identity가 Navigator RFP보다 먼저 반환될 수 있음. Swift만 바꾸면 다른 세션 생산 경로를 보장하지 못함 | GeckoView 설정 브리지에서 UA 모드를 mobile로 고정하고 다섯 identity override 제거 | 권한 있는 확장 자체의 webRequest/DOM 조작까지 금지한 것은 아님 |
| Medium | UI가 private-only에서 클라이언트 Connected를 일반 탭의 Tor 연결처럼 표시 | 선택 탭 유형·활성 세션 정책·Tor 클라이언트 상태를 분리 | 채널별 실제 프록시 계측은 아님; 클라이언트 상태 조회 지연도 별도 위험 |
| Medium | 화면/폰트/오디오/렌더링/확장 조합이 공식 Tor와 다른 지문 집단을 만들 수 있음 | 검사 도구 및 확인 절차 추가; 검증 없이 값을 임의 변경하지 않음 | 실제 디바이스·공식 Android Tor와 비교 |
| Low | UI/Accept-Language 영어 설정만으로 Intl 기본 locale 표준화까지 보장할 수 없음 | Gecko 157에 존재하는 privacy.spoof_english=2 추가 | Intl/Date와 HTTP Accept-Language 검사 |

심각도는 확인된 영향과 검증 공백을 구분한 프로젝트 위험 평가이다. High 항목은
실제 IP 누출을 재현했다는 주장이 아니다. 플랫폼 불일치는 식별에 쓸 수 있는
특징이지만 몇 비트의 정보가 추가되는지, 개인을 장기간 추적할 수 있는지는 측정하지 못했다.

## 실제 변경

* `scripts/fingerprinting-policy.py`: 고정된 패치 후 소스에만 적용하는 변환. 앵커가 바뀌거나
  중복되면 중단한다. nsRFPService.h에서 iOS가 Android의 UA OS/appVersion/oscpu/
  maxTouchPoints 상수를 공유하도록 한다. nsRFPService.cpp에서 UA의 Gecko suffix도
  Android 모바일 경로와 맞춘다. 버전 숫자는 엔진의 MOZILLA_UAVERSION을 사용한다.
* `scripts/apply-overlay.py`: 위 변환을 기존 engine phase에서 호출. 탭 선택/생성/세션 교체
  delegate가 상태 표시를 갱신하도록 앱 패치 추가.
* `overlay/Gecko/TBIOPrivacy.sys.mjs`: 설정 객체를 복사하여 identity override만 제거하고
  mobile UA 모드를 선택. private 상태·viewport 모드·JavaScript·기타 설정은 보존한다.
* `privacy-prefs.json`: `privacy.spoof_english: 2`만 추가. RFP는 기존처럼 모든 라우팅 모드에 적용.
* `overlay/Reynard/Tor/TorBrowserStatus.swift`: 현재 선택된 UI 탭 유형, 엔진 세션의 private
  상태 및 활성 라우팅 정책을 사용한다. Direct 정책인 탭에 Tor Connected를 표시하지 않는다.
* `tests/test_fingerprinting.py`, `tests/fingerprinting-settings.mjs`, `tests/test_overlay.py`:
  소스 변환·앵커 실패·컴파일러 전처리·세션 bridge 회귀 검사.
* `tests/runtime/`: 저장/텔레메트리 없는 수동 런타임 검사 페이지·Worker·개발용 HTTP 서버.
  JS/서버는 영어. 렌더링 API를 호출하는 준비물이며 아직 실행 결과는 없다.

예상 iOS RFP 정보는 Android 10 Mobile UA, `platform=Linux armv81`,
`oscpu=Linux armv81`, `appVersion=5.0 (Android 10)`, maxTouchPoints=5이다.
Gecko가 이미 사용하는 문자열 그대로이며 armv81 표기를 독자적으로 수정하지 않았다.
RFP가 적용되지 않는 system caller의 native platform은 iPhone으로 남는다.
실제 Android 엔진/OS로 바뀌는 것이 아니므로 폰트·코덱·CSS·그래픽 차이는 남는다.
공식 Tor 사용자와 같은 anonymity set에 들어간다고 주장하지 않는다.

## 공식 Tor / Gecko / 현재 앱 비교

| 표면 | 공식 Tor 전략 | 고정 Gecko 157 및 현재 앱 | 이번 처리 / 구현 한계 |
|---|---|---|---|
| RFP | 사용자 집단 내 표준화 | RFP locked=true, exemptedDomains 비움 | 보존; 실제 각 target 적용은 런타임 확인 |
| UA/JS identity | 플랫폼별 소수 표준값과 헤더/JS 정합성 | Gecko iOS 누락 + Reynard custom override 우선 경로 | 모바일 표준값 공유·세션 override 제거; HTTP/Worker 실제 확인 필요 |
| Canvas | 추출 제한 | CanvasUtils의 permission/target 기반 placeholder·randomize 경로, CanvasRenderingContext2D 및 HTMLCanvasElement 추출 코드 존재 | 기존 구현 보존; toDataURL/toBlob/getImageData/텍스트/OffscreenCanvas 검사 준비 |
| WebGL | 환경/추출 정보 축소 | ClientWebGLContext에 Mozilla renderer/vendor, capability target, readPixels/getBufferSubData 노이즈 경로 존재 | 기본 WebGL 1/2 유지. extension 목록·precision·float/PBO 등 전체 동등성 미검증 |
| 화면/letterboxing | 실제 콘텐츠 영역을 크기 집단으로 맞춤 | 앱의 UIKit/GeckoView host에 letterboxing 구현 없음 | preference 추가 안 함. 키보드·회전·visualViewport·touch 좌표 포함한 native layout 작업 필요 |
| 폰트 | 열거 제한·fallback | FontVisibilityProvider의 RFP base visibility 있음. iOS 폰트 패치에 별도 system serif family 경로 있음 | 시스템 family 경로가 visibility 제한과 일관되는지 미검증. 공통 폰트 묶음/폭/한글 fallback 이식 필요 |
| AudioContext | RFP 및 보안 수준 제한 | AudioContext.cpp에 AudioContext/AudioSampleRate target 존재. AudioBuffer.cpp만으로 sample extraction 보호를 입증할 수 없음 | Web Audio enabled는 취약점 증거가 아님. OfflineAudioContext render hash 검사 준비; AudioWorklet 등 미포함 |
| SpeechSynthesis | 노출 표면 제한 | SpeechSynthesis.cpp getVoices/voiceschanged의 RFP 차단 경로 | 보존; 늦게 로드되는 voices를 포함한 기기 확인 필요 |
| 시간/언어 | 소수 locale/시간대·타이머 값 | RFP JSDateTimeUTC/ReduceTimerPrecision, 영어 language manager. JSLocale은 spoof_english=2 필요 | 추가 locale 설정. Reykjavik은 UTC와 offset이 같을 수 있으나 Intl timezone 이름의 표준화까지 증명하지 않음 |
| 하드웨어/터치/센서 | 값 축소·입력 호환성 균형 | RFP concurrency/maxTouchPoints/touch/pointer targets. 센서·배터리·WebGPU disabled | 터치 입력 유지, 실제 기기 수치라고 단정 안 함. deviceMemory/Client Hints 지원 여부 검사 준비 |
| FPI/상태 | first-party 경계 | FPI=true, 메모리 기록, 디스크 캐시 차단, 쿠키 제한. Tor SOCKS 자격 증명은 사이트/컨텍스트별 분리 | 보존. 쿠키/스토리지/서비스 워커 실제 분리 검사 필요; 네이티브 요청은 사이트별 SOCKS 자격 증명 분리까지 구현되지 않음 |
| WebRTC/DNS | 누출 경로 차단 | WebRTC/HTTP3 disabled, Tor SOCKS remote DNS, 직접 fallback 금지. mixed/off에서는 direct 탭을 위해 OS DNS 허용 | 라우팅 보존. direct 탭의 DNS는 의도된 동작; Tor 탭의 hostname 누출과 별도 판정 |
| NoScript/보안 수준 | Standard/Safer/Safest 및 NoScript | 확장 지원·전체 JS block 스위치 있으나 공식 레벨과 동일하지 않음. JIT/Wasm 등 이미 제한 | NoScript를 자동 설치하거나 레벨을 허위로 표시하지 않음. 추가 확장/DOM 변경은 지문을 바꿀 수 있음 |
| CSS/DPR/viewport | RFP 표면 축소 + host 크기 제어 | touch/pointer target 존재하지만 iOS 레이아웃/그래픽은 실제 | DPR·pointer/hover·회전·dark/reduced-motion 검사 준비. 데스크톱 흉내를 위해 터치 제거하지 않음 |
| WebExtension | 기본 구성 정합성 중요 | popup/복원 설정 bridge 보호 추가, 확장은 여전히 권한과 독자 통신 가능 | 설치 전후 DOM·canvas·HTTP·배경 통신 비교 필요. 확장 지원 보존 |

공식 Tor 기능 설명은 아래 공식 문서에 근거한 전략 비교이다. 해당 버전의 Tor 코드
전체와 이 앱의 동일 동작을 확인한 표가 아니다. Gecko의 경로가 존재하는 것과 현재
iOS 빌드에서 적용되는 것은 구분한다.

## 기존 정상/보호 경로를 보존한 항목

Canvas 및 WebGL 랜덤화는 변경하지 않았다. Report Hash가 고정된 것은 환경 값을
표준화하는 설계와 양립한다. Image Hash 변화는 추출 보호 가능성을 보여주지만,
원본 픽셀이 다른 API나 permission 예외에서 노출되지 않는다는 증거가 아니다.
3개의 짧은 Signature로 seed 수명·엔트로피·사이트 간 연결 가능성은 측정할 수 없다.

기존 Tor.framework, Gecko 통합, 확장 지원, 서명·패키징, Privacy UI 토글/릴레이,
세 라우팅 모드, failover_direct=false, native allowFailover=false, WebRTC/HTTP3
차단, 메모리 기록, external navigation 제한을 유지했다. 워크플로는 수정하지 않았다.

| 활성 모드 | 일반 탭 | 사생활 보호 탭 |
|---|---|---|
| Always | Tor | Tor |
| Private Tabs Only | Direct | Tor |
| Tor Off | Direct | Direct |

이 표는 정책이다. Node 모의 검사는 이 선택을 검증하지만 실제 IP 경로를 증명하지 않는다.
출처가 불분명한 네이티브 보조 요청의 private-only 차단도 보존했다.

## 실행한 검사

* Python unittest: 33개 통과. 1개는 pinned Reynard **선별 원본 파일 + 합성 engine 앵커**의
  변환 통합 검사이다. 완전한 upstream checkout/Gecko 빌드 테스트라고 부르지 않는다.
* 그중 새 5개: 변경/중복 앵커 거부, 중복 적용 거부, RFP/locale 정책, 탭 상태 표시 경로, 실제 Gecko 157
  파일에 Reynard 패치를 적용한 소스 변환 및 C++ 전처리기의 5 플랫폼 identity 분기.
  C++ 전처리 검사는 헤더의 identity section만 실행; C++ 엔진 전체 컴파일 아님.
* Node 기존 라우팅·격리: 10+9+4+1+10 모의 사례 통과. 새 session identity: 4 모의 유형 통과.
* runtime JS 문법 검사 및 SHA-256 known-answer 검사 통과.
* 개발용 서버: 4 localhost HTTP smoke 검사 통과. Tor·DNS·iPhone 검사 아님.
* 실제 Canvas/WebGL/Audio 렌더링 probe, Swift/UIKit 컴파일, native Foundation 프록시 테스트,
  Gecko 브라우저 런타임, iPhone, WebSocket/미디어/다운로드 누출 실험은 **실행하지 않음**.

다시 실행:

```sh
python -m unittest discover -s tests -v
node tests/tor-isolation.mjs
node tests/fingerprinting-settings.mjs
```

선택 검사에는 UPSTREAM_SOURCE 및 GECKO_REVIEW_SOURCE가 필요하다. 기본 실행에서
자료가 없으면 해당 검사가 skipped되는 것은 정상이며, 통과로 계산하면 안 된다.
GECKO_REVIEW_SOURCE는 engine overlay 적용 전의 **Reynard 패치 후 Gecko 157 소스**이다.

## iPhone 추가 검증 절차

1. 변경을 포함한 새 빌드 설치 및 완전 종료/재실행. 먼저 일반/개인 탭에서 같은
   HTTPS 원점의 서버 수신 UA와 JS/Worker UA·platform·appVersion·oscpu를 비교한다.
   정상 HTTP UA에 Android 10/Mobile이 있고 창/Worker 표준값이 맞아야 한다.
   Client Hints는 지원 여부와 실제 헤더 모두 확인한다. 비지원이면 null/헤더 없음으로 기록.
2. `tests/runtime/index.html`을 직접 관리하는 HTTPS 원점에 올려 probe 실행.
   페이지는 외부 서비스에 전송하거나 저장하지 않는다. 서버 echo 버튼만 같은 원점에
   명시적으로 요청한다. 개발 서버는 loopback에 bind하므로 iPhone/Tor의 localhost
   제한을 우회하지 않는다. 공개 HTTPS 테스트 원점으로 제공하는 것은 별도 작업이다.
3. 같은 페이지에서 2회, 새로고침, 새 일반/개인 탭, 다른 first-party 원점,
   모든 개인 탭 종료 후 재개, 앱 재실행 순으로 비교한다. 동일 입력을 사용한다.
   raw pixels/encoded PNG/JS 배열 해시를 서로 같은 해시가 되어야 한다고 비교하지 않는다.
   각 API의 해시끼리 재현성·사이트/세션 변화만 비교한다. seed가 매 추출마다 바뀌어야
   한다는 기준을 만들지 않는다. permission 허용 전/후도 별도로 확인한다.
4. Canvas getImageData/toDataURL/toBlob, OffscreenCanvas convertToBlob, Worker
   OffscreenCanvas, WebGL1/2 readPixels, WebGL2 PBO getBufferSubData를 확인한다.
   ImageBitmap/ImageData 전달, float formats, transform feedback, 서비스 워커 등은
   현 probe에 없는 추가 검사이다. 표준화된 GPU 문자열만으로 capability 지문을 배제하지 않는다.
5. OfflineAudioContext hash, 폰트 폭/fallback, DPR/viewport/screen, CSS pointer/hover,
   timezone 이름/offset 및 Intl locale, speech voices를 확인한다. font 폭만으로 설치된
   폰트 목록을 확정할 수 없다. voices가 늦게 로드되면 다시 검사한다.
6. 확장 0개/기존 확장 활성화/비활성화에서 비교한다. 광고차단 Yes나 EFF Unique는
   해당 표본·테스트 결과로만 해석한다. 실제 사용자 집단 동일성 평가와 구분한다.
7. 관리하는 서버에서 Always/PrivateOnly/Off의 양쪽 탭을 비교. HTTPS 역방향 프록시가
   있으면 echo의 socketPeer는 프록시 IP이며 TLS ingress에서 원래 peer를 확인해야 한다.
   임의 X-Forwarded-For를 신뢰하지 않는다. 서버 IP만으로 DNS 누출은 판정하지 않는다.
8. Tor 포트 거부/중단/제어 실패를 만들고 캐시되지 않은 nonce URL, 리다이렉트,
   새 WebSocket, 연결 중인 WebSocket, 미디어 range, 네이티브 다운로드, favicon,
   확장 배경 fetch를 시험한다. Tor 대상은 direct로 전환되면 안 된다. 직접 탭은 계속
   direct가 되는 정책이다. 앱 status 문구는 합격 기준이 아니다.
9. 라우터/테스트망 캡처 및 관리하는 authoritative DNS에서 Tor 대상 hostname 질의를
   확인한다. 일반 탭 direct DNS 및 Tor 자체 부트스트랩 DNS와 구분한다. RTCPeerConnection
   생성/ICE 후보가 disabled인지 확인하고 local address 및 external scheme 차단도 검사한다.
   실제 사용자 browsing 대신 시험 도메인만 사용하며 저장소에 로그를 올리지 않는다.

## 호환성과 미완료 작업

Android UA를 보고 사이트가 Android 앱 링크/전용 기능을 제안할 수 있다. iOS 코덱·폰트
차이로 플랫폼 검출이 완전히 일치하지 않을 수 있다. custom UA를 요구하는 사이트의
우회 기능은 의도적으로 제한된다. Intl 기본 locale 영어화가 날짜/숫자 표시를 바꿀 수 있다.
상태 문구가 길어져 작은 화면에서 줄임이 생길 수 있어 UI 실기기 QA가 필요하다.

Letterboxing과 공통 폰트 집합, 독립적인 pause 차단, 네이티브 사이트별 회선 자격 증명,
공식 NoScript security levels 및 확장별 네트워크 계측은 미구현이다. 근거 없이
preference만 추가하거나 WebGL/Audio를 기본으로 꺼서 기존 동작을 바꾸지 않았다.
Canvas textMetrics/CSS 렌더링은 픽셀 노이즈와 별도 지문 표면이다.

이번 수정에는 C++ identity 경로 변경이 포함된다. 새 엔진 빌드가 필요하며 JS 리소스만
다시 패키징하여 기존 바이너리에 반영할 수 없다. 빌드/캐시 workflow 변경이나 Actions
실행은 하지 않는다. main 배포·실기기 확인 전까지 '수정 배포 완료'라고 표현하지 않는다.

## 원문

* [Tor fingerprinting strategy](https://support.torproject.org/tor-browser/features/fingerprinting-protections/)
* [Tor security levels](https://support.torproject.org/tor-browser/features/security-levels/)
* [Gecko 157 nsRFPService.h](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/toolkit/components/resistfingerprinting/nsRFPService.h)
* [Gecko 157 nsRFPService.cpp](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/toolkit/components/resistfingerprinting/nsRFPService.cpp)
* [Gecko 157 Navigator.cpp](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/dom/base/Navigator.cpp)
* [Gecko 157 CanvasUtils.cpp](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/dom/canvas/CanvasUtils.cpp)
* [Gecko 157 ClientWebGLContext.cpp](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/dom/canvas/ClientWebGLContext.cpp)
* [Gecko 157 AudioContext.cpp](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/dom/media/webaudio/AudioContext.cpp)
* [Gecko 157 FontVisibilityProvider.cpp](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/toolkit/components/resistfingerprinting/FontVisibilityProvider.cpp)
* [Pinned Reynard Navigator patch](https://github.com/minh-ton/reynard-browser/blob/ddaacd18b8c5661d495acfc0f3e90a86c484e64d/patches/dom/base/Navigator.cpp.patch)
* [Pinned Reynard Worker patch](https://github.com/minh-ton/reynard-browser/blob/ddaacd18b8c5661d495acfc0f3e90a86c484e64d/patches/dom/workers/WorkerNavigator.cpp.patch)
