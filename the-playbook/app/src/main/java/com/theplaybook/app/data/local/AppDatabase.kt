package com.theplaybook.app.data.local

import androidx.room.Database
import androidx.room.RoomDatabase
import com.theplaybook.app.data.local.dao.CourseDao
import com.theplaybook.app.data.local.dao.LessonDao
import com.theplaybook.app.data.local.dao.ModuleDao
import com.theplaybook.app.data.local.entity.CourseEntity
import com.theplaybook.app.data.local.entity.LessonEntity
import com.theplaybook.app.data.local.entity.ModuleEntity

@Database(
    entities = [CourseEntity::class, ModuleEntity::class, LessonEntity::class],
    version = 1,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun courseDao(): CourseDao
    abstract fun moduleDao(): ModuleDao
    abstract fun lessonDao(): LessonDao
}
