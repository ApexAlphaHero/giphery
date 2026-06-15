package com.giphery.app.data.remote

import com.giphery.app.data.remote.dto.AuthResultDto
import com.giphery.app.data.remote.dto.GifMetaDto
import com.giphery.app.data.remote.dto.GifPageDto
import com.giphery.app.data.remote.dto.GifUpdateRequest
import com.giphery.app.data.remote.dto.RedeemRequest
import com.giphery.app.data.remote.dto.TagDto
import okhttp3.MultipartBody
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

interface GipheryApi {

    @POST("api/v1/invites/redeem")
    suspend fun redeem(@Body body: RedeemRequest): AuthResultDto

    @GET("api/v1/gifs")
    suspend fun listGifs(
        @Query("q") q: String? = null,
        @Query("tag") tag: String? = null,
        @Query("limit") limit: Int = 30,
        @Query("cursor") cursor: String? = null,
    ): GifPageDto

    @GET("api/v1/gifs/{id}")
    suspend fun getGif(@Path("id") id: String): GifMetaDto

    @Multipart
    @POST("api/v1/gifs")
    suspend fun uploadGif(
        @Part file: MultipartBody.Part,
        @Part("title") title: okhttp3.RequestBody? = null,
        @Part("tags") tags: okhttp3.RequestBody? = null,
    ): GifMetaDto

    @PATCH("api/v1/gifs/{id}")
    suspend fun updateGif(
        @Path("id") id: String,
        @Body body: GifUpdateRequest,
    ): GifMetaDto

    @DELETE("api/v1/gifs/{id}")
    suspend fun deleteGif(@Path("id") id: String)

    @GET("api/v1/tags")
    suspend fun listTags(@Query("q") q: String? = null): List<TagDto>

    @POST("api/v1/auth/logout")
    suspend fun logout()
}
