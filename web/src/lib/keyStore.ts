// The playground's API key lives in sessionStorage only (gone when the tab closes), never localStorage.
const KEY = "ab_playground_key";

export function getPlaygroundKey(): string {
  try {
    return sessionStorage.getItem(KEY) ?? "";
  } catch {
    return "";
  }
}

export function setPlaygroundKey(value: string): void {
  try {
    if (value) sessionStorage.setItem(KEY, value);
    else sessionStorage.removeItem(KEY);
  } catch {
    // storage blocked (private mode): the key just isn't remembered
  }
}
