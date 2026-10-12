# Tor Browser iOS — Onion Reynard (experimental)

Reynard's native iOS Gecko browser with an embedded Tor client. This is an **unofficial experimental project**, unaffiliated with the Tor Project. It does not yet provide all official Tor Browser protections.

## 구현된 기능

- Orbot에서도 사용하는 Tor.framework의 CTor를 앱 내 스레드로 실행. 별도 Orbot 설치나 기기 전체 VPN은 필요하지 않습니다.
- Gecko 시작 전에 SOCKS5와 원격 DNS 설정 적용. 프록시 우회 목록 제거, 직접 연결 fallback 차단, DoH 및 WebRTC/HTTP3 차단.
- 네이티브 다운로드, 파비콘, 검색 후보, 이미지 미리보기, 미디어 artwork도 SOCKS5로 전달. Apple ProxyConfiguration의 `allowFailover = false` 적용.
- Tor bootstrap 진행률·회로 연결 상태, 일시 정지/재연결, 새 회로 요청 UI. CookieAuthentication으로 로컬 제어 채널 인증.
- Gecko private session 강제, RFP·letterboxing·first-party isolation 설정 활성화 및 엔진 pref 잠금.
- 본가 Reynard 자동 업데이트 차단 (Tor 기능 없는 앱으로 바뀌는 것 방지).
- 재현 가능한 upstream 커밋과 Tor.framework 커밋 고정. GitHub Actions가 unsigned IPA와 SHA-256을 생성.

## 설치

**iOS 17.4 이상**. Actions의 `Build Tor Browser iOS IPA` 실행에서 `Tor-Browser-iOS-unsigned` artifact를 다운로드하고 ZIP 안의 IPA를 **SideStore 또는 AltStore로 다시 서명**해 설치하세요. **Keep App Extensions**를 선택해야 합니다. 브라우저 엔진용 Helper와 OpenIn 확장이 포함됩니다. LiveContainer는 Reynard에서 지원하지 않습니다.

Tor 연결은 앱 실행 시 자동 시작됩니다. 화면 위 상태 버튼이나 Settings → Tor에서 연결 진행률과 일시 정지/새 회로 요청을 확인할 수 있습니다. 첫 연결은 시간이 걸릴 수 있습니다. https://check.torproject.org 에서 Tor 출구 사용을 확인할 수 있으나 이 검사만으로 익명성이나 모든 통신의 누출 여부가 증명되지는 않습니다.

Reynard의 JIT 활성화는 설치 방식·iOS 버전에 따라 별도 설정이 필요합니다. JIT pairing/개발자 이미지(DDI) 설정은 브라우징 통신이 아니며, 기존 Reynard의 직접 로컬 연결·Apple 개발자 이미지 다운로드 경로를 유지합니다. 필요하다면 브라우징 전 설정하세요.

## 현재 한계

- **공식 Tor Browser의 Gecko 패치 전체, NoScript 보안 수준 UI, 최상위 사이트별 SOCKS 자격 증명 격리는 아직 이식하지 않았습니다.** RFP 설정만으로 다른 Tor Browser 사용자와 동일한 지문을 보장할 수 없습니다.
- Tor의 IsolateDestAddr/IsolateDestPort/IsolateSOCKSAuth를 사용하지만 공식 브라우저의 사이트별 회로 격리와 같지 않습니다.
- ‘새 회로 요청’은 NEWNYM 요청이며 Tor가 rate-limit할 수 있습니다. 쿠키·탭·캐시·진행 중 연결을 지우는 ‘새 신원’ 기능이 아닙니다.
- private Gecko 세션을 사용해도 Reynard UI의 탭/히스토리/즐겨찾기 및 다운로드 파일 저장 정책 전체를 변경한 것은 아닙니다. 저장된 데이터는 UI에서 직접 삭제하세요.
- obfs4/Snowflake bridges UI와 transport 라이브러리 통합은 후속 작업입니다. 직접 Tor 연결을 차단하는 네트워크에서는 연결되지 않을 수 있습니다.
- iOS가 앱을 background에서 suspend하면 내장 Tor도 멈출 수 있습니다. SOCKS 설정은 유지되며 일반 연결로 전환하지 않습니다.
- 실기기에서 DNS·리다이렉트·미디어·다운로드·연결 중단·지문에 대한 네트워크 검증이 필요합니다. 현재 배포물을 익명성이 검증된 제품으로 취급하지 마세요.

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
