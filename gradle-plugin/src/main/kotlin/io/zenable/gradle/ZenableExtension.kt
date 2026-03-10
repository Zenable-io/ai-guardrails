package io.zenable.gradle

import org.gradle.api.provider.Property

/**
 * Configuration DSL for the Zenable Gradle plugin.
 *
 * Usage in build.gradle.kts:
 * ```
 * zenable {
 *     enabled.set(true)
 *     mode.set("balanced")
 *     failOnSeverity.set("high")
 *     wireIntoCheck.set(false)
 * }
 * ```
 */
abstract class ZenableExtension {
    /** Whether the plugin is enabled. Defaults to true. */
    abstract val enabled: Property<Boolean>

    /** Analysis mode: "balanced", "strict", etc. Defaults to "balanced". */
    abstract val mode: Property<String>

    /** Minimum severity to fail the build: "high", "medium", "low". Defaults to "high". */
    abstract val failOnSeverity: Property<String>

    /** Wire zenableVerify into the check lifecycle task. Defaults to false. */
    abstract val wireIntoCheck: Property<Boolean>

    /** Path to the zenable CLI binary. Auto-detected if empty. */
    abstract val cliPath: Property<String>
}
