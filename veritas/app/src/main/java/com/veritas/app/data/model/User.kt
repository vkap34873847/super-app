package com.veritas.app.data.model

data class User(
    val id: String = "",
    val email: String = "",
    val name: String = "",
    val college: String = "",
    val collegeDomain: String = "",
    val year: String = "",
    val major: String = "",
    val bio: String = "",
    val gender: String = "",
    val interestedIn: List<String> = emptyList(),
    val photos: List<String> = emptyList(),
    val isVerified: Boolean = false,
    val isApproved: Boolean = false,
    val onboardingComplete: Boolean = false,
    val age: Int = 18,
    val fcmToken: String = "",
    val createdAt: Long = System.currentTimeMillis()
)
