package com.theplaybook.app.domain.model

data class Lesson(
    val id: Long,
    val moduleId: Long,
    val title: String,
    val summary: String,
    val body: String,
    val sourceUrl: String?,
    val orderIndex: Int,
    val estimatedMinutes: Int,
    val isCompleted: Boolean = false
)
