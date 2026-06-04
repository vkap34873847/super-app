package com.veritas.app.navigation

import android.content.Intent
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.google.firebase.auth.FirebaseAuth
import com.veritas.app.data.repository.AuthRepository
import com.veritas.app.data.repository.ChatRepository
import com.veritas.app.data.repository.MatchRepository
import com.veritas.app.data.repository.UserRepository
import com.veritas.app.ui.admin.AdminScreen
import com.veritas.app.ui.auth.AuthScreen
import com.veritas.app.ui.chat.ChatListScreen
import com.veritas.app.ui.chat.ChatScreen
import com.veritas.app.ui.matches.MatchesScreen
import com.veritas.app.ui.onboarding.OnboardingScreen
import com.veritas.app.ui.profile.ProfileScreen
import com.veritas.app.ui.swipe.SwipeScreen
import kotlinx.coroutines.launch

@Composable
fun NavGraph(intent: Intent?) {
    val navController = rememberNavController()
    val authRepo = AuthRepository()
    val userRepo = UserRepository()
    val matchRepo = MatchRepository()
    val chatRepo = ChatRepository()

    val scope = rememberCoroutineScope()
    val currentUser = FirebaseAuth.getInstance().currentUser
    val startDestination = when {
        currentUser == null -> Screen.Auth.route
        intent?.data != null && authRepo.isSignInWithEmailLink(intent.data.toString()) -> Screen.Auth.route
        else -> Screen.Swipe.route
    }

    intent?.data?.let { link ->
        if (authRepo.isSignInWithEmailLink(link.toString())) {
            val email = intent.getStringExtra("email")
            if (email != null) {
                scope.launch {
                    authRepo.signInWithMagicLink(email, link.toString())
                }
            }
        }
    }

    NavHost(navController = navController, startDestination = startDestination) {
        composable(Screen.Auth.route) {
            AuthScreen(
                authRepo = authRepo,
                onAuthSuccess = { isNewUser ->
                    if (isNewUser) navController.navigate(Screen.Onboarding.route) {
                        popUpTo(Screen.Auth.route) { inclusive = true }
                    } else {
                        navController.navigate(Screen.Swipe.route) {
                            popUpTo(Screen.Auth.route) { inclusive = true }
                        }
                    }
                }
            )
        }

        composable(Screen.Onboarding.route) {
            OnboardingScreen(
                authRepo = authRepo,
                onComplete = {
                    navController.navigate(Screen.Swipe.route) {
                        popUpTo(Screen.Onboarding.route) { inclusive = true }
                    }
                }
            )
        }

        composable(Screen.Swipe.route) {
            SwipeScreen(
                userRepo = userRepo,
                matchRepo = matchRepo,
                authRepo = authRepo,
                onOpenMatches = { navController.navigate(Screen.Matches.route) },
                onOpenProfile = { navController.navigate(Screen.Profile.route) }
            )
        }

        composable(Screen.Matches.route) {
            MatchesScreen(
                authRepo = authRepo,
                userRepo = userRepo,
                onChat = { matchId, otherUserId ->
                    navController.navigate(Screen.Chat.createRoute(matchId, otherUserId))
                },
                onBack = { navController.popBackStack() }
            )
        }

        composable(
            Screen.Chat.route,
            arguments = listOf(
                navArgument("matchId") { type = NavType.StringType },
                navArgument("otherUserId") { type = NavType.StringType }
            )
        ) { backStackEntry ->
            val matchId = backStackEntry.arguments?.getString("matchId") ?: ""
            val otherUserId = backStackEntry.arguments?.getString("otherUserId") ?: ""
            ChatScreen(
                matchId = matchId,
                otherUserId = otherUserId,
                chatRepo = chatRepo,
                authRepo = authRepo,
                userRepo = userRepo,
                onBack = { navController.popBackStack() }
            )
        }

        composable(Screen.Profile.route) {
            ProfileScreen(
                authRepo = authRepo,
                userRepo = userRepo,
                onLogout = {
                    authRepo.signOut()
                    navController.navigate(Screen.Auth.route) {
                        popUpTo(0) { inclusive = true }
                    }
                },
                onBack = { navController.popBackStack() }
            )
        }

        composable(Screen.Admin.route) {
            AdminScreen(
                userRepo = userRepo,
                onBack = { navController.popBackStack() }
            )
        }
    }
}
