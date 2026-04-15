# Finance Agent Android APK Guide

Windows users can build APKs reliably using CI (GitHub Actions) without local Linux/WSL setup.

This guide covers:

1. Building a debug APK for testing
2. **Release signing setup** (Play Store-ready)
3. Building signed release artifacts (`.aab` / `.apk`)
4. Secure key handling workflow

Project path:

- App source: `TestProject1-financeagent\android_app`
- Main entrypoint: `TestProject1-financeagent\android_app\main.py`
- Build config: `TestProject1-financeagent\android_app\buildozer.spec`

---

## 1) Prerequisites

For Buildozer, use **Linux** (or **WSL2** on Windows).

Install:

- Python 3.10+
- Java JDK 17
- Git, zip/unzip
- Build dependencies for Buildozer / python-for-android
- `adb` (optional, for local install)

### Linux / WSL setup

```bash
sudo apt update
sudo apt install -y \
  git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config \
  zlib1g-dev libncurses5-dev libncursesw5-dev libtinfo5 cmake \
  libffi-dev libssl-dev adb

python3 -m pip install --upgrade pip
python3 -m pip install buildozer cython==0.29.36
```

---

## 2) Build debug APK (quick test)

```bash
cd TestProject1-financeagent/android_app
buildozer android debug
```

Output usually appears in:

- `TestProject1-financeagent/android_app/bin/`

Example:

- `financeagent-1.0.0-arm64-v8a_armeabi-v7a-debug.apk`

Install test APK:

```bash
adb install -r TestProject1-financeagent/android_app/bin/<your-debug-apk>.apk
```

---

## 3) Release signing (matches current `buildozer.spec` keys)

Your `buildozer.spec` is configured with:

- `android.release_artifact = aab`
- `android.release_keystore = %(source.dir)s/keystore/financeagent-release.keystore`
- `android.release_keyalias = financeagent`

That means you must provide:

1. Keystore file at `android_app/keystore/financeagent-release.keystore`
2. Alias named `financeagent`
3. Keystore password
4. Key alias password

> Do not commit keystore files or passwords to Git.

---

## 4) Create release keystore (one-time)

From `TestProject1-financeagent/android_app`:

```bash
mkdir -p keystore
keytool -genkeypair -v \
  -keystore keystore/financeagent-release.keystore \
  -alias financeagent \
  -keyalg RSA \
  -keysize 4096 \
  -validity 10000
```

You will be asked for:

- Keystore password
- Key password
- Organization metadata

---

## 5) Secure workflow for passwords

## Recommended (secure)

- Keep keystore file private and backed up securely
- Enter passwords only when prompted during release build
- In CI, inject passwords via secret manager into temporary config (never commit secrets)

## Avoid

- Hardcoding passwords in tracked files
- Uploading `.keystore` / `.jks` into public repositories
- Sharing signing credentials in chat/email

---

## 6) Build signed release artifact

With keystore present and alias matching:

```bash
cd TestProject1-financeagent/android_app
buildozer android release
```

Because `android.release_artifact = aab`, output will be Play Store-friendly `.aab` (and/or related release outputs depending on tooling behavior).

Artifacts are in:

- `TestProject1-financeagent/android_app/bin/`

---

## 7) Optional local-only password fields in `buildozer.spec`

If you explicitly want non-interactive local builds, you may set (not recommended in shared repos):

```ini
# android.release_keystore_password = <KEYSTORE_PASSWORD>
# android.release_keyalias_password = <KEY_PASSWORD>
```

Keep them commented in version control and only use in private local copies.

---

## 8) Verify signed artifact

```bash
# For .aab
jarsigner -verify -verbose -certs TestProject1-financeagent/android_app/bin/<release>.aab

# For .apk (if generated)
apksigner verify --verbose TestProject1-financeagent/android_app/bin/<release>.apk
```

---

## 9) CI-based APK build for Windows users (recommended)

If you're on Windows and want a ready APK without local Buildozer/WSL setup, use GitHub Actions.

### 9.1 Commit and push workflow file

Make sure this workflow exists in your repo:

- `.github/workflows/android-apk.yml`

Then push to GitHub (branch `main`/`master`) or trigger manually.

### 9.2 Trigger build

Option A: Push changes under `android_app/**`  
Option B: In GitHub -> **Actions** -> **Build Android APK** -> **Run workflow**

### 9.3 Download APK artifact

After workflow finishes:

1. Open workflow run
2. Go to **Artifacts**
3. Download `financeagent-debug-apk`
4. Extract zip to get `.apk`

### 9.4 Copy APK to phone and install

- Transfer `.apk` to your phone
- Open APK file
- Allow “Install unknown apps” if prompted
- Install

### 9.5 Notes

- CI build may take 20–60+ minutes on first run
- Artifact retention is limited (re-run workflow if expired)
- Debug APK is suitable for testing and direct installation
- For Play Store production, build and upload signed release `.aab`

---

## 10) Play Console checklist

1. Create app in Google Play Console
2. Complete store listing (icon, screenshots, descriptions)
3. Complete policy forms:
   - Data safety
   - Content rating
   - Ads declaration (if applicable)
   - App access (if applicable)
4. Upload signed `.aab`
5. Roll out gradually (recommended)

---

## 11) Versioning before each release

In `buildozer.spec`:

- Increment `version` every release (e.g., `1.0.0` -> `1.0.1`)
- Rebuild release artifact
- Upload new artifact to Play Console

---

## 12) Common release issues

### Signature/key mismatch
You are not using the same keystore/alias as previous release. Reuse the original release key.

### Version already used
Increment `version` in `buildozer.spec`.

### Build issues on Windows native shell
Use Linux/WSL2 for reliable Buildozer builds.

### Policy rejection
Align privacy policy and Data Safety declarations with actual app behavior (especially financial data + external AI API usage).

---

## 13) Security reminders for this app

- Do not hardcode Anthropic API keys in source code
- Keep user-entered API keys local to device config
- Avoid logging sensitive receipt contents in production logs
- Keep signing keys backed up and access-controlled