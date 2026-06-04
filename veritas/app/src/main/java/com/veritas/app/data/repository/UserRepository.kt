package com.veritas.app.data.repository

import com.google.firebase.firestore.FirebaseFirestore
import com.veritas.app.data.model.User
import com.veritas.app.util.Constants
import kotlinx.coroutines.tasks.await

class UserRepository {
    private val db = FirebaseFirestore.getInstance()

    companion object {
        private val mockUsers = listOf(
            User(id = "mock-1", name = "Alex", age = 21, gender = "Woman", college = "Stanford University", bio = "Love hiking and coffee", isVerified = true, isApproved = true, onboardingComplete = true),
            User(id = "mock-2", name = "Jordan", age = 22, gender = "Man", college = "Stanford University", bio = "CS major, jazz pianist", isVerified = true, isApproved = true, onboardingComplete = true),
            User(id = "mock-3", name = "Casey", age = 20, gender = "Non-binary", college = "Stanford University", bio = "Art history nerd", isVerified = true, isApproved = true, onboardingComplete = true),
            User(id = "mock-4", name = "Morgan", age = 23, gender = "Woman", college = "Stanford University", bio = "Basketball & photography", isVerified = true, isApproved = true, onboardingComplete = true),
            User(id = "mock-5", name = "Taylor", age = 21, gender = "Man", college = "Stanford University", bio = "Film buff, let's chat", isVerified = true, isApproved = true, onboardingComplete = true),
            User(id = "mock-6", name = "Riley", age = 22, gender = "Woman", college = "Stanford University", bio = "Bio major, dog mom", isVerified = true, isApproved = true, onboardingComplete = true),
            User(id = "mock-7", name = "Avery", age = 20, gender = "Man", college = "Stanford University", bio = "Philosophy & surfing", isVerified = true, isApproved = true, onboardingComplete = true),
            User(id = "mock-8", name = "Quinn", age = 23, gender = "Non-binary", college = "Stanford University", bio = "Music producer", isVerified = true, isApproved = true, onboardingComplete = true),
            User(id = "mock-9", name = "Sam", age = 21, gender = "Man", college = "Stanford University", bio = "Econ major, chess club", isVerified = true, isApproved = true, onboardingComplete = true),
            User(id = "mock-10", name = "Blake", age = 22, gender = "Woman", college = "Stanford University", bio = "Theater kid at heart", isVerified = true, isApproved = true, onboardingComplete = true),
        )
    }

    suspend fun getUsersForSwipe(excludeIds: List<String>, college: String): Result<List<User>> = runCatching {
        try {
            val snapshot = db.collection(Constants.COLLECTION_USERS)
                .whereEqualTo("college", college)
                .whereEqualTo("isApproved", true)
                .whereEqualTo("onboardingComplete", true)
                .limit(50)
                .get()
                .await()
            snapshot.documents
                .filter { it.id !in excludeIds }
                .mapNotNull { it.toObject(User::class.java)?.copy(id = it.id) }
        } catch (e: Exception) {
            mockUsers.filter { it.id !in excludeIds }.map { it.copy(college = college) }
        }
    }

    suspend fun getUserById(userId: String): Result<User?> = runCatching {
        try {
            val doc = db.collection(Constants.COLLECTION_USERS).document(userId).get().await()
            doc.toObject(User::class.java)?.copy(id = doc.id)
        } catch (e: Exception) {
            mockUsers.find { it.id == userId }
        }
    }

    suspend fun getUnapprovedUsers(): Result<List<User>> = runCatching {
        try {
            val snapshot = db.collection(Constants.COLLECTION_USERS)
                .whereEqualTo("isApproved", false)
                .whereEqualTo("onboardingComplete", true)
                .get()
                .await()
            snapshot.documents.mapNotNull { it.toObject(User::class.java)?.copy(id = it.id) }
        } catch (e: Exception) {
            emptyList()
        }
    }

    suspend fun approveUser(userId: String): Result<Unit> = runCatching {
        try {
            db.collection(Constants.COLLECTION_USERS).document(userId)
                .update("isApproved", true).await()
        } catch (e: Exception) {
            // dev mode: no-op
        }
    }

    suspend fun deleteUser(userId: String): Result<Unit> = runCatching {
        try {
            db.collection(Constants.COLLECTION_USERS).document(userId).delete().await()
        } catch (e: Exception) {
            // dev mode: no-op
        }
    }
}
