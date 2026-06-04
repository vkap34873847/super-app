package com.theplaybook.app.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.theplaybook.app.data.repository.CourseRepository
import com.theplaybook.app.domain.model.Course
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val repository: CourseRepository
) : ViewModel() {

    private val _courses = MutableStateFlow<List<Course>>(emptyList())
    val courses: StateFlow<List<Course>> = _courses.asStateFlow()

    private val _isLoading = MutableStateFlow(true)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    init {
        seedAndLoad()
    }

    private fun seedAndLoad() {
        viewModelScope.launch {
            _isLoading.value = true
            repository.seedIfEmpty()
            repository.getAllCourses().collect { courseList ->
                _courses.value = courseList
            }
            _isLoading.value = false
        }
    }
}
