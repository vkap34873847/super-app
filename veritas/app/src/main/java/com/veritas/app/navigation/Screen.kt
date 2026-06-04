package com.veritas.app.navigation

sealed class Screen(val route: String) {
    data object Auth : Screen("auth")
    data object Onboarding : Screen("onboarding")
    data object Swipe : Screen("swipe")
    data object Matches : Screen("matches")
    data object ChatList : Screen("chat_list")
    data object Chat : Screen("chat/{matchId}/{otherUserId}") {
        fun createRoute(matchId: String, otherUserId: String) = "chat/$matchId/$otherUserId"
    }
    data object Profile : Screen("profile")
    data object Admin : Screen("admin")
}
