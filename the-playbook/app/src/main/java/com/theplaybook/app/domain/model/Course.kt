package com.theplaybook.app.domain.model

data class Course(
    val id: Long,
    val title: String,
    val description: String,
    val subtitle: String,
    val iconRes: Int,
    val moduleCount: Int,
    val lessonCount: Int,
    val estimatedMinutes: Int,
    val color: Long
)
