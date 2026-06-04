-keepattributes Signature
-keepattributes *Annotation*

-keep class com.veritas.app.data.model.** { *; }

-keep class com.google.firebase.** { *; }
-dontwarn com.google.firebase.**
