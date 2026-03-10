package io.zenable.gradle

import org.gradle.api.Plugin
import org.gradle.api.initialization.Settings
import org.gradle.api.invocation.Gradle

/**
 * Init-script plugin applied at the Gradle level.
 *
 * Used by the global init script installed via `zenable install gradle`.
 * The init script handles marker-file gating (.zenable or zenable.yaml),
 * so this plugin simply applies ZenablePlugin to all projects.
 */
class ZenableInitPlugin : Plugin<Gradle> {
    override fun apply(gradle: Gradle) {
        gradle.allprojects { project ->
            project.pluginManager.apply(ZenablePlugin::class.java)
        }
    }
}
