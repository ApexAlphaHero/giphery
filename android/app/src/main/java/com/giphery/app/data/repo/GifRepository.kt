package com.giphery.app.data.repo

import com.giphery.app.data.remote.GipheryApi
import com.giphery.app.data.remote.dto.GifMetaDto
import com.giphery.app.data.remote.dto.GifUpdateRequest
import com.giphery.app.data.remote.toApiException
import com.giphery.app.domain.model.Gif
import com.giphery.app.domain.model.GifPage
import com.giphery.app.domain.model.ServerMeta
import com.giphery.app.domain.model.Tag
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class GifRepository @Inject constructor(
    private val api: GipheryApi,
) {
    suspend fun list(q: String?, tag: String?, cursor: String?): Result<GifPage> =
        call {
            val page = api.listGifs(q = q?.ifBlank { null }, tag = tag, cursor = cursor)
            GifPage(page.items.map { it.toGif() }, page.nextCursor)
        }

    suspend fun get(id: String): Result<Gif> = call { api.getGif(id).toGif() }

    suspend fun upload(
        bytes: ByteArray,
        filename: String,
        title: String?,
        tags: List<String>,
    ): Result<Gif> = call {
        val part = MultipartBody.Part.createFormData(
            "file",
            filename,
            bytes.toRequestBody("image/gif".toMediaTypeOrNull()),
        )
        val titleBody: RequestBody? = title?.takeIf { it.isNotBlank() }?.toPlain()
        val tagsBody: RequestBody? = tags.filter { it.isNotBlank() }
            .takeIf { it.isNotEmpty() }
            ?.joinToString(",")
            ?.toPlain()
        api.uploadGif(part, titleBody, tagsBody).toGif()
    }

    suspend fun update(id: String, title: String?, tags: List<String>?): Result<Gif> =
        call { api.updateGif(id, GifUpdateRequest(title = title, tags = tags)).toGif() }

    suspend fun delete(id: String): Result<Unit> = call { api.deleteGif(id) }

    suspend fun tags(q: String?): Result<List<Tag>> =
        call { api.listTags(q?.ifBlank { null }).map { Tag(it.name, it.usageCount) } }

    suspend fun meta(): Result<ServerMeta> = call {
        val m = api.meta()
        ServerMeta(
            serverVersion = m.serverVersion,
            role = m.role,
            gifs = m.gifs,
            storageBytes = m.storageBytes,
            tags = m.tags,
            users = m.users,
            devices = m.devices,
        )
    }

    private suspend fun <T> call(block: suspend () -> T): Result<T> =
        withContext(Dispatchers.IO) {
            runCatching { block() }.recoverCatching { throw it.toApiException() }
        }

    private fun String.toPlain(): RequestBody =
        toRequestBody("text/plain".toMediaTypeOrNull())

    private fun GifMetaDto.toGif() = Gif(
        id = id,
        title = title,
        tags = tags,
        rawUrl = rawUrl,
        width = width,
        height = height,
        byteSize = byteSize,
        createdAt = createdAt,
    )
}
