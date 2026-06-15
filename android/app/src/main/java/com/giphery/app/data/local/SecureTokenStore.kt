package com.giphery.app.data.local

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Keystore-backed encrypted storage for the refresh token, server base URL,
 * and identity. The access token is NOT persisted here — it lives in memory
 * (see [com.giphery.app.data.remote.SessionManager]).
 */
@Singleton
class SecureTokenStore @Inject constructor(
    @ApplicationContext context: Context,
) {
    private val prefs: SharedPreferences = run {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            FILE_NAME,
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    var refreshToken: String?
        get() = prefs.getString(KEY_REFRESH, null)
        set(value) = prefs.edit().putStringOrRemove(KEY_REFRESH, value).apply()

    var baseUrl: String?
        get() = prefs.getString(KEY_BASE_URL, null)
        set(value) = prefs.edit().putStringOrRemove(KEY_BASE_URL, value).apply()

    var username: String?
        get() = prefs.getString(KEY_USERNAME, null)
        set(value) = prefs.edit().putStringOrRemove(KEY_USERNAME, value).apply()

    val isPaired: Boolean
        get() = !refreshToken.isNullOrBlank() && !baseUrl.isNullOrBlank()

    fun clear() {
        prefs.edit().clear().apply()
    }

    private fun SharedPreferences.Editor.putStringOrRemove(
        key: String,
        value: String?,
    ): SharedPreferences.Editor = if (value == null) remove(key) else putString(key, value)

    private companion object {
        const val FILE_NAME = "giphery_secure_tokens"
        const val KEY_REFRESH = "refresh_token"
        const val KEY_BASE_URL = "base_url"
        const val KEY_USERNAME = "username"
    }
}
