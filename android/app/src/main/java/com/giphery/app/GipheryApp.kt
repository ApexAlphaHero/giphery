package com.giphery.app

import android.app.Application
import coil.ImageLoader
import coil.ImageLoaderFactory
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class GipheryApp : Application(), ImageLoaderFactory {
    // Hilt-provided loader that carries the auth token and decodes animated GIFs.
    @Inject
    lateinit var imageLoader: ImageLoader

    override fun newImageLoader(): ImageLoader = imageLoader
}
