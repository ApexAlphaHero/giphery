package com.giphery.app.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import com.giphery.app.domain.model.ThemeMode

private val FallbackDark = darkColorScheme(
    primary = Color(0xFF8AA4FF),
    secondary = Color(0xFFB9C3E6),
    tertiary = Color(0xFFE6B3D8),
)

private val FallbackLight = lightColorScheme(
    primary = Color(0xFF3D5BD6),
    secondary = Color(0xFF55608A),
    tertiary = Color(0xFF8C4A78),
)

private val GipheryTypography = Typography()

@Composable
fun GipheryTheme(
    themeMode: ThemeMode,
    content: @Composable () -> Unit,
) {
    val dark = when (themeMode) {
        ThemeMode.LIGHT -> false
        ThemeMode.DARK -> true
        ThemeMode.SYSTEM -> isSystemInDarkTheme()
    }
    val supportsDynamic = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
    val context = LocalContext.current

    val colors = when {
        supportsDynamic && dark -> dynamicDarkColorScheme(context)
        supportsDynamic && !dark -> dynamicLightColorScheme(context)
        dark -> FallbackDark
        else -> FallbackLight
    }

    MaterialTheme(
        colorScheme = colors,
        typography = GipheryTypography,
        content = content,
    )
}
