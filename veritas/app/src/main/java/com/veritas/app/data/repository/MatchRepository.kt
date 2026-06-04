package com.veritas.app.data.repository

import com.google.firebase.firestore.FirebaseFirestore
import com.veritas.app.data.model.Match
import com.veritas.app.util.Constants
import kotlinx.coroutines.tasks.await

class MatchRepository {
    private val db = FirebaseFirestore.getInstance()

    companion object {
        private val devSwipes = mutableListOf<Map<String, Any>>()
        private val devMatches = mutableListOf<Match>()
    }

    suspend fun recordSwipe(swiperId: String, swipedId: String, direction: String): Result<Boolean> = runCatching {
        try {
            val existing = db.collection(Constants.COLLECTION_SWIPES)
                .whereEqualTo("swiperId", swiperId)
                .whereEqualTo("swipedId", swipedId)
                .get()
                .await()

            if (existing.isEmpty) {
                db.collection(Constants.COLLECTION_SWIPES).add(mapOf(
                    "swiperId" to swiperId,
                    "swipedId" to swipedId,
                    "direction" to direction,
                    "createdAt" to System.currentTimeMillis()
                )).await()
            }

            if (direction == Constants.SWIPE_LIKE) {
                val reverseSwipe = db.collection(Constants.COLLECTION_SWIPES)
                    .whereEqualTo("swiperId", swipedId)
                    .whereEqualTo("swipedId", swiperId)
                    .whereEqualTo("direction", Constants.SWIPE_LIKE)
                    .get()
                    .await()

                if (!reverseSwipe.isEmpty) {
                    val match = Match(
                        user1Id = swiperId,
                        user2Id = swipedId,
                        createdAt = System.currentTimeMillis()
                    )
                    db.collection(Constants.COLLECTION_MATCHES).add(match).await()
                    return@runCatching true
                }
            }
        } catch (e: Exception) {
            // dev mode
            if (direction == Constants.SWIPE_LIKE) {
                val reverseSwipe = devSwipes.any {
                    it["swiperId"] == swipedId && it["swipedId"] == swiperId && it["direction"] == Constants.SWIPE_LIKE
                }
                devSwipes.add(mapOf(
                    "swiperId" to swiperId,
                    "swipedId" to swipedId,
                    "direction" to direction
                ))
                if (reverseSwipe) {
                    return@runCatching true
                }
            } else {
                devSwipes.add(mapOf(
                    "swiperId" to swiperId,
                    "swipedId" to swipedId,
                    "direction" to direction
                ))
            }
        }
        false
    }

    suspend fun getMatches(userId: String): Result<List<String>> = runCatching {
        try {
            val snapshot = db.collection(Constants.COLLECTION_MATCHES)
                .whereEqualTo("user1Id", userId).get().await()
            val snapshot2 = db.collection(Constants.COLLECTION_MATCHES)
                .whereEqualTo("user2Id", userId).get().await()
            val ids = mutableListOf<String>()
            snapshot.documents.forEach { ids.add(it.getString("user2Id") ?: "") }
            snapshot2.documents.forEach { ids.add(it.getString("user1Id") ?: "") }
            ids.filter { it.isNotEmpty() }
        } catch (e: Exception) {
            devMatches.filter { it.user1Id == userId || it.user2Id == userId }
                .map { if (it.user1Id == userId) it.user2Id else it.user1Id }
        }
    }

    suspend fun getSwipedIds(userId: String): Result<List<String>> = runCatching {
        try {
            val snapshot = db.collection(Constants.COLLECTION_SWIPES)
                .whereEqualTo("swiperId", userId).get().await()
            snapshot.documents.mapNotNull { it.getString("swipedId") }
        } catch (e: Exception) {
            devSwipes.filter { it["swiperId"] == userId }
                .map { it["swipedId"] as String }
        }
    }
}
