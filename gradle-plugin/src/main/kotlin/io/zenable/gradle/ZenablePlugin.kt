package io.zenable.gradle

import io.zenable.gradle.tasks.ZenableAnalyzeTask
import io.zenable.gradle.tasks.ZenableVerifyTask
import org.gradle.api.Plugin
import org.gradle.api.Project

/**
 * Project-level Zenable plugin.
 *
 * Registers zenableAnalyze and zenableVerify tasks, and optionally wires
 * zenableVerify into the check lifecycle task.
 */
class ZenablePlugin : Plugin<Project> {
    override fun apply(project: Project) {
        val extension = project.extensions.create("zenable", ZenableExtension::class.java)

        // Set defaults
        extension.enabled.convention(true)
        extension.mode.convention("balanced")
        extension.failOnSeverity.convention("high")
        extension.wireIntoCheck.convention(false)
        extension.cliPath.convention("")

        // Register tasks lazily
        project.tasks.register("zenableAnalyze", ZenableAnalyzeTask::class.java) { task ->
            task.description = "Run Zenable analysis"
            task.group = "verification"
            task.enabled.set(extension.enabled)
            task.mode.set(extension.mode)
            task.cliPath.set(extension.cliPath)
        }

        project.tasks.register("zenableVerify", ZenableVerifyTask::class.java) { task ->
            task.description = "Verify Zenable guardrails (blocking)"
            task.group = "verification"
            task.enabled.set(extension.enabled)
            task.mode.set(extension.mode)
            task.failOnSeverity.set(extension.failOnSeverity)
            task.cliPath.set(extension.cliPath)
        }

        // Optionally wire into check
        project.afterEvaluate {
            if (extension.wireIntoCheck.getOrElse(false)) {
                project.tasks.named("check") { task ->
                    task.dependsOn("zenableVerify")
                }
            }
        }
    }
}
