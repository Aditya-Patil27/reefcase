import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { components } from "../api/schema";
import type { DiveSite } from "../components/SitePicker";
import type { UploadOutcome } from "../api/upload";

type Survey = components["schemas"]["Survey"];

const mocks = vi.hoisted(() => ({
  uploadSurvey: vi.fn(),
  navigate: vi.fn(),
}));

vi.mock("@tanstack/react-router", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@tanstack/react-router")>()),
  useNavigate: () => mocks.navigate,
}));

vi.mock("../api/upload", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/upload")>()),
  uploadSurvey: mocks.uploadSurvey,
}));

/** The map needs WebGL, so the route test swaps in a stub that shows the pin readout and moves it. */
vi.mock("../components/SitePicker", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../components/SitePicker")>();
  return {
    ...actual,
    SitePicker: (props: { value: DiveSite; onChange: (next: DiveSite) => void }) => (
      <div role="group" aria-label="Dive site map">
        <p data-testid="pin-readout">{actual.formatCoordinates(props.value)}</p>
        <button type="button" onClick={() => props.onChange({ lat: -23.442, lon: 151.914 })}>
          Move pin to Heron Island
        </button>
        <button type="button" onClick={() => props.onChange({ lat: 12, lon: 200 })}>
          Move pin past the antimeridian
        </button>
      </div>
    ),
  };
});

import { Route } from "./upload";

const survey: Survey = {
  id: "srv_01JA7Z3K9YQ2C8W4T6H0M5N8P3",
  site_id: "site_lizard_island",
  dive_date: "2026-10-21",
  status: "queued",
  source: "upload",
  video_path: null,
  cover: null,
  failure_reason: null,
  created_at: "2026-10-21T09:14:00Z",
};

const clip = new File(["clip"], "lizard-island.mp4", { type: "video/mp4" });

function renderUpload() {
  const Page = Route.options.component;
  if (!Page) throw new Error("The upload route has no component.");
  return render(<Page />);
}

/** Arc's dropzone keeps its file input visually hidden, so the test drives that input directly. */
function chooseClip(): void {
  const input = document.querySelector('input[type="file"]');
  if (!(input instanceof HTMLInputElement)) throw new Error("The dropzone rendered no file input.");
  fireEvent.change(input, { target: { files: [clip] } });
}

function submit(): void {
  fireEvent.click(screen.getByRole("button", { name: "Start investigation" }));
}

