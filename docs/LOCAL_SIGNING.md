# macOS에서 IPA 서명 및 설치

이 경로는 Actions의 **기존 unsigned IPA**를 재서명합니다. Gecko, Tor.framework,
JIT Helper를 컴파일하지 않습니다. 추가 스크립트는 프로젝트와 동일한 GPL-3.0이며
Python 표준 라이브러리와 Apple의 공식 도구만 호출합니다. Xcode·security·codesign·
ditto·devicectl 자체는 Apple의 독점 도구입니다. 모든 도구까지 오픈소스라는 뜻은 아닙니다.
Apple 계정 로그인은 Xcode에서만 수행하며, 스크립트는 계정 암호나 인증 API를 다루지 않습니다.
iloader/isideload의 GrandSlam 로그인에 의존하지 않습니다.

## 첫 실행 준비

1. 전체 Xcode를 설치하고 한 번 실행해 라이선스·iOS 플랫폼 설치를 완료합니다.
   Command Line Tools만으로는 부족합니다. 필요하면
   `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer`로 선택합니다.
2. Xcode → Settings → Accounts에서 Apple 계정을 추가하고 Personal Team을 선택합니다.
   Manage Certificates에서 **Apple Development** 인증서를 생성합니다.
   다른 Mac에서 가져온 인증서는 연결된 **개인 키**도 Keychain에 있어야 합니다.
   `security find-identity -v -p codesigning`으로 확인할 수 있습니다.
3. iPhone을 연결하고 신뢰·개발자 모드를 활성화합니다. Xcode의 Devices and Simulators
   (버전에 따라 Device Hub)에서 기기 UDID를 확인합니다.
4. 본인만의 Bundle ID를 정합니다. 아래 예의 `org.example.myOnion`은 본인의 고유 ID로,
   `ABCDE12345`는 Xcode에서 확인한 Team ID로 바꿉니다.

```sh
git clone https://github.com/ACOPS1206/Tor-Browser-iOS.git
cd Tor-Browser-iOS
python3 scripts/prepare-signing-project.py \
  --output SigningPreparation \
  --bundle-id org.example.myOnion \
  --team-id ABCDE12345
open SigningPreparation/SigningPreparation.xcodeproj
```

생성된 프로젝트에는 작은 **SigningApp**, **Helper**, **OpenIn** 타깃만 있습니다.
브라우저 소스·Gecko·Tor·JIT 라이브러리는 없습니다. Xcode에서 계정·Team·실제 iPhone을
선택하고 SigningApp 스킴을 **Build**합니다. Run해서 placeholder를 브라우저 위에
설치하지 마세요. 각 타깃의 Automatically manage signing은 켜져 있습니다.
메인 앱의 increased-memory-limit와 Helper의 get-task-allow를 그대로 요청하므로,
지원되지 않는 capability가 있으면 Xcode가 오류를 표시합니다.

Xcode 계정이 이미 준비되었다면 다음 공식 명령도 사용할 수 있습니다.

```sh
xcodebuild -project SigningPreparation/SigningPreparation.xcodeproj \
  -scheme SigningApp -configuration Debug \
  -destination 'id=YOUR_IPHONE_UDID' \
  -allowProvisioningUpdates -allowProvisioningDeviceRegistration build
```

Xcode가 인증서·App ID·기기 개발용 프로파일을 준비하는 경로입니다.
계정 권한·capability·Apple 서비스 상태에 따라 실패할 수 있으며 성공을 보장하지 않습니다.
Python 서명 도구가 프로파일을 임의로 생성하거나 로그인 오류를 우회하지는 않습니다.
프로파일이 준비되지 않으면 이 단계로 돌아가라는 오류를 출력합니다.

## 기존 IPA 서명

Actions artifact ZIP을 풀어 `Tor-Browser-iOS.ipa`를 준비합니다.
처음부터 자기 Bundle ID의 인증서·프로파일이 준비되어 있다면 최소 명령은 다음과 같습니다.

```sh
./scripts/sign-ipa.sh \
  --input Tor-Browser-iOS.ipa \
  --output dist/Tor-Browser-iOS-signed.ipa
```

일반적으로 자기 Bundle ID와 기기를 명시하는 것이 편리합니다.

```sh
./scripts/sign-ipa.sh \
  --input Tor-Browser-iOS.ipa \
  --output dist/Tor-Browser-iOS-signed.ipa \
  --bundle-id org.example.myOnion \
  --team-id ABCDE12345 \
  --device YOUR_IPHONE_UDID
```

메인 ID를 변경하면 확장은 자동으로 `.Helper`, `.OpenIn` 접미사를 유지합니다.
서명 전에 ID·프로파일 변경을 모두 완료합니다. 프레임워크와 XUL처럼 확장자가 없는
Mach-O도 각각 서명하고, 확장·메인 앱 순서로 서명합니다. `codesign --deep --force`는
사용하지 않습니다. Team, 사용한 프로파일, 만료일을 출력하고, 모든 서명을 검증한
뒤에 IPA와 설치용 `dist/Tor-Browser-iOS-signed.app`를 출력합니다.
기존 출력 파일은 덮어쓰지 않습니다.

