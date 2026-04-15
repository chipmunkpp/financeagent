[app]
title = FinanceAgent
package.name = financeagent
package.domain = org.finance.agent

source.dir = .
source.include_exts = py,png,jpg,jpeg,webp,kv,json,txt
source.exclude_dirs = .git,__pycache__,bin,.buildozer,venv,.venv

version = 1.0.0
requirements = python3,kivy==2.3.0,kivymd==1.2.0,requests,plyer
orientation = portrait
fullscreen = 0

# Android platform
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True
android.private_storage = True
android.enable_androidx = True

# App permissions (review and keep minimal)
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,CAMERA

# Release artifact type:
# - aab: recommended for Google Play
# - apk: useful for direct distribution/testing
android.release_artifact = aab

# =========================
# Release signing (Play-ready)
# =========================
# IMPORTANT:
# 1) Use the same keystore/alias for every update release.
# 2) Keep keystore and passwords secure and backed up.
# 3) Prefer injecting passwords in CI/private environments.
#
# Example keystore creation:
# keytool -genkeypair -v -keystore keystore/financeagent-release.keystore -alias financeagent -keyalg RSA -keysize 4096 -validity 10000
#
# Path is relative to source.dir (this project folder):
android.release_keystore = %(source.dir)s/keystore/financeagent-release.keystore
android.release_keyalias = financeagent

# Option A (recommended): leave passwords unset here and enter when prompted during release build.
# Option B (local private machine only): uncomment and set values below.
# android.release_keystore_password = CHANGE_ME
# android.release_keyalias_password = CHANGE_ME

# Optional app icon / splash
# icon.filename = %(source.dir)s/assets/icon.png
# presplash.filename = %(source.dir)s/assets/presplash.png

[buildozer]
log_level = 2
warn_on_root = 1
