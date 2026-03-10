package io.zenable.gradle.tasks

import org.gradle.api.DefaultTask
import org.gradle.api.provider.Property
import org.gradle.api.tasks.Input
import org.gradle.api.tasks.Optional
import org.gradle.api.tasks.TaskAction
import java.io.File

/**
 * Runs Zenable analysis on the project without failing the build.
 *
 * Reports are written to build/reports/zenable/.
 */
abstract class ZenableAnalyzeTask : DefaultTask() {

    @get:Input
    abstract val enabled: Property<Boolean>

    @get:Input
    abstract val mode: Property<String>

    @get:Input
    @get:Optional
    abstract val cliPath: Property<String>

    @TaskAction
    fun analyze() {
        if (!enabled.getOrElse(true)) {
            logger.lifecycle("Zenable analysis is disabled, skipping")
            return
        }

        val cli = resolveCliPath()
        if (cli == null) {
            logger.warn("Zenable CLI not found on PATH; skipping analysis")
            return
        }

        val reportDir = File(project.layout.buildDirectory.asFile.get(), "reports/zenable")
        reportDir.mkdirs()

        val args = mutableListOf(
            cli,
            "check",
            "--source-dir", project.projectDir.absolutePath,
            "--output-format", "sarif",
            "--output", File(reportDir, "analysis.sarif").absolutePath,
            "--build-tool", "gradle",
            "--mode", mode.getOrElse("balanced"),
        )

        logger.lifecycle("Running Zenable analysis...")
        val result = project.exec { spec ->
            spec.commandLine(args)
            spec.isIgnoreExitValue = true
        }

        if (result.exitValue != 0) {
            logger.warn("Zenable analysis exited with code ${result.exitValue}")
        } else {
            logger.lifecycle("Zenable analysis complete. Report: ${reportDir.absolutePath}")
        }
    }

    private fun resolveCliPath(): String? {
        val explicit = cliPath.orNull
        if (!explicit.isNullOrBlank()) {
            return explicit
        }
        // Search PATH
        return System.getenv("PATH")?.split(File.pathSeparator)
            ?.map { File(it, "zenable") }
            ?.firstOrNull { it.exists() && it.canExecute() }
            ?.absolutePath
    }
}
