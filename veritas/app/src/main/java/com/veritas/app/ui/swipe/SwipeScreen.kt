package com.veritas.app.ui.swipe

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.veritas.app.data.model.User
import com.veritas.app.data.repository.AuthRepository
import com.veritas.app.data.repository.MatchRepository
import com.veritas.app.data.repository.UserRepository
import kotlinx.coroutines.launch
import kotlin.math.roundToInt

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SwipeScreen(
    userRepo: UserRepository,
    matchRepo: MatchRepository,
    authRepo: AuthRepository,
    onOpenMatches: () -> Unit,
    onOpenProfile: () -> Unit
) {
    var users by remember { mutableStateOf<List<User>>(emptyList()) }
    var currentIndex by remember { mutableStateOf(0) }
    var swipedIds by remember { mutableStateOf<Set<String>>(emptySet()) }
    var isLoading by remember { mutableStateOf(true) }
    var matchFound by remember { mutableStateOf(false) }
    var matchName by remember { mutableStateOf("") }
    var offsetX by remember { mutableFloatStateOf(0f) }
    var offsetY by remember { mutableFloatStateOf(0f) }
    val scope = rememberCoroutineScope()

            val userId = authRepo.getCurrentUserId()

    LaunchedEffect(Unit) {
        isLoading = true
        val college = authRepo.getUserProfile().getOrNull()?.college ?: ""
        val result = userRepo.getUsersForSwipe(excludeIds = swipedIds.toList(), college = college)
        result.onSuccess {
            users = it
        }
        isLoading = false
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Veritas", fontWeight = FontWeight.Bold) },
                actions = {
                    IconButton(onClick = onOpenMatches) {
                        Text("♥", fontSize = 20.sp)
                    }
                    IconButton(onClick = onOpenProfile) {
                        Text("👤", fontSize = 20.sp)
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
                isLoading -> {
                    CircularProgressIndicator()
                }
                users.isEmpty() || currentIndex >= users.size -> {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            "No more profiles",
                            style = MaterialTheme.typography.headlineSmall
                        )
                        Text(
                            "Check back later!",
                            style = MaterialTheme.typography.bodyMedium,
                            color = Color.Gray
                        )
                    }
                }
                else -> {
                    val currentUser = users[currentIndex]
                    Card(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp)
                            .height(500.dp)
                            .graphicsLayer {
                                translationX = offsetX
                                translationY = offsetY
                                rotationZ = offsetX * 0.02f
                            }
                            .pointerInput(Unit) {
                                detectDragGestures(
                                    onDragEnd = {
                                        if (kotlin.math.abs(offsetX) > 300f) {
                                            val direction = if (offsetX > 0) "like" else "pass"
                                            scope.launch {
                    val isMatch = matchRepo.recordSwipe(
                        swiperId = userId,
                        swipedId = currentUser.id ?: "",
                        direction = direction
                    ).getOrDefault(false)
                                                if (isMatch) {
                                                    matchName = currentUser.name
                                                    matchFound = true
                                                }
                                            }
                                            swipedIds = swipedIds + (currentUser.id ?: "")
                                            currentIndex++
                                        }
                                        offsetX = 0f
                                        offsetY = 0f
                                    }
                                ) { change, dragAmount ->
                                    change.consume()
                                    offsetX += dragAmount.x
                                    offsetY += dragAmount.y
                                }
                            },
                        shape = RoundedCornerShape(20.dp),
                        elevation = CardDefaults.cardElevation(defaultElevation = 8.dp)
                    ) {
                        Column(
                            modifier = Modifier.fillMaxSize().padding(24.dp),
                            verticalArrangement = Arrangement.Center
                        ) {
                            Text(
                                text = currentUser.name,
                                style = MaterialTheme.typography.headlineLarge,
                                fontWeight = FontWeight.Bold
                            )
                            Spacer(modifier = Modifier.height(4.dp))
                            Text(
                                text = "${currentUser.age} · ${currentUser.college}",
                                style = MaterialTheme.typography.bodyLarge,
                                color = Color.Gray
                            )
                            Spacer(modifier = Modifier.height(16.dp))
                            Text(
                                text = currentUser.bio,
                                style = MaterialTheme.typography.bodyMedium
                            )
                        }
                    }

                    if (offsetX > 50f) {
                        Text(
                            "LIKE",
                            color = Color(0xFF4CAF50),
                            fontSize = 32.sp,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier
                                .align(Alignment.CenterStart)
                                .padding(24.dp)
                                .graphicsLayer { alpha = (offsetX / 300f).coerceIn(0f, 1f) }
                        )
                    } else if (offsetX < -50f) {
                        Text(
                            "NOPE",
                            color = Color(0xFFF44336),
                            fontSize = 32.sp,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier
                                .align(Alignment.CenterEnd)
                                .padding(24.dp)
                                .graphicsLayer { alpha = (-offsetX / 300f).coerceIn(0f, 1f) }
                        )
                    }
                }
            }

            if (matchFound) {
                AlertDialog(
                    onDismissRequest = { matchFound = false },
                    title = { Text("It's a match!") },
                    text = { Text("You and $matchName liked each other.") },
                    confirmButton = {
                        TextButton(onClick = {
                            matchFound = false
                            onOpenMatches()
                        }) { Text("Message") }
                    },
                    dismissButton = {
                        TextButton(onClick = { matchFound = false }) { Text("Keep Swiping") }
                    }
                )
            }
        }
    }
}