자동 탐색 위치:

- `~/Library/MobileDevice/Provisioning Profiles`
- `~/Library/Developer/Xcode/UserData/Provisioning Profiles`
- `--profile-dir PATH`로 추가한 디렉터리

프로파일의 Team·앱 ID·개발 인증서·만료일·기기·Entitlements 값을 검사합니다.
여러 인증서가 있으면 터미널에서 선택하거나 `--identity SHA1`을 지정합니다.
`--device`가 없으면 세 프로파일에 공통으로 등록된 기기가 있어야 합니다.
다른 기기에 설치하려면 반드시 그 기기의 UDID로 다시 검증하세요.

수동 프로파일 지정 예:

```sh
./scripts/sign-ipa.sh --input Tor-Browser-iOS.ipa --output dist/signed.ipa \
  --bundle-id org.example.myOnion --team-id ABCDE12345 \
  --profile 'org.example.myOnion=/absolute/path/main.mobileprovision' \
  --profile 'org.example.myOnion.Helper=/absolute/path/helper.mobileprovision' \
  --profile 'org.example.myOnion.OpenIn=/absolute/path/openin.mobileprovision'
```

반복 사용 설정은 로컬 `signing.local.json`에 둘 수 있습니다.

```json
{
  "team_id": "ABCDE12345",
  "bundle_id": "org.example.myOnion",
  "profiles": {
    "org.example.myOnion": "/absolute/path/main.mobileprovision",
    "org.example.myOnion.Helper": "/absolute/path/helper.mobileprovision",
    "org.example.myOnion.OpenIn": "/absolute/path/openin.mobileprovision"
  }
}
```

`--config signing.local.json`으로 사용합니다. `identity`에 인증서 SHA1도 저장할 수
있습니다. `bundle_ids` 또는 반복 `--bundle-map OLD_ID=NEW_ID`는 별도 확장 ID 매핑용입니다.
프로파일 경로의 키는 **변경 후 ID**, bundle map의 키는 **원래 ID**입니다.
계정 암호는 설정에 넣지 않습니다. 인증서 개인 키·프로파일·로컬 설정·서명 결과를
GitHub나 Actions에 올리지 마세요. 이를 위한 ignore 규칙을 추가했습니다.

## Entitlements와 Personal Team 제한

| 구성요소 | 일반 빌드 요구사항 | 처리 |
|---|---|---|
| Reynard.app | com.apple.developer.kernel.increased-memory-limit = true | 프로파일 허용 여부 확인; 자동 제거 없음 |
| Reynard Helper.appex | get-task-allow = true | 개발 프로파일 필수; 자동 제거·배포 프로파일 사용 없음 |
| OpenIn.appex | 별도 capability 없음 | 고유 하위 ID와 개발 프로파일 필요 |

increased-memory-limit는 지원 기기에서 앱 메모리 한도를 높이기 위한 요청이며,
무제한 메모리나 JIT 권한을 주지 않습니다. Personal Team의 해당 capability 지원 여부를
모든 계정·Xcode 버전에 대해 단정하지 않습니다. Xcode가 발급한 프로파일에 없는 요청은
이 도구의 보수적인 검증에서 거부합니다. 유료 팀도 모든 entitlement를 자동 허용하지 않습니다.
get-task-allow는 디버거 접근을 허용하는 개발 서명 권한이며, 별도 JIT 활성화·개발자
연결이 필요할 수 있습니다. 앱 설치 성공이 Gecko/Helper/JIT의 동작을 보장하지는 않습니다.

TrollStore/jailbreak 전용 private entitlements의 platform-application,
com.apple.private.* 등은 일반 Personal Team 서명 경로에서 그대로 허용할 수 없습니다.
이 도구로 그런 빌드를 일반 개발 서명용이라고 자동 변환하지 않습니다.

메모리 권한 없는 제한된 실험을 **사용자가 명시적으로 선택**하려면 준비 프로젝트의
메인 Required.entitlements에서 해당 항목을 제거해 Xcode 프로파일을 준비한 다음,
서명 명령에 아래 옵션을 추가할 수 있습니다.

```sh
--omit-entitlement org.example.myOnion:com.apple.developer.kernel.increased-memory-limit
```

경고를 출력하며 메모리 제한으로 웹페이지나 엔진이 종료될 수 있습니다. 기본 경로는
그대로 중단합니다. Helper의 get-task-allow 및 서명 식별 권한은 이 옵션으로 제거할 수 없습니다.

무료 Personal Team은 프로파일이 통상 **발급 후 7일**에 만료되고, App ID·등록 기기
수 제한도 있습니다. 이 프로젝트는 확장까지 총 세 개의 ID를 사용합니다.
실제 만료일은 도구가 읽은 프로파일의 ExpirationDate를 따릅니다.

## 검증·설치

