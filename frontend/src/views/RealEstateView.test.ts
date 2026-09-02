import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import { applyLocale, registerMessages } from "../i18n";
import { viewMessagesA } from "../i18n/viewMessagesA";
import { realEstateMessages } from "../i18n/realEstateMessages";
import { useSessionStore } from "../stores/session";
import RealEstateView from "./RealEstateView.vue";

registerMessages(viewMessagesA);
registerMessages(realEstateMessages);

vi.mock("../api/client", () => ({
  api: vi.fn(),
  json: (method: string, body: unknown) => ({
    method,
    body: JSON.stringify(body),
  }),
}));

const apiMock = vi.mocked(api);
const projects = [
  {
    id: "11111111-1111-4111-8111-111111111111",
    name: "Málaga Centro",
    platform: "Urbanitae",
    status: "active",
    initial_capital: 1000,
    new_capital: 1000,
    returned_capital: 0,
    realized_profit: 100,
    expected_profit: 200,
    expected_irr_percent: 12,
    expected_term_months: 24,
    start_date: "2025-09-01",
    maturity_date: "2027-09-01",
    return_date: null,
    movements: [],
    origin: "",
  },
  {
    id: "22222222-2222-4222-8222-222222222222",
    name: "Barcelona",
    platform: "WeCity",
    status: "active",
    initial_capital: 1500,
    new_capital: 0,
    returned_capital: 500,
    realized_profit: 50,
    expected_profit: null,
    expected_irr_percent: 10,
    expected_term_months: 12,
    start_date: "2025-09-01",
    maturity_date: "2027-03-01",
    return_date: "2026-06-22",
    movements: [
      {
        id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        flow_type: "capital_return",
        effective_date: "2026-06-22",
        amount: 500,
        note: "Amortización parcial",
      },
      {
        id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        flow_type: "profit",
        effective_date: "2026-06-22",
        amount: 50,
        note: "Intereses ordinarios",
      },
    ],
    origin: "Reinversión de un proyecto anterior",
  },
];
const completedProject = {
  ...projects[0],
  id: "33333333-3333-4333-8333-333333333333",
  name: "Valencia Finalizado",
  status: "completed",
  returned_capital: 1000,
  maturity_date: "2027-12-31",
};
const returnedRiskProject = {
  ...projects[0],
  id: "44444444-4444-4444-8444-444444444444",
  name: "Riesgo devuelto",
  status: "defaulted",
  returned_capital: 1000,
  maturity_date: "2027-11-30",
};

