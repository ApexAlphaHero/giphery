package com.giphery.app.data.repo

import com.giphery.app.data.remote.GipheryApi
import com.giphery.app.data.remote.SessionManager
import com.giphery.app.data.remote.dto.RedeemRequest
import com.giphery.app.data.remote.toApiException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.withContext
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class AuthRepository @Inject constructor(
    private val api: GipheryApi,
    private val session: SessionManager,
) {
    val authState: StateFlow<SessionManager.AuthState> = session.authState
    val username: String? get() = session.username
    val baseUrl: String? get() = session.baseUrl

    /** Redeem an invite code against [baseUrl] and persist the session. */
    suspend fun pair(baseUrl: String, code: String, username: String): Result<Unit> =
        withContext(Dispatchers.IO) {
            runCatching {
                val normalized = baseUrl.trim().trimEnd('/')
                require(normalized.startsWith("https://")) { "Server URL must use https://" }
                // Persist the base URL first so the request targets the right host.
                session.saveServer(normalized, username.trim())
                val result = api.redeem(
                    RedeemRequest(code = code.trim(), username = username.trim()),
                )
                session.onAuthenticated(result.accessToken, result.refreshToken)
            }.recoverCatching {
                if (it !is IllegalArgumentException) session.clear()
                throw it.toApiException()
            }
        }

    /** Revoke the device server-side, then clear local state. */
    suspend fun logout(): Result<Unit> = withContext(Dispatchers.IO) {
        runCatching { api.logout() }
            .also { session.clear() }
            .map { }
            .recoverCatching { throw it.toApiException() }
    }

    /** Local-only unpair (also attempts server revoke). */
    suspend fun unpair() {
        runCatching { withContext(Dispatchers.IO) { api.logout() } }
        session.clear()
    }
}
