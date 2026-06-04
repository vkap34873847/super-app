package com.theplaybook.app.ui.module

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.theplaybook.app.data.repository.CourseRepository
import com.theplaybook.app.domain.model.Lesson
import com.theplaybook.app.domain.model.Module
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class ModuleLessonsViewModel @Inject constructor(
    private val repository: CourseRepository
) : ViewModel() {

    private val _module = MutableStateFlow<Module?>(null)
    val module: StateFlow<Module?> = _module.asStateFlow()

    private val _lessons = MutableStateFlow<List<Lesson>>(emptyList())
    val lessons: StateFlow<List<Lesson>> = _lessons.asStateFlow()

    fun loadModule(moduleId: Long) {
        viewModelScope.launch {
            repository.getLessonsByModule(moduleId).collect { lessonList ->
                _lessons.value = lessonList
            }
        }
    }
}
