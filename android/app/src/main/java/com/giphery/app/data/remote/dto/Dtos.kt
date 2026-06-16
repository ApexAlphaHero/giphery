package com.giphery.app.data.remote.dto

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class TokenPairDto(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("token_type") val tokenType: String = "bearer",
)

@Serializable
data class UserDto(
    val id: String,
    val username: String,
    @SerialName("display_name") val displayName: String? = null,
    val role: String,
    @SerialName("is_active") val isActive: Boolean = true,
)

@Serializable
data class AuthResultDto(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    val user: UserDto,
)

@Serializable
data class RedeemRequest(
    val code: String,
    val username: String,
    @SerialName("display_name") val displayName: String? = null,
)

@Serializable
data class RefreshRequest(
    @SerialName("refresh_token") val refreshToken: String,
)

@Serializable
data class GifMetaDto(
    val id: String,
    @SerialName("owner_id") val ownerId: String,
    val title: String? = null,
    @SerialName("original_filename") val originalFilename: String,
    @SerialName("mime_type") val mimeType: String,
    @SerialName("byte_size") val byteSize: Long,
    val width: Int,
    val height: Int,
    @SerialName("content_hash") val contentHash: String,
    val tags: List<String> = emptyList(),
    @SerialName("raw_url") val rawUrl: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
)

@Serializable
data class GifPageDto(
    val items: List<GifMetaDto>,
    @SerialName("next_cursor") val nextCursor: String? = null,
)

@Serializable
data class GifUpdateRequest(
    val title: String? = null,
    val tags: List<String>? = null,
)

@Serializable
data class TagDto(
    val name: String,
    @SerialName("usage_count") val usageCount: Int,
)

@Serializable
data class MetaDto(
    @SerialName("server_version") val serverVersion: String,
    val role: String,
    val gifs: Int,
    @SerialName("storage_bytes") val storageBytes: Long,
    val tags: Int,
    val users: Int? = null,
    val devices: Int? = null,
)

@Serializable
data class ApiErrorBody(
    val error: ApiErrorDetail,
)

@Serializable
data class ApiErrorDetail(
    val code: String,
    val message: String,
)
