package com.theplaybook.app.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.theplaybook.app.data.local.entity.ModuleEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface ModuleDao {
    @Query("SELECT * FROM modules WHERE course_id = :courseId ORDER BY order_index ASC")
    fun getModulesByCourse(courseId: Long): Flow<List<ModuleEntity>>

    @Query("SELECT * FROM modules WHERE id = :moduleId")
    fun getModuleById(moduleId: Long): Flow<ModuleEntity?>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertModules(modules: List<ModuleEntity>)

    @Query("DELETE FROM modules WHERE course_id = :courseId")
    suspend fun deleteByCourse(courseId: Long)
}
