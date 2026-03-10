package io.zenable.gradle.tasks

import org.gradle.api.DefaultTask
import org.gradle.api.GradleException
import org.gradle.api.provider.Property
import org.gradle.api.tasks.Input
import org.gradle.api.tasks.Optional
import org.gradle.api.tasks.TaskAction
import java.io.File

/**
 * Runs Zenable verification and fails the build if violations exceed threshold.
 *
 * This task is designed to be wired into the `check` lifecycle task.
 */
abstract class ZenableVerifyTask : DefaultTask() {

    @get:Input
    abstract val enabled: Property<Boolean>

    @get:Input
    abstract val mode: Property<String>

    @get:Input
    abstract val failOnSeverity: Property<String>

    @get:Input
    @get:Optional
    abstract val cliPath: Property<String>

    @TaskAction
    fun verify() {
        if (!enabled.getOrElse(true)) {
            logger.lifecycle("Zenable verification is disabled, skipping")
            return
        }

        val cli = resolveCliPath()
        if (cli == null) {
            logger.warn("Zenable CLI not found on PATH; skipping verification")
            return
        }

        val reportDir = File(project.layout.buildDirectory.asFile.get(), "reports/zenable")
        reportDir.mkdirs()

        val args = mutableListOf(
            cli,
            "check",
            "--source-dir", project.projectDir.absolutePath,
            "--output-format", "sarif",
            "--output", File(reportDir, "verify.sarif").absolutePath,
            "--build-tool", "gradle",
            "--mode", mode.getOrElse("balanced"),
            "--fail-on-severity", failOnSeverity.getOrElse("high"),
        )

        logger.lifecycle("Running Zenable verification...")
        val result = project.exec { spec ->
            spec.commandLine(args)
            spec.isIgnoreExitValue = true
        }

        if (result.exitValue != 0) {
            throw GradleException(
                "Zenable verification failed (exit code ${result.exitValue}). " +
                "See report: ${reportDir.absolutePath}"
            )
        }

        logger.lifecycle("Zenable verification passed.")
    }

    private fun resolveCliPath(): String? {
        val explicit = cliPath.orNull
        if (!explicit.isNullOrBlank()) {
            return explicit
        }
        return System.getenv("PATH")?.split(File.pathSeparator)
            ?.map { File(it, "zenable") }
            ?.firstOrNull { it.exists() && it.canExecute() }
            ?.absolutePath
    }
}
