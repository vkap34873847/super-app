package com.theplaybook.app.data.local.entity

import com.theplaybook.app.domain.model.Course

fun CourseEntity.toDomain() = Course(
    id = id,
    title = title,
    description = description,
    subtitle = subtitle,
    iconRes = iconRes,
    moduleCount = moduleCount,
    lessonCount = lessonCount,
    estimatedMinutes = estimatedMinutes,
    color = color
)

fun Course.toEntity() = CourseEntity(
    id = id,
    title = title,
    description = description,
    subtitle = subtitle,
    iconRes = iconRes,
    moduleCount = moduleCount,
    lessonCount = lessonCount,
    estimatedMinutes = estimatedMinutes,
    color = color
)
