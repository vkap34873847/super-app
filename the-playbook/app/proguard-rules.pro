# Add project specific ProGuard rules here.
-keepattributes Signature
-keepattributes *Annotation*

# Retrofit
-dontwarn retrofit2.**
-keep class retrofit2.** { *; }

# Gson
-keepattributes Signature
-keep class com.theplaybook.app.data.** { *; }

# Room
-keep class * extends androidx.room.RoomDatabase
