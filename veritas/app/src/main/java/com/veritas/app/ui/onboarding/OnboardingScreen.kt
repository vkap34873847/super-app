package com.veritas.app.ui.onboarding

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.veritas.app.data.colleges
import com.veritas.app.data.College
import com.veritas.app.data.model.User
import com.veritas.app.data.repository.AuthRepository
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OnboardingScreen(
    authRepo: AuthRepository,
    onComplete: () -> Unit
) {
    var name by remember { mutableStateOf("") }
    var age by remember { mutableStateOf("") }
    var selectedCollege by remember { mutableStateOf<String?>(null) }
    var collegeSearch by remember { mutableStateOf("") }
    var bio by remember { mutableStateOf("") }
    var gender by remember { mutableStateOf("") }
    var showCollegeList by remember { mutableStateOf(false) }
    var isLoading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val genders = listOf("Man", "Woman", "Non-binary", "Other")

    val filteredColleges = colleges
        .filter { it.name.contains(collegeSearch, ignoreCase = true) }
        .take(20)

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        item {
            Text(
                text = "Create your profile",
                style = MaterialTheme.typography.headlineLarge,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.padding(bottom = 8.dp)
            )
        }

        item {
            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                label = { Text("Name") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
        }

        item {
            OutlinedTextField(
                value = age,
                onValueChange = { if (it.all { c -> c.isDigit() } && it.length <= 2) age = it },
                label = { Text("Age") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
        }

        item {
            Text("Gender", style = MaterialTheme.typography.labelLarge)
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                genders.forEach { g ->
                    FilterChip(
                        selected = gender == g,
                        onClick = { gender = g },
                        label = { Text(g) }
                    )
                }
            }
        }

        item {
            OutlinedTextField(
                value = collegeSearch,
                onValueChange = {
                    collegeSearch = it
                    showCollegeList = it.isNotEmpty()
                },
                label = { Text("College") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
            if (selectedCollege != null) {
                Text(
                    text = "Selected: $selectedCollege",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.padding(top = 4.dp)
                )
            }
        }

        if (showCollegeList && selectedCollege == null) {
            items(filteredColleges) { college ->
                TextButton(
                    onClick = {
                        selectedCollege = college.name
                        collegeSearch = college.name
                        showCollegeList = false
                    },
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(college.name)
                }
            }
        }

        item {
            OutlinedTextField(
                value = bio,
                onValueChange = { bio = it },
                label = { Text("Bio") },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(120.dp),
                maxLines = 4
            )
        }

        item {
            error?.let {
                Text(
                    text = it,
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall
                )
            }
        }

        item {
            Button(
                onClick = {
                    onComplete()
                },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(52.dp),
                enabled = true
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(24.dp),
                        color = MaterialTheme.colorScheme.onPrimary
                    )
                } else {
                    Text("Complete Profile", fontSize = 16.sp)
                }
            }
        }

        item { Spacer(modifier = Modifier.height(32.dp)) }
    }
}
