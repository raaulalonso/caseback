#!/usr/bin/env bash
# Takes the screenshots of the iOS app that the website's "The app" section is rendered from.
#
#   tools/app_renders/capture.sh <simulator udid> <path to Caseback.app> <en|es> <output dir>
#
# Use a CLEAN simulator (xcrun simctl create "Caseback Shots" com.apple.CoreSimulator.SimDeviceType.iPhone-17-Pro
# com.apple.CoreSimulator.SimRuntime.iOS-26-4): a simulator signed in to an Apple ID shows account prompts over the app,
# and the status bar can carry a "back to <app>" link. Every screen shows invented fixtures (apps/ios/README.md,
# "Simulator launch arguments"); nothing here comes from a disc. The build:
#
#   cd apps/ios && xcodebuild -project Caseback.xcodeproj -scheme Caseback \
#     -destination "platform=iOS Simulator,id=<udid>" -derivedDataPath <dir> CODE_SIGNING_ALLOWED=NO build
set -eu

UDID=$1; APP=$2; LANG_CODE=$3; OUT=$4
BUNDLE=com.raaulalonso.caseback
case "$LANG_CODE" in
  en) LOCALE=en_US ;;
  es) LOCALE=es_ES ;;
  *) echo "language must be en or es" >&2; exit 1 ;;
esac
mkdir -p "$OUT"

# The usual store-screenshot status bar: 9:41, full signal, plain battery.
xcrun simctl status_bar "$UDID" override --time 9:41 --batteryState discharging --batteryLevel 100 \
  --wifiBars 3 --cellularMode active --cellularBars 4 >/dev/null
xcrun simctl install "$UDID" "$APP"

# shot <name> <settle seconds> <app arguments...>
# ONLY="today_now trends_scrub" runs just those.
shot() {
  local name=$1 wait=$2; shift 2
  if [ -n "${ONLY:-}" ] && [[ " $ONLY " != *" $name "* ]]; then return 0; fi
  xcrun simctl terminate "$UDID" "$BUNDLE" >/dev/null 2>&1 || true
  xcrun simctl launch "$UDID" "$BUNDLE" -AppleLanguages "($LANG_CODE)" -AppleLocale "$LOCALE" "$@" >/dev/null
  sleep "$wait"
  xcrun simctl io "$UDID" screenshot --type=png "$OUT/$name.png" >/dev/null 2>&1
  echo "$LANG_CODE/$name"
}

DONE=(-onboarding-done YES)

shot today_now        5 "${DONE[@]}" -today-state normal -today-page 0
shot today_night      5 "${DONE[@]}" -today-state normal -today-page 1
shot today_sheet      6 "${DONE[@]}" -today-state normal -today-drawer 1
shot today_info       5 "${DONE[@]}" -today-state normal -today-info readiness

shot trends_readiness 6 "${DONE[@]}" -tab trends -trends-state normal -trends-metric readiness -trends-range 30
shot trends_scrub     6 "${DONE[@]}" -tab trends -trends-state normal -trends-metric restingHR -trends-range 30 -trends-scrub 21
shot trends_sleep     6 "${DONE[@]}" -tab trends -trends-state normal -trends-metric sleep -trends-range 30

# The metric screens (-today-open) are not captured: opened this way their charts stay empty (2026-10-28, iOS 26.4).

shot device           5 "${DONE[@]}" -tab device -device-state connected
shot device_data      9 "${DONE[@]}" -tab device -device-state connected -device-sheet data
shot device_health    9 "${DONE[@]}" -tab device -device-state connected -device-sheet health
shot device_mode      9 "${DONE[@]}" -tab device -device-state connected -device-sheet mode

# The widgets are not captured here: they go on the Simulator's own Home Screen, see home_screen.sh.

xcrun simctl terminate "$UDID" "$BUNDLE" >/dev/null 2>&1 || true
