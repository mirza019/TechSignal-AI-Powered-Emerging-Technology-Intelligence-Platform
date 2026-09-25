// @vitest-environment jsdom
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import "@testing-library/jest-dom/vitest";
import { Technologies } from "./Technologies";
vi.mock("../App", () => ({
  useSession: () => ({
    user: { role: "Viewer" },
    settings: { domains: [{ name: "HVDC" }, { name: "Energy Storage" }] },
  }),
}));
vi.mock("../hooks", () => ({
  useApi: () => ({
    loading: false,
    error: "",
    refresh: vi.fn(),
    data: [
      {
        id: "1",
        name: "HVDC test technology",
        domain: "HVDC",
        description: "A test record",
        horizon: "H1",
        approved: true,
        confidence: 0.8,
        evidence_count: 3,
        keywords: [],
        score: null,
      },
      {
        id: "2",
        name: "Storage test technology",
        domain: "Energy Storage",
        description: "Another test record",
        horizon: "H3",
        approved: false,
        confidence: 0.5,
        evidence_count: 4,
        keywords: [],
        score: null,
      },
    ],
  }),
}));
afterEach(cleanup);
describe("technology portfolio filters", () => {
  it("filters real cards by search and prevents viewer edit controls", () => {
    render(
      <MemoryRouter>
        <Technologies />
      </MemoryRouter>,
    );
    expect(
      screen.queryByRole("button", { name: "Add technology" }),
    ).not.toBeInTheDocument();
    fireEvent.change(
      screen.getByRole("textbox", { name: "Search technologies…" }),
      { target: { value: "Storage" } },
    );
    expect(screen.queryByText("HVDC test technology")).not.toBeInTheDocument();
    expect(screen.getByText("Storage test technology")).toBeInTheDocument();
  });
  it("honors the analyst review queue link and horizon filtering", () => {
    render(
      <MemoryRouter initialEntries={["/technologies?review=pending"]}>
        <Technologies />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("checkbox", { name: "Awaiting review" }),
    ).toBeChecked();
    expect(screen.queryByText("HVDC test technology")).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Horizon" }), {
      target: { value: "H1" },
    });
    expect(
      screen.getByText("No technologies match these filters."),
    ).toBeInTheDocument();
  });
});
