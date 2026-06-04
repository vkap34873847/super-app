package com.veritas.app.data.repository

import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.Query
import com.veritas.app.data.model.Message
import com.veritas.app.util.Constants
import kotlinx.coroutines.tasks.await

class ChatRepository {
    private val db = FirebaseFirestore.getInstance()

    companion object {
        private val devMessages = mutableListOf<Map<String, Any>>()
    }

    suspend fun sendMessage(matchId: String, senderId: String, text: String): Result<Unit> = runCatching {
        try {
            val msg = mapOf(
                "matchId" to matchId,
                "senderId" to senderId,
                "text" to text,
                "createdAt" to System.currentTimeMillis()
            )
            db.collection(Constants.COLLECTION_MESSAGES).add(msg).await()

            db.collection(Constants.COLLECTION_MATCHES).document(matchId)
                .update("lastMessageAt", System.currentTimeMillis(), "lastMessageText", text)
                .await()
        } catch (e: Exception) {
            devMessages.add(mapOf(
                "matchId" to matchId,
                "senderId" to senderId,
                "text" to text,
                "createdAt" to System.currentTimeMillis()
            ))
        }
    }

    fun getMessagesFlow(matchId: String) = db.collection(Constants.COLLECTION_MESSAGES)
        .whereEqualTo("matchId", matchId)
        .orderBy("createdAt", Query.Direction.ASCENDING)
        .addSnapshotListener { snapshot, _ ->
            snapshot?.let {
                // handled by caller via callback
            }
        }

    fun listenForMatches(userId: String, onUpdate: (List<com.veritas.app.data.model.Match>) -> Unit) {
        try {
            db.collection(Constants.COLLECTION_MATCHES)
                .whereEqualTo("user1Id", userId)
                .orderBy("lastMessageAt", Query.Direction.DESCENDING)
                .addSnapshotListener { snapshot, _ ->
                    val matches = snapshot?.documents?.mapNotNull {
                        it.toObject(com.veritas.app.data.model.Match::class.java)?.copy(id = it.id)
                    } ?: emptyList()
                    onUpdate(matches)
                }

            db.collection(Constants.COLLECTION_MATCHES)
                .whereEqualTo("user2Id", userId)
                .orderBy("lastMessageAt", Query.Direction.DESCENDING)
                .addSnapshotListener { snapshot, _ ->
                    val matches = snapshot?.documents?.mapNotNull {
                        it.toObject(com.veritas.app.data.model.Match::class.java)?.copy(id = it.id)
                    } ?: emptyList()
                    onUpdate(matches)
                }
        } catch (e: Exception) {
            // dev mode: no-op
        }
    }
}
