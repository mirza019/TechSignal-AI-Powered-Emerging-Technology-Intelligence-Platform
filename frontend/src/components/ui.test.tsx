// @vitest-environment jsdom
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { EvidenceList, SearchBox, Modal } from "./ui";

afterEach(cleanup);
describe("evidence and analyst interactions", () => {
  it("marks synthetic sources and preserves primary-source references", () => {
    render(
      <EvidenceList
        records={[
          {
            id: "evidence-123",
            title: "Synthetic converter study",
            source_type: "paper",
            url: "https://example.com/study",
            published_at: "2025-01-01",
            content: "A sample abstract",
            provider: "Demo",
            is_demo: true,
            metadata_json: {},
            technology_id: "tech-1",
          },
        ]}
      />,
    );
    expect(screen.getByText("Sample")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Synthetic converter study/ }),
    ).toHaveAttribute("href", "https://example.com/study");
    expect(screen.getByText(/Evidence evidence-123/)).toBeInTheDocument();
  });
  it("propagates user search input", () => {
    const change = vi.fn();
    render(<SearchBox value="" onChange={change} />);
    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "HVDC" },
    });
    expect(change).toHaveBeenCalledWith("HVDC");
  });
  it("keeps clicks inside a review modal from closing it", () => {
    const close = vi.fn();
    render(
      <Modal title="Review assessment" onClose={close}>
        <button>Approve</button>
      </Modal>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(close).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Close dialog" }));
    expect(close).toHaveBeenCalledOnce();
  });
});
