package com.theplaybook.app.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.theplaybook.app.ui.course.CourseDetailScreen
import com.theplaybook.app.ui.home.HomeScreen
import com.theplaybook.app.ui.lesson.LessonScreen
import com.theplaybook.app.ui.module.ModuleLessonsScreen
import com.theplaybook.app.ui.settings.SettingsScreen

object Routes {
    const val HOME = "home"
    const val COURSE_DETAIL = "course/{courseId}"
    const val MODULE_LESSONS = "module/{moduleId}"
    const val LESSON = "lesson/{lessonId}"
    const val SETTINGS = "settings"

    fun courseDetail(courseId: Long) = "course/$courseId"
    fun moduleLessons(moduleId: Long) = "module/$moduleId"
    fun lesson(lessonId: Long) = "lesson/$lessonId"
}

@Composable
fun NavGraph() {
    val navController = rememberNavController()

    NavHost(navController = navController, startDestination = Routes.HOME) {
        composable(Routes.HOME) {
            HomeScreen(
                onCourseClick = { courseId ->
                    navController.navigate(Routes.courseDetail(courseId))
                },
                onSettingsClick = {
                    navController.navigate(Routes.SETTINGS)
                }
            )
        }

        composable(
            route = Routes.COURSE_DETAIL,
            arguments = listOf(navArgument("courseId") { type = NavType.LongType })
        ) { backStackEntry ->
            val courseId = backStackEntry.arguments?.getLong("courseId") ?: return@composable
            CourseDetailScreen(
                courseId = courseId,
                onModuleClick = { moduleId ->
                    navController.navigate(Routes.moduleLessons(moduleId))
                },
                onBack = { navController.popBackStack() }
            )
        }

        composable(
            route = Routes.MODULE_LESSONS,
            arguments = listOf(navArgument("moduleId") { type = NavType.LongType })
        ) { backStackEntry ->
            val moduleId = backStackEntry.arguments?.getLong("moduleId") ?: return@composable
            ModuleLessonsScreen(
                moduleId = moduleId,
                onLessonClick = { lessonId ->
                    navController.navigate(Routes.lesson(lessonId))
                },
                onBack = { navController.popBackStack() }
            )
        }

        composable(
            route = Routes.LESSON,
            arguments = listOf(navArgument("lessonId") { type = NavType.LongType })
        ) { backStackEntry ->
            val lessonId = backStackEntry.arguments?.getLong("lessonId") ?: return@composable
            LessonScreen(
                lessonId = lessonId,
                onBack = { navController.popBackStack() }
            )
        }

        composable(Routes.SETTINGS) {
            SettingsScreen(onBack = { navController.popBackStack() })
        }
    }
}
