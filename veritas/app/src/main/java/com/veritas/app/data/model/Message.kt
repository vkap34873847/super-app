package com.veritas.app.data.model

data class Message(
    val id: String = "",
    val matchId: String = "",
    val senderId: String = "",
    val text: String = "",
    val createdAt: Long = System.currentTimeMillis()
)
