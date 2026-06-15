package com.giphery.app.data.remote

import com.giphery.app.data.remote.dto.RefreshRequest
import com.giphery.app.data.remote.dto.TokenPairDto
import retrofit2.http.Body
import retrofit2.http.POST

/** Refresh endpoint kept on a separate client (no authenticator → no loop). */
interface AuthApi {
    @POST("api/v1/auth/refresh")
    suspend fun refresh(@Body body: RefreshRequest): TokenPairDto
}
