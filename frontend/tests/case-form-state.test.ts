/**
 * Regression tests for the dataset test-case dialog state.
 *
 * Bug: opening "Edit" on a case and then cancelling left that case selected,
 * so the next "Add Case" submitted an update that overwrote it.
 *
 * Run with: npm test   (Node's built-in runner; no extra dependencies)
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import type { TestCaseDetail } from "../lib/api.ts";
import {
  caseFormReducer,
  getCaseSubmitTarget,
  initialCaseFormState,
  type CaseFormAction,
  type CaseFormState,
} from "../app/evaluations/datasets/case-form-state.ts";

function makeCase(id: string): TestCaseDetail {
  return {
    id,
    dataset_id: "dataset-1",
    org_id: "org-1",
    case_identifier: `case_${id}`,
    query: `Question ${id}?`,
    query_type: "factoid",
    expected_behavior: "answer",
    ground_truth_answer: null,
    key_facts: [],
    ground_truth_evidence: [],
    conversation_history: [],
    metadata_json: {},
    created_at: "2026-10-13T00:00:00",
    updated_at: "2026-10-13T00:00:00",
  };
}

const run = (...actions: CaseFormAction[]): CaseFormState =>
  actions.reduce(caseFormReducer, initialCaseFormState);

test("cancelling an edit and then adding a case creates a new case", () => {
  const existing = makeCase("a1");
  const state = run(
    { type: "openEdit", testCase: existing },
    { type: "close" }, // Cancel / Escape / backdrop
    { type: "openAdd" }
  );

  assert.equal(state.mode, "add");
  assert.equal(state.editingCase, null);
  assert.deepEqual(getCaseSubmitTarget(state), { kind: "create" });
});

test("opening Add directly from an edit never targets the edited case", () => {
  const state = run({ type: "openEdit", testCase: makeCase("a1") }, { type: "openAdd" });
  assert.deepEqual(getCaseSubmitTarget(state), { kind: "create" });
});

test("closing the dialog discards the edited case", () => {
  const state = run({ type: "openEdit", testCase: makeCase("a1") }, { type: "close" });
  assert.deepEqual(state, initialCaseFormState);
  assert.equal(getCaseSubmitTarget(state), null);
});

test("editing targets exactly the case that was opened", () => {
  assert.deepEqual(getCaseSubmitTarget(run({ type: "openEdit", testCase: makeCase("a1") })), {
    kind: "update",
    caseId: "a1",
  });
  assert.deepEqual(
    getCaseSubmitTarget(
      run(
        { type: "openEdit", testCase: makeCase("a1") },
        { type: "close" },
        { type: "openEdit", testCase: makeCase("b2") }
      )
    ),
    { kind: "update", caseId: "b2" }
  );
});

test("a closed dialog has no submit target", () => {
  assert.equal(getCaseSubmitTarget(initialCaseFormState), null);
  assert.equal(getCaseSubmitTarget(run({ type: "openAdd" }, { type: "close" })), null);
});
