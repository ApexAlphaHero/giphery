package com.giphery.app.domain.model

enum class ThemeMode { LIGHT, DARK, SYSTEM }

data class Gif(
    val id: String,
    val title: String?,
    val tags: List<String>,
    val rawUrl: String,
    val width: Int,
    val height: Int,
    val byteSize: Long,
    val createdAt: String,
)

data class GifPage(
    val items: List<Gif>,
    val nextCursor: String?,
)

data class Tag(
    val name: String,
    val usageCount: Int,
)

data class ServerMeta(
    val serverVersion: String,
    val role: String,
    val gifs: Int,
    val storageBytes: Long,
    val tags: Int,
    val users: Int?,
    val devices: Int?,
)
