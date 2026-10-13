import type { TestCaseDetail } from "@/lib/api";

/**
 * Lifecycle of the add / edit test-case dialog.
 *
 * The case being edited lives inside the "edit" state only, so closing the
 * dialog (cancel, Escape, backdrop or a successful save) always discards it.
 * This prevents a later "Add Case" from being submitted as an update to a
 * previously opened case.
 */
export type CaseFormState =
  | { mode: "closed"; editingCase: null }
  | { mode: "add"; editingCase: null }
  | { mode: "edit"; editingCase: TestCaseDetail };

export type CaseFormAction =
  | { type: "openAdd" }
  | { type: "openEdit"; testCase: TestCaseDetail }
  | { type: "close" };

export const initialCaseFormState: CaseFormState = { mode: "closed", editingCase: null };

export function caseFormReducer(_state: CaseFormState, action: CaseFormAction): CaseFormState {
  switch (action.type) {
    case "openAdd":
      return { mode: "add", editingCase: null };
    case "openEdit":
      return { mode: "edit", editingCase: action.testCase };
    case "close":
      return initialCaseFormState;
  }
}

export type CaseSubmitTarget =
  | { kind: "create" }
  | { kind: "update"; caseId: string };

/** Decides what a submit of the case form does; null when the form is closed. */
export function getCaseSubmitTarget(state: CaseFormState): CaseSubmitTarget | null {
  switch (state.mode) {
    case "add":
      return { kind: "create" };
    case "edit":
      return { kind: "update", caseId: state.editingCase.id };
    case "closed":
      return null;
  }
}
