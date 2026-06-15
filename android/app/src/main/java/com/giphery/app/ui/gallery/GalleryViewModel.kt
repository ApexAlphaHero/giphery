package com.giphery.app.ui.gallery

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.giphery.app.data.remote.ApiException
import com.giphery.app.data.repo.GifRepository
import com.giphery.app.domain.model.Gif
import com.giphery.app.domain.model.Tag
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class GalleryUiState(
    val items: List<Gif> = emptyList(),
    val tags: List<Tag> = emptyList(),
    val query: String = "",
    val selectedTag: String? = null,
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val loadingMore: Boolean = false,
    val error: String? = null,
    val nextCursor: String? = null,
) {
    val isEmpty: Boolean get() = !loading && error == null && items.isEmpty()
}

@HiltViewModel
class GalleryViewModel @Inject constructor(
    private val repository: GifRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(GalleryUiState())
    val state: StateFlow<GalleryUiState> = _state.asStateFlow()

    init {
        refresh()
        loadTags()
    }

    fun onQueryChange(value: String) = _state.update { it.copy(query = value) }

    fun onSearch() = reload()

    fun onSelectTag(tag: String?) {
        _state.update { it.copy(selectedTag = tag) }
        reload()
    }

    fun refresh() {
        _state.update { it.copy(refreshing = true, error = null) }
        load(reset = true)
    }

    private fun reload() {
        _state.update { it.copy(loading = true, error = null) }
        load(reset = true)
    }

    fun loadMore() {
        val s = _state.value
        if (s.loadingMore || s.nextCursor == null) return
        _state.update { it.copy(loadingMore = true) }
        load(reset = false)
    }

    private fun load(reset: Boolean) {
        val s = _state.value
        val cursor = if (reset) null else s.nextCursor
        viewModelScope.launch {
            repository.list(q = s.query, tag = s.selectedTag, cursor = cursor)
                .onSuccess { page ->
                    _state.update {
                        it.copy(
                            items = if (reset) page.items else it.items + page.items,
                            nextCursor = page.nextCursor,
                            loading = false,
                            refreshing = false,
                            loadingMore = false,
                            error = null,
                        )
                    }
                }
                .onFailure { e ->
                    _state.update {
                        it.copy(
                            loading = false,
                            refreshing = false,
                            loadingMore = false,
                            error = (e as? ApiException)?.message ?: "Failed to load.",
                        )
                    }
                }
        }
    }

    private fun loadTags() {
        viewModelScope.launch {
            repository.tags(null).onSuccess { tags ->
                _state.update { it.copy(tags = tags) }
            }
        }
    }
}
