package com.giphery.app.data.remote

import com.giphery.app.data.local.SecureTokenStore
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Holds auth state: the access token in memory, the refresh token + base URL in
 * the Keystore-backed [SecureTokenStore]. Exposes a reactive [authState] so the
 * UI can react to pairing / logout.
 */
@Singleton
class SessionManager @Inject constructor(
    private val store: SecureTokenStore,
) {
    enum class AuthState { UNKNOWN, AUTHENTICATED, UNAUTHENTICATED }

    @Volatile
    private var accessToken: String? = null

    private val _authState = MutableStateFlow(
        if (store.isPaired) AuthState.AUTHENTICATED else AuthState.UNAUTHENTICATED,
    )
    val authState: StateFlow<AuthState> = _authState.asStateFlow()

    val baseUrl: String? get() = store.baseUrl
    val username: String? get() = store.username
    val refreshToken: String? get() = store.refreshToken

    fun currentAccessToken(): String? = accessToken

    /** Persist a freshly issued pair after pairing or a successful refresh. */
    fun onAuthenticated(accessToken: String, refreshToken: String) {
        this.accessToken = accessToken
        store.refreshToken = refreshToken
        _authState.value = AuthState.AUTHENTICATED
    }

    fun saveServer(baseUrl: String, username: String) {
        store.baseUrl = baseUrl
        store.username = username
    }

    fun updateAccessToken(token: String) {
        accessToken = token
    }

    /** Clear everything (logout / unpair / refresh failure). */
    fun clear() {
        accessToken = null
        store.clear()
        _authState.value = AuthState.UNAUTHENTICATED
    }
}
