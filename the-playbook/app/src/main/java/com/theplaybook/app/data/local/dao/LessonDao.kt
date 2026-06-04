package com.theplaybook.app.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.theplaybook.app.data.local.entity.LessonEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface LessonDao {
    @Query("SELECT * FROM lessons WHERE module_id = :moduleId ORDER BY order_index ASC")
    fun getLessonsByModule(moduleId: Long): Flow<List<LessonEntity>>

    @Query("SELECT * FROM lessons WHERE id = :lessonId")
    fun getLessonById(lessonId: Long): Flow<LessonEntity?>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertLessons(lessons: List<LessonEntity>)

    @Query("UPDATE lessons SET is_completed = :completed WHERE id = :lessonId")
    suspend fun updateCompletion(lessonId: Long, completed: Boolean)

    @Query("DELETE FROM lessons WHERE module_id = :moduleId")
    suspend fun deleteByModule(moduleId: Long)

    @Query("SELECT COUNT(*) FROM lessons WHERE module_id = :moduleId AND is_completed = 1")
    fun getCompletedLessonCount(moduleId: Long): Flow<Int>
}
