/** The message of whatever a `catch` caught: an Error (or anything with a `message`), else the value itself. */
export function errorMessage(e: unknown): string {
  if (e && typeof e === 'object' && 'message' in e) return String(e.message);
  return String(e);
}
