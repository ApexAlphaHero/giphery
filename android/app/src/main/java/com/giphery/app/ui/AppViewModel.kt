package com.giphery.app.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.giphery.app.data.local.SettingsStore
import com.giphery.app.data.remote.SessionManager
import com.giphery.app.data.repo.AuthRepository
import com.giphery.app.domain.model.ThemeMode
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject

@HiltViewModel
class AppViewModel @Inject constructor(
    settingsStore: SettingsStore,
    authRepository: AuthRepository,
) : ViewModel() {

    val themeMode: StateFlow<ThemeMode> = settingsStore.themeMode
        .stateIn(viewModelScope, SharingStarted.Eagerly, ThemeMode.SYSTEM)

    val authState: StateFlow<SessionManager.AuthState> = authRepository.authState
}
