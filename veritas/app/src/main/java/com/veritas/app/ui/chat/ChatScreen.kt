package com.veritas.app.ui.chat

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.Query
import com.veritas.app.data.model.Message
import com.veritas.app.data.repository.AuthRepository
import com.veritas.app.data.repository.ChatRepository
import com.veritas.app.data.repository.UserRepository
import com.veritas.app.util.Constants
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    matchId: String,
    otherUserId: String,
    chatRepo: ChatRepository,
    authRepo: AuthRepository,
    userRepo: UserRepository,
    onBack: () -> Unit
) {
    var messages by remember { mutableStateOf<List<Message>>(emptyList()) }
    var inputText by remember { mutableStateOf("") }
    var otherUserName by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    val listState = rememberLazyListState()
    val senderId = authRepo.getCurrentUserId()
    val db = FirebaseFirestore.getInstance()

    LaunchedEffect(otherUserId) {
        val user = userRepo.getUserById(otherUserId).getOrNull()
        otherUserName = user?.name ?: "User"
    }

    LaunchedEffect(matchId) {
        db.collection(Constants.COLLECTION_MESSAGES)
            .whereEqualTo("matchId", matchId)
            .orderBy("createdAt", Query.Direction.ASCENDING)
            .addSnapshotListener { snapshot, _ ->
                val msgs = snapshot?.documents?.mapNotNull {
                    it.toObject(Message::class.java)?.copy(id = it.id)
                } ?: emptyList()
                messages = msgs
                if (msgs.isNotEmpty()) {
                    scope.launch {
                        listState.animateScrollToItem(msgs.size - 1)
                    }
                }
            }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(otherUserName, fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Text("←", fontSize = 20.sp)
                    }
                }
            )
        },
        bottomBar = {
            Surface(
                tonalElevation = 2.dp,
                modifier = Modifier.fillMaxWidth()
            ) {
                Row(
                    modifier = Modifier
                        .padding(8.dp)
                        .fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedTextField(
                        value = inputText,
                        onValueChange = { inputText = it },
                        modifier = Modifier.weight(1f),
                        placeholder = { Text("Type a message...") },
                        singleLine = true
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Button(
                        onClick = {
                            if (inputText.isNotBlank()) {
                                scope.launch {
                                    chatRepo.sendMessage(matchId, senderId, inputText.trim())
                                }
                                inputText = ""
                            }
                        }
                    ) {
                        Text("Send")
                    }
                }
            }
        }
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            state = listState,
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            items(messages) { msg ->
                val isMine = msg.senderId == senderId
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalAlignment = if (isMine) Alignment.End else Alignment.Start
                ) {
                    Surface(
                        shape = MaterialTheme.shapes.medium,
                        color = if (isMine)
                            MaterialTheme.colorScheme.primary
                        else
                            MaterialTheme.colorScheme.surfaceVariant,
                        modifier = Modifier.widthIn(max = 280.dp)
                    ) {
                        Text(
                            text = msg.text,
                            modifier = Modifier.padding(12.dp),
                            color = if (isMine)
                                MaterialTheme.colorScheme.onPrimary
                            else
                                MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
        }
    }
}
