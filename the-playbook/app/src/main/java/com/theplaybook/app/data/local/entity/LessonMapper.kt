package com.theplaybook.app.data.local.entity

import com.theplaybook.app.domain.model.Lesson

fun LessonEntity.toDomain() = Lesson(
    id = id,
    moduleId = moduleId,
    title = title,
    summary = summary,
    body = body,
    sourceUrl = sourceUrl,
    orderIndex = orderIndex,
    estimatedMinutes = estimatedMinutes,
    isCompleted = isCompleted
)

fun Lesson.toEntity() = LessonEntity(
    id = id,
    moduleId = moduleId,
    title = title,
    summary = summary,
    body = body,
    sourceUrl = sourceUrl,
    orderIndex = orderIndex,
    estimatedMinutes = estimatedMinutes,
    isCompleted = isCompleted
)
