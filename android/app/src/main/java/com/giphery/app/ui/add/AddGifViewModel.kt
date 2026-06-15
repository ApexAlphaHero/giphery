package com.giphery.app.ui.add

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.giphery.app.data.remote.ApiException
import com.giphery.app.data.repo.GifRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import javax.inject.Inject

data class AddUiState(
    val pickedUri: Uri? = null,
    val filename: String = "upload.gif",
    val title: String = "",
    val tagsText: String = "",
    val uploading: Boolean = false,
    val error: String? = null,
    val done: Boolean = false,
)

@HiltViewModel
class AddGifViewModel @Inject constructor(
    @ApplicationContext private val context: Context,
    private val repository: GifRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(AddUiState())
    val state: StateFlow<AddUiState> = _state.asStateFlow()

    fun onPicked(uri: Uri) {
        _state.update { it.copy(pickedUri = uri, filename = queryName(uri), error = null) }
    }

    fun onTitle(value: String) = _state.update { it.copy(title = value) }
    fun onTags(value: String) = _state.update { it.copy(tagsText = value) }

    fun upload() {
        val s = _state.value
        val uri = s.pickedUri ?: return
        _state.update { it.copy(uploading = true, error = null) }
        viewModelScope.launch {
            val bytes = withContext(Dispatchers.IO) {
                runCatching { context.contentResolver.openInputStream(uri)?.use { it.readBytes() } }
                    .getOrNull()
            }
            if (bytes == null || bytes.isEmpty()) {
                _state.update { it.copy(uploading = false, error = "Couldn't read the selected file.") }
                return@launch
            }
            val tags = s.tagsText.split(",").map { it.trim() }.filter { it.isNotBlank() }
            repository.upload(bytes, s.filename, s.title.ifBlank { null }, tags)
                .onSuccess { _state.update { it.copy(uploading = false, done = true) } }
                .onFailure { e ->
                    _state.update {
                        it.copy(uploading = false, error = (e as? ApiException)?.message ?: "Upload failed.")
                    }
                }
        }
    }

    private fun queryName(uri: Uri): String {
        var name = "upload.gif"
        runCatching {
            context.contentResolver.query(uri, null, null, null, null)?.use { cursor ->
                val idx = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (idx >= 0 && cursor.moveToFirst()) {
                    cursor.getString(idx)?.let { name = it }
                }
            }
        }
        return if (name.endsWith(".gif", ignoreCase = true)) name else "$name.gif"
    }
}
