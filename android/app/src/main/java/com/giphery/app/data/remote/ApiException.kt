package com.giphery.app.data.remote

import com.giphery.app.data.remote.dto.ApiErrorBody
import kotlinx.serialization.json.Json
import retrofit2.HttpException

/** A user-presentable error parsed from the API error envelope. */
class ApiException(
    val code: String,
    override val message: String,
    val status: Int,
) : Exception(message)

private val errorJson = Json { ignoreUnknownKeys = true }

fun Throwable.toApiException(): ApiException = when (this) {
    is ApiException -> this
    is HttpException -> {
        val body = response()?.errorBody()?.string()
        val parsed = body?.let {
            runCatching { errorJson.decodeFromString<ApiErrorBody>(it).error }.getOrNull()
        }
        ApiException(
            code = parsed?.code ?: "http_${code()}",
            message = parsed?.message ?: "Request failed (${code()})",
            status = code(),
        )
    }
    is java.net.UnknownHostException ->
        ApiException("network", "Can't reach the server. Check the URL and your connection.", 0)
    is java.net.SocketTimeoutException ->
        ApiException("timeout", "The server took too long to respond.", 0)
    else -> ApiException("unknown", message ?: "Something went wrong.", 0)
}
