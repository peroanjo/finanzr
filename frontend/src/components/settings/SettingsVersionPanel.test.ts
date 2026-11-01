import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { i18n } from "../../i18n";
import SettingsVersionPanel from "./SettingsVersionPanel.vue";
import { api } from "../../api/client";

vi.mock("../../api/client", () => ({ api: vi.fn() }));
const mockApi = vi.mocked(api);
const response = {
  installed_version: "1.0.0",
  installed_commit: null,
  comparison_basis: "version_tag",
  repository_url: "https://github.com/example/synthetic",
  checked_at: "2026-01-01T12:00:00Z",
  release_status: "available",
  release_update: "available",
  latest_release: "v2.0.0-alpha.1",
  main: {
    status: "ahead",
    ahead_by: 2,
    behind_by: 0,
    url: "https://github.com/example/synthetic/compare/v1...main",
    commits: [
      {
        sha: "a".repeat(40),
        message: "Synthetic commit",
        url: "https://github.com/example/synthetic/commit/aaa",
      },
    ],
  },
  releases: [
    {
      tag: "v2.0.0-alpha.1",
      name: "Synthetic release",
      published_at: "2026-01-01T12:00:00Z",
      prerelease: true,
      notes: "# Changes\n<script>alert('synthetic')</script>",
      url: "https://github.com/example/synthetic/releases/tag/v2",
    },
  ],
};
function render() {
  return mount(SettingsVersionPanel, { global: { plugins: [i18n] } });
}

describe("SettingsVersionPanel", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    i18n.global.locale.value = "es-ES";
  });
  it("shows release notes as text, build uncertainty and separate main commits", async () => {
    mockApi.mockResolvedValue(response);
    const wrapper = render();
    await flushPromises();
    expect(mockApi).toHaveBeenCalledWith("/installation/version");
    expect(wrapper.text()).toContain(
      "Hay una nueva versión publicada disponible",
    );
    expect(wrapper.text()).toContain("2 commits nuevos");
    expect(wrapper.text()).toContain("Commit de compilación no disponible");
    expect(wrapper.text()).toContain("Preliminar");
    expect(wrapper.text()).toContain("Última versión publicada en main");
    expect(wrapper.text()).toContain("<script>");
    expect(wrapper.find("script").exists()).toBe(false);
    expect(wrapper.find("details").attributes("open")).toBeDefined();
    await wrapper.find("button").trigger("click");
    await flushPromises();
    expect(mockApi).toHaveBeenCalledTimes(2);
  });
  it("can retry a failed request", async () => {
    mockApi.mockRejectedValueOnce(new Error("unavailable"));
    const wrapper = render();
    await flushPromises();
    expect(wrapper.find('[role="alert"]').exists()).toBe(true);
    mockApi.mockResolvedValue({
      ...response,
      releases: [],
      release_update: "unknown",
      main: null,
    });
    await wrapper.find("button").trigger("click");
    await flushPromises();
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    expect(wrapper.text()).toContain("No se puede determinar");
    expect(wrapper.text()).toContain("No se puede comparar");
    expect(wrapper.text()).toContain("No se han encontrado versiones");
  });
});
