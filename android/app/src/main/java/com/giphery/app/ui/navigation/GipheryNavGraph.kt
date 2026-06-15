package com.giphery.app.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.giphery.app.data.remote.SessionManager
import com.giphery.app.ui.add.AddGifScreen
import com.giphery.app.ui.detail.DetailScreen
import com.giphery.app.ui.gallery.GalleryScreen
import com.giphery.app.ui.pairing.PairingScreen
import com.giphery.app.ui.settings.SettingsScreen

object Routes {
    const val PAIRING = "pairing"
    const val GALLERY = "gallery"
    const val ADD = "add"
    const val SETTINGS = "settings"
    const val DETAIL = "detail/{gifId}"

    fun detail(gifId: String) = "detail/$gifId"
}

@Composable
fun GipheryNavGraph(authState: SessionManager.AuthState) {
    val navController = rememberNavController()

    val start = if (authState == SessionManager.AuthState.AUTHENTICATED) {
        Routes.GALLERY
    } else {
        Routes.PAIRING
    }

    // React to logout/unpair: bounce back to pairing and clear the back stack.
    LaunchedEffect(authState) {
        if (authState == SessionManager.AuthState.UNAUTHENTICATED) {
            navController.navigate(Routes.PAIRING) {
                popUpTo(0) { inclusive = true }
                launchSingleTop = true
            }
        }
    }

    NavHost(navController = navController, startDestination = start) {
        composable(Routes.PAIRING) {
            PairingScreen(
                onPaired = {
                    navController.navigate(Routes.GALLERY) {
                        popUpTo(Routes.PAIRING) { inclusive = true }
                    }
                },
            )
        }
        composable(Routes.GALLERY) {
            GalleryScreen(
                onOpenGif = { navController.navigate(Routes.detail(it)) },
                onAddGif = { navController.navigate(Routes.ADD) },
                onOpenSettings = { navController.navigate(Routes.SETTINGS) },
            )
        }
        composable(Routes.ADD) {
            AddGifScreen(onDone = { navController.popBackStack() })
        }
        composable(Routes.SETTINGS) {
            SettingsScreen(onBack = { navController.popBackStack() })
        }
        composable(Routes.DETAIL) { entry ->
            val gifId = entry.arguments?.getString("gifId").orEmpty()
            DetailScreen(
                gifId = gifId,
                onBack = { navController.popBackStack() },
                onDeleted = { navController.popBackStack() },
            )
        }
    }
}