describe("RealEstateView", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    useSessionStore().user = {
      id: "user-1",
      email: "user@finanzr.local",
      display_name: "User",
      role: "user",
      language: "es-ES",
      preferred_language: "es-ES",
      default_language: "es-ES",
      default_crowdfunding_tax_rate: 19,
      active_workspace_id: "workspace-1",
      workspaces: [
        {
          id: "workspace-1",
          name: "Personal",
          slug: "personal",
          base_currency: "EUR",
          role: "owner",
        },
      ],
    };
    applyLocale("es-ES");
    HTMLDialogElement.prototype.showModal = vi.fn(function (
      this: HTMLDialogElement,
    ) {
      this.setAttribute("open", "");
    });
    HTMLDialogElement.prototype.close = vi.fn(function (
      this: HTMLDialogElement,
    ) {
      this.removeAttribute("open");
    });
    apiMock.mockImplementation(async (path) => {
      if (path === "/real-estate") return projects;
      throw new Error(`Unexpected path: ${path}`);
    });
  });

  it("calculates net amounts with a custom project rate and the session default", async () => {
    const customProjects = [
      {
        ...projects[0],
        tax_rate: 0, // 0% tax -> 100 gross = 100 net, 200 expected gross = 200 expected net
      },
      {
        ...projects[1],
        tax_rate: 10, // 10% tax -> 50 gross = 45 net, 100 expected gross = 90 expected net
      },
    ];
    apiMock.mockResolvedValue(customProjects);
    const wrapper = mount(RealEstateView);
    await flushPromises();

    // Project 1: net profit 100 (0% of 100), Project 2: net profit 45 (10% of 50) => Total net = 145.00
    expect(wrapper.get(".general-kpis").text()).toContain("+145,00");
    // Project 1: expected net 200, Project 2: expected net 90 => Total expected net = 290.00
    expect(wrapper.get(".general-kpis").text()).toContain("+290,00");
  });

  it("shows overall KPIs, maturities, and project metrics", async () => {
    const wrapper = mount(RealEstateView);
    await flushPromises();

    expect(wrapper.text()).toContain("Capital trabajando sobre plano");
    expect(wrapper.text()).toContain("Proyectos de crowdfunding");
    expect(wrapper.get(".live-capital").text()).toContain("2000,00");
    expect(wrapper.get(".general-kpis").text()).toContain("1000,00");
    expect(wrapper.get(".general-kpis").text()).toContain("+121,50");
    expect(wrapper.get(".general-kpis").text()).toContain("+243,00");
    expect(wrapper.get(".general-kpis").text()).toContain(
      "Neto tras retenciones",
    );
    expect(wrapper.get(".general-kpis").text()).not.toContain("19 %");
    expect(wrapper.get(".general-kpis").text()).toMatch(/11\s%/);
    expect(wrapper.get(".maturity-strip").text()).toContain("Barcelona");
    expect(wrapper.findAll(".project-card")).toHaveLength(2);
    expect(wrapper.findAll(".project-card")[1].text()).toContain(
      "Reinversión de un proyecto anterior",
    );
  });

  it("uses API-calculated net amounts to preserve the historical rate", async () => {
    apiMock.mockResolvedValue([
      {
        ...projects[0],
        tax_rate: 30,
        net_realized_profit: 81,
        net_expected_profit: 162,
      },
    ]);
    const wrapper = mount(RealEstateView);
    await flushPromises();

    expect(wrapper.get(".general-kpis").text()).toContain("+81,00");
    expect(wrapper.get(".general-kpis").text()).toContain("+162,00");
    expect(wrapper.get(".project-card").text()).toContain("81,00");
  });

  it("opens the creation flow from the primary action", async () => {
    const wrapper = mount(RealEstateView);
    await flushPromises();

    await wrapper.get(".add-project").trigger("click");

    expect(wrapper.get(".estate-dialog").attributes("open")).toBeDefined();
    expect(wrapper.get(".estate-dialog").text()).toContain("Nueva inversión");
  });

  it("edits returns and profits as dated movements", async () => {
    apiMock.mockImplementation(async (path, options) => {
      if (path === "/real-estate" && !options) return projects;
      if (path === "/real-estate/22222222-2222-4222-8222-222222222222")
        return projects[1];
      throw new Error(`Unexpected path: ${path}`);
    });
    const wrapper = mount(RealEstateView);
    await flushPromises();

    await wrapper.findAll(".project-actions button")[1].trigger("click");

    expect(wrapper.findAll(".movement-row")).toHaveLength(2);
    expect(
      wrapper.findAll<HTMLInputElement>(".movement-note input")[0].element
        .value,
    ).toBe("Amortización parcial");
    await wrapper.findAll(".movement-editor header button")[1].trigger("click");
    expect(wrapper.findAll(".movement-row")).toHaveLength(3);
    await wrapper.get(".estate-dialog form").trigger("submit");
    await flushPromises();

    const request = apiMock.mock.calls.find(
      ([path]) => path === "/real-estate/22222222-2222-4222-8222-222222222222",
    );
    const movements = JSON.parse(String(request?.[1]?.body)).movements;
    expect(movements).toHaveLength(3);
    expect(movements[0].id).toBe("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa");
  });

  it("preserves a movement without an effective date when editing", async () => {
    const undatedProject = {
      ...projects[1],
      movements: [
        {
          ...projects[1].movements[1],
          effective_date: null,
        },
      ],
    };
    apiMock.mockImplementation(async (path, options) => {
      if (path === "/real-estate" && !options) return [undatedProject];
      if (path === `/real-estate/${undatedProject.id}`) return undatedProject;
      throw new Error(`Unexpected path: ${path}`);
    });
    const wrapper = mount(RealEstateView);
    await flushPromises();

    await wrapper.get(".project-actions button").trigger("click");
    expect(
      wrapper.get<HTMLInputElement>('.movement-row input[type="date"]').element
        .value,
    ).toBe("");
    await wrapper.get(".estate-dialog form").trigger("submit");
    await flushPromises();

    const request = apiMock.mock.calls
      .filter(
        ([path, options]) =>
          path === `/real-estate/${undatedProject.id}` && options,
      )
      .at(-1);
    expect(
      JSON.parse(String(request?.[1]?.body)).movements[0].effective_date,
    ).toBeNull();
  });

  it("translates statuses, actions, and formats into English", async () => {
    applyLocale("en");
    const wrapper = mount(RealEstateView);
    await flushPromises();

    expect(wrapper.text()).toContain("Capital at work before completion");
    expect(wrapper.text()).toContain("Crowdfunding projects");
    expect(wrapper.get(".live-capital").text()).toContain("€2,000.00");
    expect(wrapper.findAll(".status")[0].text()).toBe("Active");
    expect(wrapper.get(".add-project").text()).toContain("New investment");
  });

  it("separates completed projects into a collapsed section with full progress", async () => {
    apiMock.mockResolvedValue([...projects, completedProject]);
    const wrapper = mount(RealEstateView);
    await flushPromises();

    const activeGrid = wrapper.get(".project-grid--active");
    const completed = wrapper.get("details.completed-projects");

    expect(activeGrid.text()).not.toContain("Valencia Finalizado");
    expect(activeGrid.findAll(".project-card")).toHaveLength(2);
    expect(completed.attributes("open")).toBeUndefined();
    expect(completed.get("summary").text()).toContain("Proyectos completados");
    expect(completed.get("summary").text()).toContain("1 completado");
    expect(completed.get(".project-progress").text()).toContain("Completado");
    expect(completed.get(".progress-track").attributes("aria-valuenow")).toBe(
      "100",
    );
    expect(completed.get(".progress-track i").attributes("style")).toContain(
      "width: 100%",
    );
  });

  it("allows opening completed projects and editing one of them", async () => {
    apiMock.mockResolvedValue([...projects, completedProject]);
    const wrapper = mount(RealEstateView);
    await flushPromises();

    const completed = wrapper.get("details.completed-projects");
    await completed.get("summary").trigger("click");

    expect(completed.attributes("open")).toBeDefined();
    await completed.get(".project-actions button").trigger("click");
    expect(wrapper.get(".estate-dialog").attributes("open")).toBeDefined();
    expect(wrapper.get(".estate-dialog").text()).toContain("Editar proyecto");
  });

  it("treats a risky project with no live capital as completed", async () => {
    apiMock.mockResolvedValue([...projects, returnedRiskProject]);
    const wrapper = mount(RealEstateView);
    await flushPromises();

    expect(wrapper.get(".project-grid--active").text()).not.toContain(
      "Riesgo devuelto",
    );
    const completed = wrapper.get("details.completed-projects");
    expect(completed.text()).toContain("Riesgo devuelto");
    expect(completed.get(".status").text()).toBe("Completado");
    expect(completed.get(".progress-track").attributes("aria-valuenow")).toBe(
      "100",
    );
    expect(completed.get(".progress-track i").attributes("style")).toContain(
      "width: 100%",
    );
  });

  it("translates the completed-projects area into English", async () => {
    applyLocale("en");
    apiMock.mockResolvedValue([completedProject]);
    const wrapper = mount(RealEstateView);
    await flushPromises();

    expect(wrapper.get(".active-projects-empty").text()).toContain(
      "No active projects",
    );
    expect(wrapper.get("details.completed-projects summary").text()).toContain(
      "Completed projects",
    );
    expect(
      wrapper.get(".completed-projects .project-progress").text(),
    ).toContain("Completed");
  });

  it("keeps the global empty state when there are no investments", async () => {
    apiMock.mockResolvedValue([]);
    const wrapper = mount(RealEstateView);
    await flushPromises();

    expect(wrapper.get(".empty-estate").text()).toContain(
      "Aún no hay proyectos",
    );
    expect(wrapper.find("details.completed-projects").exists()).toBe(false);
  });
});
