/**
 * Toggle an index while preserving click order and never mutating the input.
 * Selected entries always remain removable, even after the limit is reached.
 */
export function toggleLimitedIndex(selected, index, limit) {
  const current = [...new Set(selected)];
  if (!Number.isInteger(index) || index < 0 || !Number.isInteger(limit) || limit < 0) {
    return current;
  }
  if (current.includes(index)) {
    return current.filter((item) => item !== index);
  }
  if (current.length >= limit) {
    return current;
  }
  return [...current, index];
}
