package com.theplaybook.app.domain.model

data class Module(
    val id: Long,
    val courseId: Long,
    val title: String,
    val summary: String,
    val orderIndex: Int,
    val lessonCount: Int
)
