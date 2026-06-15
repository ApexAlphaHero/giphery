package com.giphery.app.ui.detail

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.giphery.app.data.remote.ApiException
import com.giphery.app.data.repo.GifRepository
import com.giphery.app.domain.model.Gif
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DetailUiState(
    val gif: Gif? = null,
    val loading: Boolean = true,
    val error: String? = null,
    val editing: Boolean = false,
    val titleDraft: String = "",
    val tagsDraft: String = "",
    val saving: Boolean = false,
    val deleting: Boolean = false,
    val deleted: Boolean = false,
)

@HiltViewModel
class DetailViewModel @Inject constructor(
    private val repository: GifRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(DetailUiState())
    val state: StateFlow<DetailUiState> = _state.asStateFlow()

    fun load(id: String) {
        _state.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            repository.get(id)
                .onSuccess { gif -> _state.update { it.copy(gif = gif, loading = false) } }
                .onFailure { e ->
                    _state.update {
                        it.copy(loading = false, error = (e as? ApiException)?.message ?: "Failed to load.")
                    }
                }
        }
    }

    fun startEditing() {
        val gif = _state.value.gif ?: return
        _state.update {
            it.copy(
                editing = true,
                titleDraft = gif.title.orEmpty(),
                tagsDraft = gif.tags.joinToString(", "),
            )
        }
    }

    fun cancelEditing() = _state.update { it.copy(editing = false) }
    fun onTitleDraft(value: String) = _state.update { it.copy(titleDraft = value) }
    fun onTagsDraft(value: String) = _state.update { it.copy(tagsDraft = value) }

    fun save() {
        val gif = _state.value.gif ?: return
        val s = _state.value
        val tags = s.tagsDraft.split(",").map { it.trim() }.filter { it.isNotBlank() }
        _state.update { it.copy(saving = true, error = null) }
        viewModelScope.launch {
            repository.update(gif.id, title = s.titleDraft.ifBlank { null }, tags = tags)
                .onSuccess { updated ->
                    _state.update { it.copy(gif = updated, editing = false, saving = false) }
                }
                .onFailure { e ->
                    _state.update {
                        it.copy(saving = false, error = (e as? ApiException)?.message ?: "Save failed.")
                    }
                }
        }
    }

    fun delete() {
        val gif = _state.value.gif ?: return
        _state.update { it.copy(deleting = true, error = null) }
        viewModelScope.launch {
            repository.delete(gif.id)
                .onSuccess { _state.update { it.copy(deleting = false, deleted = true) } }
                .onFailure { e ->
                    _state.update {
                        it.copy(deleting = false, error = (e as? ApiException)?.message ?: "Delete failed.")
                    }
                }
        }
    }
}
