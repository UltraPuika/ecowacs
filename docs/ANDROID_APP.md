# Android app (APK)

There are two ways to put the app on an Android phone. Both show the same app,
served by your Raspberry Pi.

| | Browser install (PWA) | Downloadable APK |
|---|---|---|
| How | Chrome → ⋮ → Add to Home screen | Download `Robots-x.y.z.apk` and install it |
| Updates | Automatic, whenever the Pi is updated | The app content updates automatically from the Pi. The wrapper itself rarely needs an update. |
| Needs | Nothing | Allowing "install unknown apps" once |

The APK is a small native Android app (`android/`). On first start it asks for
the Pi's address and then shows the web app full-screen. It has no robot logic
of its own and no Ecovacs credentials. It needs Android 10 or newer.

## Download

- **Releases:** GitHub → this repository → **Releases** → the latest `v…` release → `Robots-<version>.apk`.
- **Every build:** GitHub → **Actions** → "Android APK" → the latest run → **Artifacts**.
  This is a zip that contains the APK, and it needs a GitHub login.

If the repository is private, downloading needs a GitHub login. The easiest way
is to download the APK on your computer and send it to the phone, for example
via USB or Google Drive.

## Install on the phone

1. Open the downloaded `Robots-….apk` on the phone.
2. Android asks to allow installing from this source (Chrome or Files). Allow it, go back, and tap **Install**.
3. Open **Robots**. Enter the Pi's address, for example `192.168.1.10:8080`, and tap **Saglabāt**.
4. Log in with `APP_PASSWORD`.

If the Pi cannot be reached, the app shows **"Nav savienojuma"** with the
buttons **Mēģināt vēlreiz** and **Mainīt adresi**.

Play Protect may warn that the app is from an unknown developer. That is
expected for apps that are not from the Play Store.

## Making a new release

```bash
git tag v1.0.1
git push origin v1.0.1
```

The workflow builds the APK and attaches it to a GitHub release for that tag.

You can also publish a release without git: on GitHub go to **Actions → Android APK →
Run workflow**, choose the branch, enter a tag such as `v1.0.1` in **release_tag**, and click **Run workflow**.

## Stable signing (recommended)

Without a release key, the APK is signed with a throw-away debug key that
changes on every build. Installing a newer APK then fails with "App not
installed", and you have to uninstall the old one first. To avoid this, create a
key once and store it as GitHub secrets:

```bash
keytool -genkeypair -v -keystore robots-release.jks -alias robots \
  -keyalg RSA -keysize 4096 -validity 10000
base64 -w0 robots-release.jks   # copy the output
```

Go to GitHub → repository **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | the base64 output |
| `ANDROID_KEYSTORE_PASSWORD` | the keystore password |
| `ANDROID_KEY_ALIAS` | `robots` |
| `ANDROID_KEY_PASSWORD` | the key password |

Keep `robots-release.jks` and the passwords somewhere safe, outside the
repository. Never commit them.

## Building locally

You need the Android SDK (Android Studio) and JDK 17.

```bash
cd android
./gradlew assembleRelease     # → app/build/outputs/apk/release/app-release.apk
```

## Security notes

- The app allows plain `http://` because it talks to a Pi on your home network.
  Use it only on your home Wi-Fi. Do not expose the Pi to the internet.
- Links to other websites open in the normal browser, not inside the app.
- The app stores only the server address and the login cookie.
