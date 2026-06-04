package com.veritas.app.ui.matches

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.veritas.app.data.model.Match
import com.veritas.app.data.repository.AuthRepository
import com.veritas.app.data.repository.MatchRepository
import com.veritas.app.data.repository.UserRepository
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MatchesScreen(
    authRepo: AuthRepository,
    userRepo: UserRepository,
    onChat: (matchId: String, otherUserId: String) -> Unit,
    onBack: () -> Unit
) {
    val matchRepo = remember { MatchRepository() }
    var matchIds by remember { mutableStateOf<List<String>>(emptyList()) }
    var matchedUsers by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var isLoading by remember { mutableStateOf(true) }
    val scope = rememberCoroutineScope()
    val userId = authRepo.getCurrentUserId()

    LaunchedEffect(userId) {
        isLoading = true
        val result = matchRepo.getMatches(userId)
        result.onSuccess { ids ->
            matchIds = ids
            ids.forEach { id ->
                scope.launch {
                    val user = userRepo.getUserById(id).getOrNull()
                    if (user != null) {
                        matchedUsers = matchedUsers + (id to user.name)
                    }
                }
            }
        }
        isLoading = false
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Matches", fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Text("←", fontSize = 20.sp)
                    }
                }
            )
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentAlignment = Alignment.Center
        ) {
            when {
                isLoading -> CircularProgressIndicator()
                matchIds.isEmpty() -> {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            "No matches yet",
                            style = MaterialTheme.typography.headlineSmall
                        )
                        Text(
                            "Keep swiping!",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.5f)
                        )
                    }
                }
                else -> {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(matchIds) { otherUserId ->
                            val name = matchedUsers[otherUserId] ?: "Loading..."
                            Card(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { onChat("", otherUserId) }
                            ) {
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .padding(16.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Surface(
                                        modifier = Modifier.size(56.dp),
                                        shape = MaterialTheme.shapes.extraLarge,
                                        color = MaterialTheme.colorScheme.primaryContainer
                                    ) {
                                        Box(contentAlignment = Alignment.Center) {
                                            Text(
                                                text = name.take(1),
                                                style = MaterialTheme.typography.titleLarge,
                                                color = MaterialTheme.colorScheme.onPrimaryContainer
                                            )
                                        }
                                    }
                                    Spacer(modifier = Modifier.width(16.dp))
                                    Text(
                                        text = name,
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Medium
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
