package io.zenable.gradle

import org.gradle.api.provider.Property

/**
 * Configuration DSL for the Zenable Gradle plugin.
 *
 * Usage in build.gradle.kts:
 * ```
 * zenable {
 *     enabled.set(true)
 *     wireIntoCheck.set(false)
 * }
 * ```
 */
abstract class ZenableExtension {
    /** Whether the plugin is enabled. Defaults to true. */
    abstract val enabled: Property<Boolean>

    /** Wire zenableVerify into the check lifecycle task. Defaults to false. */
    abstract val wireIntoCheck: Property<Boolean>

    /** Path to the zenable CLI binary. Auto-detected if empty. */
    abstract val cliPath: Property<String>

    /** Base branch for --branch comparison. Defaults to "main". */
    abstract val baseBranch: Property<String>

    /** Skip AI review during checks. Defaults to false. */
    abstract val skipAiReview: Property<Boolean>

    /** Skip guardrails during checks. Defaults to false. */
    abstract val skipGuardrails: Property<Boolean>
}
