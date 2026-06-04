package com.theplaybook.app.data.remote

import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

interface RedditApi {

    @GET("r/{subreddit}/hot.json")
    suspend fun getHotPosts(
        @Path("subreddit") subreddit: String,
        @Query("limit") limit: Int = 25
    ): RedditResponse

    @GET("r/{subreddit}/top.json")
    suspend fun getTopPosts(
        @Path("subreddit") subreddit: String,
        @Query("t") time: String = "month",
        @Query("limit") limit: Int = 25
    ): RedditResponse

    @GET("r/{subreddit}/search.json")
    suspend fun searchPosts(
        @Path("subreddit") subreddit: String,
        @Query("q") query: String,
        @Query("limit") limit: Int = 25
    ): RedditResponse
}

data class RedditResponse(
    val data: RedditData
)

data class RedditData(
    val children: List<RedditChild>,
    val after: String?
)

data class RedditChild(
    val kind: String,
    val data: RedditPost
)

data class RedditPost(
    val id: String,
    val title: String,
    val selftext: String,
    val url: String,
    val permalink: String,
    val score: Int,
    val num_comments: Int,
    val created_utc: Double,
    val author: String,
    val subreddit: String,
    val over_18: Boolean
)
