package com.theplaybook.app.data.local.entity

import com.theplaybook.app.domain.model.Module

fun ModuleEntity.toDomain() = Module(
    id = id,
    courseId = courseId,
    title = title,
    summary = summary,
    orderIndex = orderIndex,
    lessonCount = lessonCount
)

fun Module.toEntity() = ModuleEntity(
    id = id,
    courseId = courseId,
    title = title,
    summary = summary,
    orderIndex = orderIndex,
    lessonCount = lessonCount
)
