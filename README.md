# Tor Browser iOS — Onion Reynard (experimental)

Reynard's native iOS Gecko browser with an embedded Tor client. This is an **unofficial experimental project**, unaffiliated with the Tor Project. It does not yet provide all official Tor Browser protections.

## 구현된 기능

- Orbot에서도 사용하는 Tor.framework의 CTor를 앱 내 스레드로 실행. 별도 Orbot 설치나 기기 전체 VPN은 필요하지 않습니다.
- Gecko 시작 전에 SOCKS5와 원격 DNS 설정 적용. 프록시 우회 목록 제거, 직접 연결 fallback 차단, DoH 및 WebRTC/HTTP3 차단.
- 네이티브 다운로드, 파비콘, 검색 후보, 이미지 미리보기, 미디어 artwork도 SOCKS5로 전달. Apple ProxyConfiguration의 `allowFailover = false` 적용.
- Tor bootstrap 진행률·회로 연결 상태, 일시 정지/재연결, 새 회로 요청 UI. CookieAuthentication으로 로컬 제어 채널 인증.
- Gecko private session·RFP·first-party isolation 강제 및 엔진 pref 잠금. 최상위 사이트별 임시 SOCKS 인증값과 연결 풀 격리 추가.
- 웹 JavaScript JIT/WASM/WebGPU/센서/DRM 제한, HTTPS-Only 고정 및 onion 예외. Tor 화면에서 다음 실행의 JavaScript 완전 차단을 선택할 수 있습니다.
- 방문 기록·탭·탐색 썸네일·파비콘·사이트 메타데이터·권한은 메모리에만 저장. 자동 HTTP 디스크 캐시 비활성화, 이전 자동 탐색 기록은 시작 시 정리합니다.
- 웹 탐색의 외부 앱 URL 스킴 차단. 사이트별 UA 지문 override 사용 중단, 웹 언어를 en-US/en으로 통일.
- 본가 Reynard 자동 업데이트 차단 (Tor 기능 없는 앱으로 바뀌는 것 방지).
- 재현 가능한 upstream 커밋과 Tor.framework 커밋 고정. GitHub Actions가 unsigned IPA와 SHA-256을 생성.

## 설치

**iOS 17.4 이상**. Actions의 `Build Tor Browser iOS IPA` 실행에서 `Tor-Browser-iOS-unsigned` artifact를 다운로드하고 ZIP 안의 IPA를 **SideStore 또는 AltStore로 다시 서명**해 설치하세요. **Keep App Extensions**를 선택해야 합니다. 브라우저 엔진용 Helper와 OpenIn 확장이 포함됩니다. LiveContainer는 Reynard에서 지원하지 않습니다.

Tor 연결은 앱 실행 시 자동 시작됩니다. 화면 위 상태 버튼이나 Settings → Privacy → Tor Connection & Relays에서 연결 진행률과 일시 정지/새 회로 요청을 확인할 수 있습니다. 첫 연결은 시간이 걸릴 수 있습니다. https://check.torproject.org 에서 Tor 출구 사용을 확인할 수 있으나 이 검사만으로 익명성이나 모든 통신의 누출 여부가 증명되지는 않습니다.

Reynard의 JIT 활성화는 설치 방식·iOS 버전에 따라 별도 설정이 필요합니다. JIT pairing/개발자 이미지(DDI) 설정은 브라우징 통신이 아니며, 기존 Reynard의 직접 로컬 연결·Apple 개발자 이미지 다운로드 경로를 유지합니다. 필요하다면 브라우징 전 설정하세요.

## macOS에서 IPA 서명 및 설치

Actions의 unsigned IPA를 로컬 Apple Development 인증서로 서명하는 도구를 추가했습니다. **Gecko·Tor·JIT Helper 재컴파일은 필요 없습니다.** 최초 인증서·프로파일 준비는 Xcode의 공식 자동 서명 경로를 이용합니다.

```sh
./scripts/sign-ipa.sh --input Tor-Browser-iOS.ipa --output dist/Tor-Browser-iOS-signed.ipa
```

기본 명령은 IPA의 기존 Bundle ID에 맞는 프로파일을 찾습니다. 본인 ID를 사용하는 경우 `--bundle-id`, 여러 팀은 `--team-id`를 지정하세요. 메인 앱과 두 확장의 프로파일·권한을 검사하고 중첩 코드부터 서명한 뒤 검증된 IPA와 설치용 `.app`를 출력합니다. 지원되지 않는 권한은 조용히 제거하지 않습니다.

[최초 Xcode 준비, 이후 업데이트, 수동 프로파일 지정, Entitlements·7일 제한, 설치 및 오류 해결](docs/LOCAL_SIGNING.md)을 참고하세요. 실제 Apple 계정의 프로파일 발급·인증서 서명·iPhone 설치는 사용자 Mac에서 검증해야 합니다.

## 현재 한계

- **공식 Tor Browser의 Gecko 패치 전체, NoScript, letterboxing은 아직 이식하지 않았습니다.** RFP 설정만으로 다른 Tor Browser 사용자와 동일한 지문을 보장할 수 없습니다. 기존 letterboxing 설정만으로 기능이 구현되었다고 볼 수 없어 제거했습니다.
- 최상위 사이트별 SOCKS 인증값 격리는 구현했지만 실기기의 Gecko 채널 originAttributes 및 Tor 실연결 검증은 아직 필요합니다. Foundation 요청에는 해당 사이트 문맥이 전달되지 않습니다.
- ‘새 회로 요청’은 NEWNYM 요청이며 Tor가 rate-limit할 수 있습니다. 쿠키·탭·캐시·진행 중 연결을 지우는 ‘새 신원’ 기능이 아닙니다.
- 자동 탐색 기록은 실행 중 메모리에 유지되며 앱을 완전히 종료하면 탭·방문 기록을 복원하지 않습니다. 즐겨찾기와 명시적 다운로드 파일은 저장됩니다. OS가 만드는 기록까지 완전히 제거하지는 않습니다.
- obfs4/Snowflake bridges UI와 transport 라이브러리 통합은 후속 작업입니다. 직접 Tor 연결을 차단하는 네트워크에서는 연결되지 않을 수 있습니다.
- iOS가 앱을 background에서 suspend하면 내장 Tor도 멈출 수 있습니다. SOCKS 설정은 유지되며 일반 연결로 전환하지 않습니다.
- 실기기에서 DNS·리다이렉트·미디어·다운로드·연결 중단·지문에 대한 네트워크 검증이 필요합니다. 현재 배포물을 익명성이 검증된 제품으로 취급하지 마세요.

