# Giphery Android management app

Jetpack Compose (Material 3) client to pair with a Giphery server and manage
GIFs: upload, tag, search, edit, delete, with light/dark/auto theming and
Material You dynamic color.

## Architecture
- **MVVM + repository**, single-activity, Compose Navigation, Hilt DI.
- **data/** — Retrofit `GipheryApi`, DTOs, repositories, encrypted token store
  (`SecureTokenStore`, Keystore-backed), settings DataStore.
- **data/remote** — dynamic base-URL interceptor (server entered at pairing),
  auth header injection, and a `TokenAuthenticator` that transparently refreshes
  the access token on 401 (rotating refresh token).
- **domain/** — UI models. **ui/** — theme, navigation, screens + ViewModels.

## Security
- HTTPS only (`usesCleartextTraffic=false` + network security config).
- Refresh token + base URL in **EncryptedSharedPreferences** (Android Keystore);
  access token kept in memory only.
- Token store excluded from cloud backup / device transfer (`allowBackup=false`,
  data-extraction + backup rules); OkHttp logging redacts `Authorization`.
- Cert pinning is intentionally **off** (SWAG cert rotation / self-signed during
  dev would break pins). To enable, add a `CertificatePinner` in `NetworkModule`.

## Build
> The Gradle **wrapper jar** (`gradle/wrapper/gradle-wrapper.jar`) is a binary
> and is not committed here. Generate it once before building from the CLI:
>
> ```bash
> cd android
> gradle wrapper --gradle-version 8.13   # or just open the folder in Android Studio
> ```
> Android Studio (Ladybug+) regenerates it automatically on first sync.

```bash
cd android
./gradlew assembleDebug          # build the debug APK
./gradlew testDebugUnitTest      # unit tests (Turbine + coroutines-test)
./gradlew ktlintCheck detekt     # lint
```

Requires JDK 17, Android SDK with **compileSdk/targetSdk 36**, minSdk 26.

## Using the app
1. Admin creates an invitation in the web console and shares the code.
2. Launch the app → **Pair**: enter the server URL (`https://…`), the code, and a
   username → you land on the gallery.
3. Add GIFs (+), tag and search, tap a GIF to view/edit/delete, and toggle the
   theme in **Settings**. Logout/unpair revokes the device server-side.
