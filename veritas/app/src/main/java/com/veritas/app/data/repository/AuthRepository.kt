package com.veritas.app.data.repository

import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.auth.FirebaseUser
import com.veritas.app.data.model.User
import com.google.firebase.firestore.FirebaseFirestore
import com.veritas.app.util.Constants
import kotlinx.coroutines.tasks.await

class AuthRepository {
    private val auth = FirebaseAuth.getInstance()
    private val db = FirebaseFirestore.getInstance()

    companion object {
        const val DEV_USER_ID = "dev-user-001"
        private var devUserProfile: User? = null
    }

    fun getCurrentUser(): FirebaseUser? = auth.currentUser

    suspend fun sendMagicLink(email: String): Result<Unit> = runCatching {
        try {
            val actionCodeSettings = com.google.firebase.auth.ActionCodeSettings.newBuilder()
                .setUrl("https://veritasapp.page.link/auth")
                .setHandleCodeInApp(true)
                .setAndroidPackageName("com.veritas.app", true, null)
                .build()
            auth.sendSignInLinkToEmail(email, actionCodeSettings).await()
        } catch (e: Exception) {
            throw DevModeException()
        }
    }

    suspend fun signInWithMagicLink(email: String, link: String): Result<FirebaseUser?> = runCatching {
        if (auth.isSignInWithEmailLink(link)) {
            auth.signInWithEmailLink(email, link).await()
        }
        auth.currentUser
    }

    fun isSignInWithEmailLink(link: String): Boolean {
        return auth.isSignInWithEmailLink(link)
    }

    suspend fun createUserProfile(user: User): Result<Unit> = runCatching {
        try {
            val uid = auth.currentUser?.uid ?: throw Exception("Not authenticated")
            db.collection(Constants.COLLECTION_USERS).document(uid).set(user).await()
        } catch (e: Exception) {
            if (e is DevModeException) throw e
            devUserProfile = user.copy(id = DEV_USER_ID)
        }
    }

    suspend fun getUserProfile(): Result<User?> = runCatching {
        try {
            val uid = auth.currentUser?.uid ?: return@runCatching null
            val doc = db.collection(Constants.COLLECTION_USERS).document(uid).get().await()
            doc.toObject(User::class.java)
        } catch (e: Exception) {
            devUserProfile
        }
    }

    suspend fun updateUserProfile(updates: Map<String, Any>): Result<Unit> = runCatching {
        try {
            val uid = auth.currentUser?.uid ?: throw Exception("Not authenticated")
            db.collection(Constants.COLLECTION_USERS).document(uid).update(updates).await()
        } catch (e: Exception) {
            devUserProfile = devUserProfile?.copy(
                name = updates["name"] as? String ?: devUserProfile?.name ?: ""
            )
        }
    }

    fun signOut() {
        auth.signOut()
    }

    fun getCurrentUserId(): String = try {
        auth.currentUser?.uid ?: DEV_USER_ID
    } catch (e: Exception) {
        DEV_USER_ID
    }

    class DevModeException : Exception("Dev mode")
}
