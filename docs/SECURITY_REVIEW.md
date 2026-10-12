# Tor Browser 소스 검토와 iOS 적용 결과

검토일: 2026-10-12. 대상: Reynard `ddaacd18b8c5661d495acfc0f3e90a86c484e64d`, Gecko `FIREFOX_157_0_1_RELEASE`.

Tor Browser 전체 저장소의 완전한 감사나 전체 패치 이식 결과가 아니다. GitLab 원본 raw 접근이 제한되어 Tor Project가 공식 커밋 메일로 공개한 소스와 변경사항을 검토했다. 과거 기본 설정 덤프는 최근 설정 변경 및 현재 Gecko 정의와 대조했으며, 오래된 설정을 그대로 복사하지 않았다.

## 검토한 공식 소스

- [000-tor-browser.js 초기 소스](https://archive.torproject.org/websites/lists.torproject.org/pipermail/tor-commits/2022-October/238229.html): 프록시 우회 방지, 원격 DNS, 브라우저와 Tor의 연결 경계.
- [001-base-profile.js 소스](https://archive.torproject.org/websites/lists.torproject.org/pipermail/tor-commits/2022-October/238538.html): 사생활 모드, 지문 방어, 디스크 기록과 백그라운드 통신 제한.
- [2026-09 프록시 설정 재검토](https://lists.torproject.org/mailman3/hyperkitty/list/tor-commits@lists.torproject.org/message/J24F7RWVKLQENZM3RLL4M5XAZQ7RNYQR/): 로컬 네트워크 접근 제한, DNS 차단, onion HTTPS 예외, HTTP/3 차단.
- [SecurityLevel.sys.mjs 설정표](https://lists.torproject.org/mailman3/hyperkitty/list/tbb-commits@lists.torproject.org/thread/WW4KDJ745IFDZ6S23ID3GYNJICLT4UM2/): JavaScript JIT, 정규식 JIT, WASM, 폰트 렌더링 기능 제한. NoScript와의 연동은 이번에 이식하지 않았다.
- [2026-03 WebGPU 제한 변경](https://lists.torproject.org/mailman3/hyperkitty/list/tbb-commits@lists.torproject.org/2026/3/?count=25&page=3): 검증되지 않은 GPU API의 공격·지문 표면 제한.
- [Gecko 정적 설정 정의](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/modules/libpref/init/StaticPrefList.yaml), [동적 설정 정의](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/modules/libpref/init/all.js): 적용할 설정이 현재 엔진에 실제 존재하는지 확인.
- [Gecko 프록시 API](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/netwerk/base/nsIProtocolProxyService.idl), [채널 필터 계약](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/netwerk/base/nsIProtocolProxyFilter.idl), [구현](https://github.com/mozilla-firefox/firefox/blob/FIREFOX_157_0_1_RELEASE/netwerk/base/nsProtocolProxyService.cpp): SOCKS 인증, 연결 풀 격리 키, 원격 DNS 플래그, 실패 시 fallback 처리.

## 보호 구조와 적용

| 보호 목적 | 이번 구현 | 검증 범위 / 한계 |
| --- | --- | --- |
| 실제 IP·DNS 누출 방지 | SOCKS 강제, 로컬 DNS 비활성화, DoH·WebRTC·HTTP/3 차단, 프록시 예외 제거 | 설정 목록·잠금·네이티브 proxy 검사. 실기기 전체 트래픽 캡처는 미실시 |
| 로컬 서비스 공격 방지 | Gecko LNA 활성화 및 차단, 최상위 로컬 접근 허용 해제, Tor의 내부 IP/DNS 응답 거부 | 네이티브는 기존 IP literal/localhost 차단 유지. LNA는 실기기 검사 필요 |
| 사이트 사이 추적 제한 | FPI, 제3자 쿠키 차단, 최상위 사이트별 임시 SOCKS 자격 증명 | Gecko 채널에 firstPartyDomain이 실제 전달되는지 기기에서 확인해야 함 |
| 회로 격리 | firstPartyDomain·privateBrowsingId·userContextId별 임의 인증값과 연결 풀 키 | 같은 CDN도 첫 사이트가 다르면 다른 자격 증명. Foundation 요청은 Gecko 자격 증명을 공유하지 않음 |
| 알 수 없는 요청 문맥 | 요청마다 다른 자격 증명 | 격리를 보수적으로 강화하므로 회로 수·지연이 늘어날 수 있음 |
| 공격 표면 축소 | 웹 JavaScript JIT·정규식 JIT·WASM·WebGPU·Graphite·SVG OpenType 폰트·센서·배터리·DRM 비활성화 | 일부 사이트의 성능과 기능이 제한됨. WebGL·일반 SVG 전체 차단은 하지 않음 |
| 스크립트 완전 차단 | Tor 화면에서 다음 실행의 JavaScript 허용/차단 선택 | 앱을 완전히 종료하고 재실행해야 반영. NoScript의 사이트별 예외 및 공식 3단계 보안 수준과 다름 |
| 통신 암호화 | HTTPS-Only 및 사생활 모드 HTTPS-Only 고정, onion 자동 HTTPS 업그레이드 예외 | onion 서비스 자체의 Tor 암호화 때문에 HTTP onion을 무조건 HTTPS로 바꾸지 않음 |
| 디스크의 탐색 흔적 축소 | 방문 기록·탭·권한·파비콘 SQLite DB를 메모리로 전환. 탭/탐색 썸네일·사이트 메타데이터도 메모리 저장. HTTP 디스크 캐시 비활성화 | OS 스냅샷·충돌 기록·사용자 명시적 다운로드까지 제거하는 기능은 아님 |
| 이전 버전 기록 정리 | 시작 시 AppData의 History, TabManagement, TabSessions, Favicons, SiteMetadata, SitePermissions 삭제 | 즐겨찾기·명시적 다운로드·일반 설정·JIT pairing·Tor guard 상태 유지 |
| 외부 앱으로 IP 노출 방지 | 일반 탐색·리다이렉트·iframe·팝업의 외부 URL 스킴 차단 | 사용자가 다운로드 파일을 다른 앱으로 열면 그 앱의 통신 정책은 별개 |
| 지문 방어 우회 방지 | RFP 예외 목록 고정, 사이트별 UA/appVersion/oscpu/buildID override 사용 중단, 웹 언어 en-US/en 통일 | iOS 렌더링·터치·폰트·실제 viewport 등을 공식 Tor Browser 집단과 동일하게 만들지는 못함 |
| 잘못된 설정에 대한 방어 | 기본 설정 로딩 시 잠금, profile startup 재잠금, Swift 기본 설정 bridge 필터, Gecko 설정 이름 검사 | 이름 존재 검사는 기능의 런타임 작동을 증명하지 않음 |

## 중요한 정정과 미이식 기능

- 이전의 `privacy.resistFingerprinting.letterboxing=true` 표시는 창 크기를 맞추는 UI 구현이 없는 상태였다. 현재 Gecko 중앙 설정 정의에도 해당 키가 없어 제거했다. **letterboxing은 미구현**이다. 제거된 `network.predictor.enabled`도 삭제했고 현재의 DNS prefetch·speculative 연결 차단은 유지했다.
- 공식 Tor Browser의 전체 Canvas/WebGL/폰트/화면 크기 보호, 번들 폰트, Tor 전용 패치 전체, NoScript, obfs4/Snowflake는 이식하지 않았다.
- 새 회로 버튼은 기존 NEWNYM이다. 열려 있는 연결·쿠키·탭을 모두 정리하는 New Identity는 아니다. 사이트별 인증값도 실행 중 유지된다.
- Tor guard 상태를 지우지 않는다. 매번 가드를 무작위로 바꾸는 것은 익명성 향상으로 간주하면 안 된다.
- Safe Browsing 원격 조회와 addon 자동 업데이트는 기존에 꺼져 있다. 외부 통신을 줄이는 대신 피싱/악성 사이트 경고 및 업데이트 관리가 약해지는 한계가 있다. 브라우저·Tor 보안 업데이트를 정기적으로 배포해야 한다.
- 일반 설정 화면의 UA/언어·HTTPS/DoH 등의 기존 컨트롤보다 잠긴 보안 정책이 우선한다. 해당 컨트롤 전체의 UI 정리는 후속 작업이다.
- JIT 개발자 연결과 Apple 개발자 이미지 설정 다운로드는 기존 직접 연결 경로다. 브라우징 요청과 다르며, 이에 대한 기기 전체 VPN 보호는 제공하지 않는다.

## 검증

- Python 정책·원본 소스 적용 통합 검사 8개 통과. 실제 고정 Reynard checkout에 변환을 적용하고, 자동 탐색 저장 경로에서 파일 읽기·쓰기가 제거됐는지 검사했다.
- Node SOCKS 필터 로직 검사 10개 통과. 동일 사이트 유지, 다른 사이트/사생활/컨테이너 분리, 문맥 누락, 기존 direct 프록시 대체, 원격 DNS 플래그, 직접 fallback 없음, 메모리 한도 초과, 프록시 생성 실패 시 채널 취소를 검사했다. Gecko XPCOM 통합이나 Tor 실연결 검사는 아니다.
- 71개 정책 설정 이름을 Gecko 157 소스와 대조했다. Gecko startup 및 새 모듈의 JavaScript 문법 검사를 통과했다.
- Actions에 iOS UIKit 타입 검사, 수정된 Swift 저장소/탐색 코드 문법 검사, Tor arm64 컴파일, Gecko 설정 이름 검사, 전체 앱/IPA 빌드를 연결했다. 이 문서 작성 시점에는 새 전체 IPA 빌드가 아직 완료되지 않았다.

실기기에서는 DNS 패킷, Tor 중단, 로컬 주소/redirect/websocket, 다운로드, 최상위 사이트와 iframe의 SOCKS 인증, 앱 강제 종료 후 디스크 기록, JavaScript 차단 모드, 브라우저 지문을 확인해야 한다.
