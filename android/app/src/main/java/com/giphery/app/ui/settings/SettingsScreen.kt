package com.giphery.app.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.selection.selectable
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import com.giphery.app.domain.model.ThemeMode

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    viewModel: SettingsViewModel = hiltViewModel(),
) {
    val theme by viewModel.themeMode.collectAsState()
    val meta by viewModel.meta.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Settings") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("Appearance", style = MaterialTheme.typography.titleMedium)
            Card(modifier = Modifier.fillMaxWidth()) {
                Column {
                    ThemeOption("Light", theme == ThemeMode.LIGHT) { viewModel.setTheme(ThemeMode.LIGHT) }
                    ThemeOption("Dark", theme == ThemeMode.DARK) { viewModel.setTheme(ThemeMode.DARK) }
                    ThemeOption("System default", theme == ThemeMode.SYSTEM) {
                        viewModel.setTheme(ThemeMode.SYSTEM)
                    }
                }
            }

            Text("Account", style = MaterialTheme.typography.titleMedium)
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Signed in as ${viewModel.username ?: "—"}")
                    Text(
                        viewModel.baseUrl ?: "—",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            Text("About & stats", style = MaterialTheme.typography.titleMedium)
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(
                    modifier = Modifier.fillMaxWidth().padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    StatRow("App version", viewModel.appVersion)
                    when {
                        meta.loading -> StatRow("Server", "loading…")
                        meta.error != null -> StatRow("Server", meta.error ?: "unavailable")
                        meta.meta != null -> {
                            val m = meta.meta!!
                            StatRow("Server version", m.serverVersion)
                            StatRow(if (m.role == "admin") "GIFs (all users)" else "GIFs", m.gifs.toString())
                            StatRow("Storage used", formatBytes(m.storageBytes))
                            StatRow("Tags", m.tags.toString())
                            m.users?.let { StatRow("Users", it.toString()) }
                            m.devices?.let { StatRow("Paired devices", it.toString()) }
                        }
                    }
                }
            }

            OutlinedButton(onClick = viewModel::logout, modifier = Modifier.fillMaxWidth()) {
                Text("Log out")
            }
            OutlinedButton(onClick = viewModel::unpair, modifier = Modifier.fillMaxWidth()) {
                Text("Unpair this device")
            }
        }
    }
}

@Composable
private fun StatRow(label: String, value: String) {
    androidx.compose.foundation.layout.Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.weight(1f),
        )
        Text(value, style = MaterialTheme.typography.bodyMedium)
    }
}

private fun formatBytes(bytes: Long): String {
    if (bytes < 1024) return "$bytes B"
    val units = listOf("KB", "MB", "GB", "TB")
    var value = bytes.toDouble() / 1024
    var i = 0
    while (value >= 1024 && i < units.size - 1) {
        value /= 1024
        i++
    }
    return String.format(java.util.Locale.US, "%.1f %s", value, units[i])
}

@Composable
private fun ThemeOption(label: String, selected: Boolean, onClick: () -> Unit) {
    androidx.compose.foundation.layout.Row(
        modifier = Modifier
            .fillMaxWidth()
            .selectable(selected = selected, onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        RadioButton(selected = selected, onClick = onClick)
        Text(label, modifier = Modifier.padding(start = 12.dp))
    }
    HorizontalDivider()
}
