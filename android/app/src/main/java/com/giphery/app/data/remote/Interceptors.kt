package com.giphery.app.data.remote

import com.giphery.app.data.remote.dto.RefreshRequest
import dagger.Lazy
import kotlinx.coroutines.runBlocking
import okhttp3.Authenticator
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import javax.inject.Inject
import javax.inject.Singleton

/** Placeholder host Retrofit is built with; rewritten per-request at runtime. */
const val PLACEHOLDER_HOST = "giphery.invalid"

/**
 * Rewrites requests aimed at [PLACEHOLDER_HOST] to the user-configured server
 * base URL (entered during pairing). Lets one Retrofit instance target any host.
 */
@Singleton
class DynamicBaseUrlInterceptor @Inject constructor(
    private val session: SessionManager,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        if (request.url.host != PLACEHOLDER_HOST) return chain.proceed(request)

        val base = session.baseUrl?.toHttpUrlOrNull()
            ?: return chain.proceed(request)
        val newUrl = request.url.newBuilder()
            .scheme(base.scheme)
            .host(base.host)
            .port(base.port)
            .build()
        return chain.proceed(request.newBuilder().url(newUrl).build())
    }
}

/** Adds the in-memory access token to outgoing API requests. */
@Singleton
class AuthInterceptor @Inject constructor(
    private val session: SessionManager,
) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = session.currentAccessToken()
        val request = if (token != null) {
            chain.request().newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        } else {
            chain.request()
        }
        return chain.proceed(request)
    }
}

/**
 * On a 401, transparently refreshes the access token (rotating refresh token)
 * and retries the original request once. On failure, clears the session so the
 * UI routes back to pairing.
 */
@Singleton
class TokenAuthenticator @Inject constructor(
    private val session: SessionManager,
    private val authApi: Lazy<AuthApi>,
) : Authenticator {
    override fun authenticate(route: Route?, response: Response): Request? {
        // Give up after one retry to avoid loops.
        if (responseCount(response) >= 2) return null

        val refresh = session.refreshToken ?: return null
        val newAccess = synchronized(this) {
            // Another thread may have refreshed already — retry with the current token.
            val current = session.currentAccessToken()
            if (current != null && current != tokenFrom(response)) {
                current
            } else {
                runCatching {
                    runBlocking { authApi.get().refresh(RefreshRequest(refresh)) }
                }.map { pair ->
                    session.onAuthenticated(pair.accessToken, pair.refreshToken)
                    pair.accessToken
                }.getOrElse {
                    session.clear()
                    return null
                }
            }
        }
        return response.request.newBuilder()
            .header("Authorization", "Bearer $newAccess")
            .build()
    }

    private fun tokenFrom(response: Response): String? =
        response.request.header("Authorization")?.removePrefix("Bearer ")

    private fun responseCount(response: Response): Int {
        var count = 1
        var prior = response.priorResponse
        while (prior != null) {
            count++
            prior = prior.priorResponse
        }
        return count
    }
}
