package com.theplaybook.app.ui.course

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.theplaybook.app.data.repository.CourseRepository
import com.theplaybook.app.domain.model.Course
import com.theplaybook.app.domain.model.Module
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class CourseDetailViewModel @Inject constructor(
    private val repository: CourseRepository
) : ViewModel() {

    private val _course = MutableStateFlow<Course?>(null)
    val course: StateFlow<Course?> = _course.asStateFlow()

    private val _modules = MutableStateFlow<List<Module>>(emptyList())
    val modules: StateFlow<List<Module>> = _modules.asStateFlow()

    private val _completedCounts = MutableStateFlow<Map<Long, Int>>(emptyMap())
    val completedCounts: StateFlow<Map<Long, Int>> = _completedCounts.asStateFlow()

    fun loadCourse(courseId: Long) {
        viewModelScope.launch {
            repository.getCourseById(courseId).collect { c ->
                _course.value = c
            }
        }
        viewModelScope.launch {
            repository.getModulesByCourse(courseId).collect { m ->
                _modules.value = m
                m.forEach { module ->
                    launch {
                        repository.getCompletedLessonCount(module.id).collect { count ->
                            _completedCounts.value = _completedCounts.value + (module.id to count)
                        }
                    }
                }
            }
        }
    }
}
