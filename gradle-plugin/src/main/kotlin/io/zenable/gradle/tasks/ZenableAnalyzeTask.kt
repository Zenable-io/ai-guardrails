package io.zenable.gradle.tasks

import org.gradle.api.DefaultTask
import org.gradle.api.provider.Property
import org.gradle.api.tasks.Input
import org.gradle.api.tasks.Optional
import org.gradle.api.tasks.TaskAction
import java.io.File

/**
 * Runs Zenable check on the project without failing the build.
 *
 * Uses `zenable check` with only real CLI flags:
 *   --branch, --base-branch, --base-path, --dry-run,
 *   --skip-ai-review, --skip-semgrep
 */
abstract class ZenableAnalyzeTask : DefaultTask() {

    @get:Input
    @get:Optional
    abstract val cliPath: Property<String>

    @get:Input
    abstract val baseBranch: Property<String>

    @get:Input
    abstract val skipAiReview: Property<Boolean>

    @get:Input
    abstract val skipGuardrails: Property<Boolean>

    @TaskAction
    fun analyze() {
        val cli = resolveCliPath()
        if (cli == null) {
            logger.warn("Zenable CLI not found on PATH; skipping analysis")
            return
        }

        val args = mutableListOf(
            cli,
            "check",
            "--base-path", project.projectDir.absolutePath,
        )

        val branch = baseBranch.getOrElse("main")
        if (branch.isNotBlank()) {
            args.addAll(listOf("--base-branch", branch))
        }

        if (skipAiReview.getOrElse(false)) {
            args.add("--skip-ai-review")
        }

        if (skipGuardrails.getOrElse(false)) {
            args.add("--skip-semgrep")
        }

        logger.lifecycle("Running Zenable analysis...")
        val result = project.exec { spec ->
            spec.commandLine(args)
            spec.isIgnoreExitValue = true
        }

        if (result.exitValue != 0) {
            logger.warn("Zenable analysis exited with code ${result.exitValue}")
        } else {
            logger.lifecycle("Zenable analysis complete.")
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
