# Earn Easy24 Android

Native Android floating assistant for user-reviewed CAPTCHA OCR.

## Build

```powershell
cd android-app
$env:JAVA_HOME = "C:\tmp\earneasy24-android-tools\jdk-17"
$env:ANDROID_HOME = "C:\tmp\earneasy24-android-tools\android-sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
.\gradlew.bat assembleDebug
```

Debug APK:

```text
android-app/app/build/outputs/apk/debug/app-debug.apk
```

## Runtime permissions

The app asks the user to enable:

- Display over other apps, for the floating mini panel.
- Screen capture consent, for each capture session.
- Notifications, for the foreground capture service on Android 13+.

This APK does not use Android Accessibility APIs and does not auto-click or auto-type into other apps.

## Sideload

With USB debugging enabled on a phone:

```powershell
C:\tmp\earneasy24-android-tools\android-sdk\platform-tools\adb.exe install -r app\build\outputs\apk\debug\app-debug.apk
```
