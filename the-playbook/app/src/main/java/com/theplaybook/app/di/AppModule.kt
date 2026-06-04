package com.theplaybook.app.di

import android.content.Context
import androidx.room.Room
import com.theplaybook.app.data.local.AppDatabase
import com.theplaybook.app.data.local.dao.CourseDao
import com.theplaybook.app.data.local.dao.LessonDao
import com.theplaybook.app.data.local.dao.ModuleDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): AppDatabase {
        return Room.databaseBuilder(
            context,
            AppDatabase::class.java,
            "the_playbook_db"
        ).fallbackToDestructiveMigration().build()
    }

    @Provides
    fun provideCourseDao(db: AppDatabase): CourseDao = db.courseDao()

    @Provides
    fun provideModuleDao(db: AppDatabase): ModuleDao = db.moduleDao()

    @Provides
    fun provideLessonDao(db: AppDatabase): LessonDao = db.lessonDao()
}
