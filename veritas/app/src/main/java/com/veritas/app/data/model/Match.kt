package com.veritas.app.data.model

data class Match(
    val id: String = "",
    val user1Id: String = "",
    val user2Id: String = "",
    val createdAt: Long = System.currentTimeMillis(),
    val lastMessageAt: Long = 0,
    val lastMessageText: String = ""
)
