package com.giphery.app.ui.pairing

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.giphery.app.data.remote.ApiException
import com.giphery.app.data.repo.AuthRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class PairingUiState(
    val baseUrl: String = "https://",
    val code: String = "",
    val username: String = "",
    val loading: Boolean = false,
    val error: String? = null,
    val paired: Boolean = false,
) {
    val canSubmit: Boolean
        get() = baseUrl.startsWith("https://") && baseUrl.length > 8 &&
            code.isNotBlank() && username.length >= 3 && !loading
}

@HiltViewModel
class PairingViewModel @Inject constructor(
    private val authRepository: AuthRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(PairingUiState())
    val state: StateFlow<PairingUiState> = _state.asStateFlow()

    fun onBaseUrl(value: String) = _state.update { it.copy(baseUrl = value, error = null) }
    fun onCode(value: String) = _state.update { it.copy(code = value, error = null) }
    fun onUsername(value: String) = _state.update { it.copy(username = value, error = null) }

    fun submit() {
        val s = _state.value
        if (!s.canSubmit) return
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            authRepository.pair(s.baseUrl, s.code, s.username)
                .onSuccess { _state.update { st -> st.copy(loading = false, paired = true) } }
                .onFailure { e ->
                    val msg = (e as? ApiException)?.message ?: "Pairing failed. Check the details."
                    _state.update { st -> st.copy(loading = false, error = msg) }
                }
        }
    }
}