보호 기능 분석·공식 소스 링크·구체적인 적용 범위와 검증 한계는 [SECURITY_REVIEW.md](docs/SECURITY_REVIEW.md)에 기록했습니다. JavaScript 차단 선택은 앱을 완전히 종료하고 재실행해야 반영됩니다. JIT/WASM 제한으로 일부 사이트가 느려지거나 동작하지 않을 수 있습니다.

## Source / 빌드

소스는 이 저장소의 `overlay`, `scripts/apply-overlay.py`, `privacy-prefs.json` 및 `upstream.lock.json`에 고정된 [Reynard](https://github.com/minh-ton/reynard-browser) 원본으로 구성됩니다. CI는 고정된 원본을 checkout하고 변경사항을 적용한 뒤 Gecko와 앱을 직접 빌드합니다. 기존 IPA를 재포장하는 방식이 아닙니다.

```sh
git clone https://github.com/ACOPS1206/Tor-Browser-iOS.git
cd Tor-Browser-iOS
git clone https://github.com/minh-ton/reynard-browser.git upstream
git -C upstream checkout ddaacd18b8c5661d495acfc0f3e90a86c484e64d
cd upstream
git submodule update --init --recursive support/idevice
./tools/development/update-gecko.sh
./tools/development/apply-patches.sh
cd ..
python3 scripts/apply-overlay.py upstream
cd upstream/browser
pod install
cd ..
./tools/development/build-gecko.sh --auto-clobber
./tools/development/build-idevice.sh
./tools/release/build-app.sh --no-signing
./tools/release/create-ipa.sh
```

빌드 의존성 설치 및 Xcode 선택은 `.github/workflows/build-ipa.yml`을 참고하세요. 최초 Gecko 빌드는 상당한 시간과 디스크를 사용합니다.

## License / 출처

Reynard 및 이 overlay는 GPL-3.0, Gecko 수정사항은 MPL-2.0 (`LICENSE.firefox`). Tor.framework는 MIT이며 포함 라이브러리의 라이선스도 적용됩니다. [Reynard](https://github.com/minh-ton/reynard-browser), [Tor.framework](https://github.com/iCepa/Tor.framework), [Orbot](https://github.com/guardianproject/orbot-apple), [Tor Project](https://www.torproject.org/)에 감사드립니다. 공식 Tor Browser 브랜드/보증을 주장하지 않습니다.

## Tor 사용 범위

Settings → Privacy에 **Use Tor / Private Tabs Only / Block JavaScript** 토글이 있습니다. Use Tor만 켜면 모든 탭, Private Tabs Only도 켜면 개인 탭만 Tor를 사용하고, Use Tor를 끄면 모든 탭이 직접 연결됩니다. 앱 UI는 영어로 표시됩니다. 기본값은 항상입니다. 변경은 다음 앱 실행에 적용되므로 앱을 완전히 종료하고 다시 실행하세요. 실행 중 탭·다운로드의 경로를 갑자기 바꾸지 않습니다.

| 설정 | 일반 탭 | 사생활 보호 탭 |
|---|---|---|
| 항상 | Tor | Tor |
| 사생활 보호 탭만 | 직접 연결 | Tor |
| 사용 안 함 | 직접 연결 | 직접 연결 |

직접 연결은 실제 IP를 노출할 수 있고 사생활 보호 탭도 IP를 숨기지는 않습니다. RFP·추적 방지·메모리 기록 정책은 그대로 유지합니다. 혼합 모드에서는 탭 출처를 확인할 수 없는 검색 제안·아이콘·메타데이터·네이티브 미리보기 및 일부 네이티브 다운로드를 차단합니다. 웹페이지와 Gecko를 통해 캡처되는 다운로드는 해당 탭 경로를 따르며, 미디어 artwork는 원래 세션의 개인 모드를 따릅니다. 알 수 없는 Gecko 채널은 Tor로 처리하고 Tor 오류 시 직접 연결로 우회하지 않습니다.


## Relay information

Open **Settings → Privacy → Tor Connection & Relays**, or tap the browser status button.
The relay view shows built general-purpose circuits, with each relay's role (Guard / Middle / Exit), nickname, IP address and fingerprint. Circuits may be unused or belong to different sites; they are not attributed to the current tab. Onion-service and internal directory circuits are excluded rather than mislabeled as exit circuits. Missing IP metadata is shown as unavailable. Information is read through the authenticated local Tor controller only, is not persisted, refreshes every 10 seconds while the page is visible, and is cleared on pause or loss of Tor readiness. A 10-second timeout rejects late responses.

The direct-routing implementation uses the pinned Gecko 157 proxy API with all eight `newProxyInfo` arguments. Older builds used a six-argument call that Gecko skipped, leaving SOCKS enabled for ordinary tabs and causing proxy-refused errors when Tor was off. Regression tests now enforce the real API signature and replacement of an existing SOCKS proxy. Changes still apply only after a full app restart.
