#!/bin/bash
# Generate Gradle wrapper for Veritas Android project
# Requires JDK 17+

# Use the project-root gradle.properties to set wrapper version
cat > /tmp/gradle-init-script.gradle << 'EOF'
gradle.wrapper.gradleVersion=8.5
EOF

java -Dorg.gradle.appname=gradlew -Dorg.gradle.wrapper.version=8.5 \
  -classpath "$HOME/.gradle/wrapper/dists/*/gradle-wrapper-*.jar" \
  org.gradle.wrapper.GradleWrapperMain wrapper --gradle-version=8.5
EOF