describe("the upload route", () => {
  beforeEach(() => {
    mocks.uploadSurvey.mockReset();
    mocks.navigate.mockReset();
    mocks.navigate.mockResolvedValue(undefined);
    // jsdom 30 has no object URLs (web/src/api/upload.ts notes the same for the preview).
    URL.createObjectURL = vi.fn(() => "blob:clip");
    URL.revokeObjectURL = vi.fn();
  });

  it("shows the clip error when the form is submitted without a clip", async () => {
    renderUpload();

    submit();

    expect(await screen.findByText("Choose the dive clip to investigate.")).toBeInTheDocument();
    expect(mocks.uploadSurvey).not.toHaveBeenCalled();
    expect(screen.getByRole("group", { name: "Dive clip" })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(screen.getByRole("group", { name: "Dive clip" })).toHaveFocus();
  });

  it("shows the chosen clip with its size, then uploads and opens the survey", async () => {
    let settle: (outcome: UploadOutcome) => void = () => {};
    mocks.uploadSurvey.mockImplementation(
      (_input: unknown, options: { onProgress?: (next: { loaded: number; total: number }) => void }) => {
        options.onProgress?.({ loaded: 18_300_000, total: 43_600_000 });
        return new Promise<UploadOutcome>((resolve) => {
          settle = resolve;
        });
      },
    );
    renderUpload();

    chooseClip();
    expect(screen.getAllByText("lizard-island.mp4").length).toBeGreaterThan(0);
    expect(screen.getByText(/^4 B · —$/)).toBeInTheDocument();

    submit();

    const bar = await screen.findByRole("progressbar", { name: "Upload progress" });
    expect(bar).toHaveAttribute("aria-valuenow", "42");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
    expect(screen.getByText("Uploading 42% · 18.3 / 43.6 MB")).toBeInTheDocument();

    expect(mocks.uploadSurvey).toHaveBeenCalledWith(
      expect.objectContaining({
        video: clip,
        lat: -14.668,
        lon: 145.461,
        diveDate: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
      }),
      expect.objectContaining({ onProgress: expect.any(Function) }),
    );

    settle({ ok: true, survey });

    await waitFor(() =>
      expect(mocks.navigate).toHaveBeenCalledWith({
        to: "/surveys/$id",
        params: { id: survey.id },
      }),
    );
  });

  it("puts each 422 message beside its field and focuses the first invalid one", async () => {
    mocks.uploadSurvey.mockResolvedValue({
      ok: false,
      status: 422,
      fieldErrors: [
        { field: "lat", message: "Latitude is outside the survey grid." },
        { field: "site_name", message: "Site name is longer than 120 characters." },
      ],
      message: "Some details of the dive need fixing before the survey can start.",
    } satisfies UploadOutcome);
    renderUpload();

    chooseClip();
    submit();

    expect(await screen.findByText("Latitude is outside the survey grid.")).toBeInTheDocument();
    expect(screen.getByText("Site name is longer than 120 characters.")).toBeInTheDocument();

    const latitude = screen.getByRole("group", { name: "Latitude" });
    expect(latitude).toHaveAttribute("aria-invalid", "true");
    expect(latitude).toHaveAttribute("aria-describedby", "upload-lat-error");
    expect(screen.getByLabelText("Site name")).toHaveAttribute("aria-invalid", "true");

    expect(document.activeElement).toBe(screen.getByRole("spinbutton", { name: "Latitude" }));
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(mocks.navigate).not.toHaveBeenCalled();
  });

  it("clears a field error when that field changes", async () => {
    mocks.uploadSurvey.mockResolvedValue({
      ok: false,
      status: 422,
      fieldErrors: [
        { field: "lat", message: "Latitude is outside the survey grid." },
        { field: "site_name", message: "Site name is longer than 120 characters." },
      ],
      message: "Some details of the dive need fixing before the survey can start.",
    } satisfies UploadOutcome);
    renderUpload();

    chooseClip();
    submit();
    expect(await screen.findByText("Site name is longer than 120 characters.")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Site name"), { target: { value: "Heron Island" } });
    expect(screen.getByLabelText("Site name")).not.toHaveAttribute("aria-invalid");
    await waitFor(() =>
      expect(screen.queryByText("Site name is longer than 120 characters.")).toBeNull(),
    );
    expect(screen.getByText("Latitude is outside the survey grid.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Move pin to Heron Island" }));
    expect(screen.queryByText("Latitude is outside the survey grid.")).toBeNull();
  });

  it("keeps the pin and the coordinate fields in step, both ways", async () => {
    renderUpload();

    expect(screen.getByTestId("pin-readout")).toHaveTextContent("14.6680° S  145.4610° E", {
      normalizeWhitespace: false,
    });
    expect(screen.getByText("14.6680° S")).toBeInTheDocument();
    expect(screen.getByText("145.4610° E")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Move pin to Heron Island" }));
    expect(screen.getByTestId("pin-readout")).toHaveTextContent("23.4420° S  151.9140° E", {
      normalizeWhitespace: false,
    });

    fireEvent.click(screen.getByRole("button", { name: "Move pin past the antimeridian" }));
    expect(screen.getByText("180.0000° E")).toBeInTheDocument();

    const latitude = screen.getByRole("spinbutton", { name: "Latitude" });
    latitude.focus();
    fireEvent.keyDown(latitude, { key: "End" });
    expect(screen.getByTestId("pin-readout")).toHaveTextContent("90.0000° N  180.0000° E", {
      normalizeWhitespace: false,
    });
  });

  it("shows a form-level message above the submit button when the API is unreachable", async () => {
    mocks.uploadSurvey.mockResolvedValue({
      ok: false,
      status: null,
      fieldErrors: [],
      message: "Couldn't reach the ReefCase API. Check the connection and try again.",
    } satisfies UploadOutcome);
    renderUpload();

    chooseClip();
    submit();

    expect(
      await screen.findByText(
        "Couldn't reach the ReefCase API. Check the connection and try again.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start investigation" })).toBeInTheDocument();
    expect(mocks.navigate).not.toHaveBeenCalled();
  });
});
