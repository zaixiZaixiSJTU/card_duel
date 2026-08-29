import assert from "node:assert/strict";
import test from "node:test";

import { toggleLimitedIndex } from "../app/selection.js";

test("selected cards can always be removed after the limit is reached", () => {
  const full = toggleLimitedIndex([1], 2, 2);
  assert.deepEqual(full, [1, 2]);
  assert.deepEqual(toggleLimitedIndex(full, 1, 2), [2]);
});

test("selection does not overfill or mutate its source", () => {
  const source = [0, 1];
  assert.deepEqual(toggleLimitedIndex(source, 2, 2), [0, 1]);
  assert.deepEqual(source, [0, 1]);
});

test("selection normalizes duplicates and rejects invalid indexes", () => {
  assert.deepEqual(toggleLimitedIndex([1, 1], 1, 3), []);
  assert.deepEqual(toggleLimitedIndex([1], -1, 3), [1]);
});
