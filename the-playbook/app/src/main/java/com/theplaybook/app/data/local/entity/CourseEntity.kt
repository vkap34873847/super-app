package com.theplaybook.app.data.local.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "courses")
data class CourseEntity(
    @PrimaryKey val id: Long,
    val title: String,
    val description: String,
    val subtitle: String,
    @ColumnInfo(name = "icon_res") val iconRes: Int,
    @ColumnInfo(name = "module_count") val moduleCount: Int,
    @ColumnInfo(name = "lesson_count") val lessonCount: Int,
    @ColumnInfo(name = "estimated_minutes") val estimatedMinutes: Int,
    val color: Long
)
