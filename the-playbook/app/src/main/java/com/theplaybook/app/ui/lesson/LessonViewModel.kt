package com.theplaybook.app.ui.lesson

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.theplaybook.app.data.repository.CourseRepository
import com.theplaybook.app.domain.model.Lesson
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class LessonViewModel @Inject constructor(
    private val repository: CourseRepository
) : ViewModel() {

    private val _lesson = MutableStateFlow<Lesson?>(null)
    val lesson: StateFlow<Lesson?> = _lesson.asStateFlow()

    fun loadLesson(lessonId: Long) {
        viewModelScope.launch {
            repository.getLessonById(lessonId).collect { l ->
                _lesson.value = l
            }
        }
    }

    fun markComplete(lessonId: Long) {
        viewModelScope.launch {
            repository.markLessonCompleted(lessonId)
        }
    }
}
