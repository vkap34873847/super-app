package com.theplaybook.app.data.remote

import com.theplaybook.app.data.local.entity.LessonEntity
import com.theplaybook.app.data.local.entity.ModuleEntity
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class RedditContentParser @Inject constructor() {

    private var lessonIdCounter = 1000L
    private var moduleIdCounter = 100L

    data class ParsedCourse(
        val title: String,
        val description: String,
        val subtitle: String,
        val modules: List<ParsedModule>
    )

    data class ParsedModule(
        val title: String,
        val summary: String,
        val orderIndex: Int,
        val lessons: List<ParsedLesson>
    )

    data class ParsedLesson(
        val title: String,
        val summary: String,
        val body: String,
        val sourceUrl: String?,
        val orderIndex: Int,
        val estimatedMinutes: Int
    )

    fun parseIntoCourse(
        posts: List<RedditPost>,
        courseId: Long,
        courseTitle: String,
        courseDescription: String,
        courseSubtitle: String
    ): ParsedCourse {
        val modules = posts.filter { it.selftext.length > 100 }
            .filterNot { it.over_18 }
            .chunked(5)
            .mapIndexed { moduleIndex, chunk ->
                ParsedModule(
                    title = "Module ${moduleIndex + 1}: ${chunk.first().title.take(40)}",
                    summary = "Lessons from r/${chunk.first().subreddit}",
                    orderIndex = moduleIndex,
                    lessons = chunk.mapIndexed { lessonIndex, post ->
                        ParsedLesson(
                            title = post.title,
                            summary = post.selftext.take(120) + "...",
                            body = formatLessonBody(post),
                            sourceUrl = "https://reddit.com${post.permalink}",
                            orderIndex = lessonIndex,
                            estimatedMinutes = calculateReadTime(post.selftext)
                        )
                    }
                )
            }
        return ParsedCourse(courseTitle, courseDescription, courseSubtitle, modules)
    }

    fun toModuleEntities(
        parsedModules: List<ParsedModule>,
        courseId: Long
    ): List<ModuleEntity> {
        return parsedModules.map { module ->
            ModuleEntity(
                id = moduleIdCounter++,
                courseId = courseId,
                title = module.title,
                summary = module.summary,
                orderIndex = module.orderIndex,
                lessonCount = module.lessons.size
            )
        }
    }

    fun toLessonEntities(
        parsedModules: List<ParsedModule>,
        moduleEntities: List<ModuleEntity>
    ): List<LessonEntity> {
        return parsedModules.flatMap { parsedModule ->
            val moduleEntity = moduleEntities.find { it.orderIndex == parsedModule.orderIndex }!!
            parsedModule.lessons.map { lesson ->
                LessonEntity(
                    id = lessonIdCounter++,
                    moduleId = moduleEntity.id,
                    title = lesson.title,
                    summary = lesson.summary,
                    body = lesson.body,
                    sourceUrl = lesson.sourceUrl,
                    orderIndex = lesson.orderIndex,
                    estimatedMinutes = lesson.estimatedMinutes,
                    isCompleted = false
                )
            }
        }
    }

    private fun formatLessonBody(post: RedditPost): String {
        val body = post.selftext
            .replace(Regex("\\[.*?\\]\\(.*?\\)"), "") // remove markdown links
            .replace(Regex("\\*\\*|\\*|__"), "")       // remove bold/italic
            .trim()
        val header = "**Source:** r/${post.subreddit} by u/${post.author}\n\n---\n\n"
        return header + body
    }

    private fun calculateReadTime(text: String): Int {
        val wordCount = text.split("\\s+".toRegex()).size
        return maxOf(2, wordCount / 200) // ~200 wpm
    }
}
