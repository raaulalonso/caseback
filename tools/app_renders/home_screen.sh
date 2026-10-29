#!/usr/bin/env bash
# The widgets on the iOS Simulator's own Home Screen, for the website's "The app" section.
#
#   tools/app_renders/home_screen.sh setup   <udid> <path to Caseback.app>
#   tools/app_renders/home_screen.sh capture <udid> <en|es> <output dir>
#
# `setup` works on a clean simulator (see capture.sh for how to make one and for the build, which must be signed locally
# (CODE_SIGN_IDENTITY=-) so that the app and its widget share their App Group). It puts the app on the Home Screen, adds the widgets
# through the real widget gallery and sets a wallpaper, all with UI tests (ui/) that drive SpringBoard. `capture` takes the same
# Home Screen at three moments after the last sync, which the app fakes with -widget-age-hours (UI test testCapture).
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
CMD=$1; UDID=$2
BUNDLE=com.raaulalonso.caseback
DERIVED=${DERIVED:-${TMPDIR:-/tmp}/caseback-home-ui}

lang() {
  case "$1" in en) L=en; LOC=en_US ;; es) L=es; LOC=es_ES ;; *) echo "language must be en or es" >&2; exit 1 ;; esac
  xcrun simctl shutdown "$UDID" >/dev/null 2>&1 || true
  xcrun simctl boot "$UDID"
  xcrun simctl spawn "$UDID" defaults write "Apple Global Domain" AppleLanguages -array "$L"
  xcrun simctl spawn "$UDID" defaults write "Apple Global Domain" AppleLocale -string "$LOC"
  xcrun simctl shutdown "$UDID"; xcrun simctl boot "$UDID"; sleep 15
  xcrun simctl status_bar "$UDID" override --time 9:41 --batteryState discharging --batteryLevel 100 \
    --wifiBars 3 --cellularMode active --cellularBars 4 >/dev/null
}

ui() {  # a UI test of ui/, with a time limit: a stuck SpringBoard would hold xcodebuild for ever
  (cd "$HERE/ui" && xcodegen generate --spec project.yml >/dev/null &&
    perl -e 'alarm 300; exec @ARGV' xcodebuild test -project Driver.xcodeproj -scheme Driver \
      -destination "platform=iOS Simulator,id=$UDID" -derivedDataPath "$DERIVED" \
      -only-testing:"DriverUITests/HomeScreenTests/$1" 2>&1 | grep -E "error:|Test Case.*(passed|failed)")
}

case "$CMD" in
  setup)
    APP=$3
    lang en
    xcrun simctl install "$UDID" "$APP"
    xcrun simctl launch "$UDID" "$BUNDLE" -AppleLanguages "(en)" -AppleLocale en_US -onboarding-done YES -today-state normal >/dev/null
    sleep 6; xcrun simctl terminate "$UDID" "$BUNDLE"
    ui testLayout; ui testSmallWidgetSleep; ui testWallpaper
    ;;
  capture)
    LANG_CODE=$3; OUT=$4
    mkdir -p "$OUT"
    lang "$LANG_CODE"
    TEST_RUNNER_CAPTURE_DIR=$OUT TEST_RUNNER_CAPTURE_LANG=$LANG_CODE ui testCapture
    ls "$OUT"
    ;;
  *) echo "usage: home_screen.sh setup|capture <udid> ..." >&2; exit 1 ;;
esac
