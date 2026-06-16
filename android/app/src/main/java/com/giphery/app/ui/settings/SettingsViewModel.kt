package com.giphery.app.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.giphery.app.BuildConfig
import com.giphery.app.data.local.SettingsStore
import com.giphery.app.data.repo.AuthRepository
import com.giphery.app.data.repo.GifRepository
import com.giphery.app.domain.model.ServerMeta
import com.giphery.app.domain.model.ThemeMode
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class MetaUiState(
    val loading: Boolean = true,
    val meta: ServerMeta? = null,
    val error: String? = null,
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val settingsStore: SettingsStore,
    private val authRepository: AuthRepository,
    private val gifRepository: GifRepository,
) : ViewModel() {

    val themeMode: StateFlow<ThemeMode> = settingsStore.themeMode
        .stateIn(viewModelScope, SharingStarted.Eagerly, ThemeMode.SYSTEM)

    val username: String? get() = authRepository.username
    val baseUrl: String? get() = authRepository.baseUrl
    val appVersion: String = "${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})"

    private val _meta = MutableStateFlow(MetaUiState())
    val meta: StateFlow<MetaUiState> = _meta.asStateFlow()

    init {
        loadMeta()
    }

    fun loadMeta() {
        _meta.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            gifRepository.meta()
                .onSuccess { m -> _meta.update { MetaUiState(loading = false, meta = m) } }
                .onFailure { e ->
                    _meta.update { it.copy(loading = false, error = e.message ?: "Couldn't load server info") }
                }
        }
    }

    fun setTheme(mode: ThemeMode) {
        viewModelScope.launch { settingsStore.setThemeMode(mode) }
    }

    fun logout() {
        viewModelScope.launch { authRepository.logout() }
    }

    fun unpair() {
        viewModelScope.launch { authRepository.unpair() }
    }
}