도구는 각 중첩 실행 파일·번들에 `codesign --verify --strict`를 실행하고, 서명된
Entitlements를 요청값·프로파일 허용값과 비교합니다. Team, 앱·확장 ID 및 embedded
프로파일을 다시 확인합니다. 설치용 앱을 복사한 뒤에도 모든 중첩 서명을 다시 검증합니다.
검증 성공은 iOS의 최종 설치 승인·실행 성공을 대신하지 않습니다.

공식 명령:

```sh
xcrun devicectl list devices
xcrun devicectl device install app --device YOUR_IPHONE_UDID \
  dist/Tor-Browser-iOS-signed.app
```

설치에는 IPA 대신 출력된 **.app 디렉터리**를 전달합니다. Xcode Devices and Simulators의
Installed Apps 추가 기능 또는 해당 버전의 Device Hub도 사용할 수 있습니다.
명령 구문은 설치된 Xcode의 `xcrun devicectl device install app --help`로 확인하세요.
기기 신뢰·Developer Mode·프로파일에 등록된 UDID·프로파일 유효기간을 확인하세요.

## 이후 업데이트

새 unsigned IPA를 다운로드하고 동일 Bundle ID·Team 설정으로 서명합니다. 출력 경로는
새로 지정하거나 이전 출력물을 직접 정리합니다. 엔진을 다시 빌드하지 않습니다.
프로파일이 만료됐다면 준비 프로젝트에서 동일 계정·실제 iPhone으로 Build하여 갱신한 뒤
재서명·재설치합니다. 변경하지 않은 Team/Bundle ID를 유지하는 것이 앱 데이터 유지에
도움이 되지만, 앱 삭제·ID 변경은 별도 설치나 데이터 손실로 이어질 수 있습니다.

## 오류 해결

| 오류 | 확인·해결 |
|---|---|
| No signing certificate | Xcode Accounts → Manage Certificates에서 Apple Development 생성; 개인 키 존재·Keychain 잠금 확인 |
| No provisioning profile | 준비 프로젝트의 세 타깃 자동 서명 Build; 올바른 Team/기기 선택; --profile 또는 --profile-dir 지정 |
| Bundle Identifier mismatch | 최종 앱 ID와 프로파일 application-identifier 비교; 확장은 메인 ID + '.'로 시작해야 함 |
| Unsupported entitlement | Xcode에서 capability 요청 후 프로파일 재생성; private 권한은 일반 서명 불가; 메모리 권한 제거는 명시적 제한 실험만 |
| Invalid code signature | 원본 IPA에서 다시 서명; 서명 후 Info.plist·리소스·dylib를 편집하지 않기; 모든 중첩 서명의 첫 실패 항목 확인 |
| Failed to verify app integrity | UDID·만료일·인증서/개인 키·세 프로파일·권한 확인; 기기 설치 로그 확인; --device 지정으로 다시 검증 |

기존 upstream create-ipa.sh는 archive의 앱·확장 ID를 강제로 수정했습니다. 일반 CI
배포물은 unsigned이므로 로컬 최종 서명 전에 변경됐지만, 서명된 archive를 재포장할
때는 서명을 깨뜨릴 수 있었습니다. CI는 이제 scripts/create-ipa.sh로 archive를 복사해
**기존 ID를 유지**하고 요구 Entitlements만 포함합니다. 원본 archive는 수정하지 않으며
embedded.mobileprovision이 있는 signed archive는 거부합니다. 정식 서명 archive를
배포하려면 Xcode exportArchive를 사용하세요.

## 검증 범위

- Python 테스트: 프로파일 Team/인증서/기기/만료일·앱 ID·Entitlements 허용값,
  archive 경로·symlink 보호, 중첩 서명 순서, 확장 ID 관계, unsigned IPA의 필수 권한 유지.
- CI 추가 검사: macOS에서 작은 준비 프로젝트의 Xcode 빌드(CODE_SIGNING_ALLOWED=NO),
  실제 unsigned archive 패키징·Bundle ID/권한 manifest 유지.
- **미검증:** 실제 Apple Development 개인 키 서명, Personal Team 프로파일 신규 발급,
  실기기 설치·7일 갱신·메모리 한도·Helper/JIT 및 Tor 실연결.
  공개 CI에는 인증서·Apple 계정·프로파일을 업로드하지 않습니다.

## Apple 공식 자료

- [무료 개발자 계정과 Personal Team 제한](https://developer.apple.com/help/account/basics/about-your-developer-account)
- [자동 서명 및 capability 준비](https://help.apple.com/xcode/mac/current/en.lproj/dev60b6fbbc7.html)
- [실기기 실행과 Xcode 자동 서명](https://help.apple.com/xcode/mac/current/en.lproj/dev5a825a1ca.html)
- [TN3125: 프로비저닝 프로파일과 권한](https://developer.apple.com/documentation/technotes/tn3125-inside-code-signing-provisioning-profiles)
- [Increased memory limit](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.kernel.increased-memory-limit)
