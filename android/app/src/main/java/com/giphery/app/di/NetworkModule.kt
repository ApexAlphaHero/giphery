package com.giphery.app.di

import com.giphery.app.BuildConfig
import com.giphery.app.data.remote.AuthApi
import com.giphery.app.data.remote.AuthInterceptor
import com.giphery.app.data.remote.DynamicBaseUrlInterceptor
import com.giphery.app.data.remote.GipheryApi
import com.giphery.app.data.remote.PLACEHOLDER_HOST
import com.giphery.app.data.remote.TokenAuthenticator
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit
import javax.inject.Named
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    private const val PLACEHOLDER_BASE = "https://$PLACEHOLDER_HOST/"

    @Provides
    @Singleton
    fun provideJson(): Json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
    }

    private fun logging(): HttpLoggingInterceptor =
        HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG) {
                HttpLoggingInterceptor.Level.BASIC
            } else {
                HttpLoggingInterceptor.Level.NONE
            }
            // Never log secrets.
            redactHeader("Authorization")
            redactHeader("Cookie")
        }

    /** Bare client for the refresh endpoint (no authenticator → no refresh loop). */
    @Provides
    @Singleton
    @Named("auth")
    fun provideAuthClient(dynamicBaseUrl: DynamicBaseUrlInterceptor): OkHttpClient =
        OkHttpClient.Builder()
            .addInterceptor(dynamicBaseUrl)
            .addInterceptor(logging())
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()

    /** Main client: injects the access token and refreshes transparently on 401. */
    @Provides
    @Singleton
    @Named("api")
    fun provideApiClient(
        dynamicBaseUrl: DynamicBaseUrlInterceptor,
        authInterceptor: AuthInterceptor,
        authenticator: TokenAuthenticator,
    ): OkHttpClient =
        OkHttpClient.Builder()
            .addInterceptor(dynamicBaseUrl)
            .addInterceptor(authInterceptor)
            .authenticator(authenticator)
            .addInterceptor(logging())
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .build()

    @Provides
    @Singleton
    fun provideAuthApi(@Named("auth") client: OkHttpClient, json: Json): AuthApi =
        Retrofit.Builder()
            .baseUrl(PLACEHOLDER_BASE)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(AuthApi::class.java)

    @Provides
    @Singleton
    fun provideGipheryApi(@Named("api") client: OkHttpClient, json: Json): GipheryApi =
        Retrofit.Builder()
            .baseUrl(PLACEHOLDER_BASE)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(GipheryApi::class.java)
}
