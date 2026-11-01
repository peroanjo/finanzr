import { defineMessageCatalog } from "./catalog";

export const versionMessages = defineMessageCatalog(
  {
    version: {
      title: "Version",
      unknownBranch: "unknown branch",
      branchUnavailable:
        "The installed branch could not be identified. Update checks are unavailable for this build.",
      subtitle: "Releases and changes",
      installed: "Installed version",
      latest: "Latest release on {branch}",
      help: "Check published releases and development changes on {branch}. Updates are installed manually.",
      check: "Check for updates",
      loading: "Checking…",
      error:
        "GitHub is unavailable or its request limit has been reached. Try again later.",
      tagBasis:
        "Build commit unavailable. Comparisons use the installed version tag and may not reflect local changes.",
      checked: "Checked: {date}. Results are cached for one hour.",
      repository: "View repository",
      commits: "Commits on {branch}",
      newCommits:
        "{count} new commits on {branch} relative to this installation.",
      compare: "View full comparison",
      moreCommits:
        "Only part of the commit history is shown. Open the full comparison to see all changes.",
      comparisonUnavailable:
        "Cannot compare this installation with {branch}. Its commit or version tag may be unavailable on GitHub.",
      changelog: "Changelog",
      releaseLimit:
        "Up to 10 recent releases, verified as belonging to {branch}. Includes prereleases.",
      noReleases:
        "No published releases on {branch} were found among the latest releases.",
      prerelease: "Prerelease",
      noNotes: "No release notes were provided.",
      openRelease: "View release notes on GitHub",
      update: {
        available: "A newer release is available.",
        current: "This installation matches the latest release.",
        ahead: "This installation includes changes after the latest release.",
        diverged: "This installation has diverged from the latest release.",
        unknown: "Cannot determine whether a newer release is available.",
      },
      branch: {
        identical: "This installation matches {branch}.",
        behind: "This installation includes commits that are not on {branch}.",
        diverged:
          "This installation and {branch} have diverged. Review the comparison before updating.",
      },
    },
  },
  {
    version: {
      title: "Versión",
      unknownBranch: "rama desconocida",
      branchUnavailable:
        "No se ha podido identificar la rama instalada. No se pueden consultar novedades de esta compilación.",
      subtitle: "Versiones y cambios",
      installed: "Versión instalada",
      latest: "Última versión publicada en {branch}",
      help: "Consulta las versiones publicadas y los cambios de desarrollo en {branch}. Las actualizaciones se instalan manualmente.",
      check: "Buscar actualizaciones",
      loading: "Consultando…",
      error:
        "GitHub no está disponible o se ha alcanzado su límite de consultas. Inténtalo más tarde.",
      tagBasis:
        "Commit de compilación no disponible. La comparación usa la etiqueta de la versión instalada y puede no reflejar los cambios locales.",
      checked:
        "Consultado: {date}. Los resultados se guardan en caché durante una hora.",
      repository: "Ver repositorio",
      commits: "Commits en {branch}",
      newCommits:
        "Hay {count} commits nuevos en {branch} respecto a esta instalación.",
      compare: "Ver comparación completa",
      moreCommits:
        "Se muestra parte del historial de commits. Abre la comparación completa para ver todos los cambios.",
      comparisonUnavailable:
        "No se puede comparar esta instalación con {branch}. Su commit o etiqueta de versión puede no estar disponible en GitHub.",
      changelog: "Registro de cambios",
      releaseLimit:
        "Hasta 10 versiones recientes verificadas como parte de {branch}. Incluye versiones preliminares.",
      noReleases:
        "No se han encontrado versiones publicadas de {branch} entre las más recientes.",
      prerelease: "Preliminar",
      noNotes: "Esta versión no incluye notas de cambios.",
      openRelease: "Ver notas de la versión en GitHub",
      update: {
        available: "Hay una nueva versión publicada disponible.",
        current: "Esta instalación coincide con la última versión publicada.",
        ahead:
          "Esta instalación incluye cambios posteriores a la última versión publicada.",
        diverged:
          "Esta instalación ha divergido de la última versión publicada.",
        unknown: "No se puede determinar si hay una nueva versión publicada.",
      },
      branch: {
        identical: "Esta instalación coincide con {branch}.",
        behind: "Esta instalación incluye commits que no están en {branch}.",
        diverged:
          "Esta instalación y {branch} han divergido. Revisa la comparación antes de actualizar.",
      },
    },
  },
);
