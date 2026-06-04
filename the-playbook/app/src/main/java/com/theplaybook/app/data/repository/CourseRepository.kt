package com.theplaybook.app.data.repository

import com.theplaybook.app.data.local.SeedData
import com.theplaybook.app.data.local.dao.CourseDao
import com.theplaybook.app.data.local.dao.LessonDao
import com.theplaybook.app.data.local.dao.ModuleDao
import com.theplaybook.app.data.local.entity.toDomain
import com.theplaybook.app.domain.model.Course
import com.theplaybook.app.domain.model.Lesson
import com.theplaybook.app.domain.model.Module
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class CourseRepository @Inject constructor(
    private val courseDao: CourseDao,
    private val moduleDao: ModuleDao,
    private val lessonDao: LessonDao,
) {
    fun getAllCourses(): Flow<List<Course>> {
        return courseDao.getAllCourses().map { entities ->
            entities.map { it.toDomain() }
        }
    }

    fun getCourseById(courseId: Long): Flow<Course?> {
        return courseDao.getCourseById(courseId).map { it?.toDomain() }
    }

    fun getModulesByCourse(courseId: Long): Flow<List<Module>> {
        return moduleDao.getModulesByCourse(courseId).map { entities ->
            entities.map { it.toDomain() }
        }
    }

    fun getLessonsByModule(moduleId: Long): Flow<List<Lesson>> {
        return lessonDao.getLessonsByModule(moduleId).map { entities ->
            entities.map { it.toDomain() }
        }
    }

    fun getLessonById(lessonId: Long): Flow<Lesson?> {
        return lessonDao.getLessonById(lessonId).map { it?.toDomain() }
    }

    fun getCompletedLessonCount(moduleId: Long): Flow<Int> {
        return lessonDao.getCompletedLessonCount(moduleId)
    }

    suspend fun markLessonCompleted(lessonId: Long) {
        lessonDao.updateCompletion(lessonId, true)
    }

    suspend fun seedIfEmpty() {
        val existing = courseDao.getAllCourses().first()
        if (existing.isEmpty()) {
            courseDao.insertCourses(SeedData.getCourses())
            moduleDao.insertModules(SeedData.getModules())
            lessonDao.insertLessons(SeedData.getLessons())
        }
    }
}
