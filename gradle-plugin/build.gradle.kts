plugins {
    `java-gradle-plugin`
    `maven-publish`
    kotlin("jvm") version "1.9.22"
    id("com.gradle.plugin-publish") version "1.2.1"
}

group = "io.zenable.gradle"
version = "0.1.0"

repositories {
    mavenCentral()
    gradlePluginPortal()
}

dependencies {
    implementation(kotlin("stdlib"))
    testImplementation(kotlin("test"))
    testImplementation("org.junit.jupiter:junit-jupiter:5.10.2")
}

tasks.test {
    useJUnitPlatform()
}

gradlePlugin {
    website.set("https://zenable.io")
    vcsUrl.set("https://github.com/Zenable-io/ai-guardrails")
    plugins {
        create("zenable") {
            id = "io.zenable.gradle"
            implementationClass = "io.zenable.gradle.ZenablePlugin"
            displayName = "Zenable Guardrails"
            description = "AI guardrails for Gradle builds"
            tags.set(listOf("security", "compliance", "guardrails", "ai"))
        }
        create("zenableInit") {
            id = "io.zenable.gradle.init"
            implementationClass = "io.zenable.gradle.ZenableInitPlugin"
            displayName = "Zenable Guardrails (Init)"
            description = "Init plugin for global Zenable integration"
        }
    }
}
