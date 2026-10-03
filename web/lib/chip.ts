/**
 * The only words a status may use, mirroring the backend's `Chip` type.
 *
 * A union, so "Overdue" or "Defaulter" cannot be written anywhere in the UI
 * without failing the type check. There is also no red in the palette: a
 * status here describes where someone is in their own rhythm, never a verdict.
 */

export const CHIPS = ["on_rhythm", "changed", "not_confirmed", "new"] as const;

export type Chip = (typeof CHIPS)[number];

export const CHIP_LABEL: Record<Chip, string> = {
  on_rhythm: "On rhythm",
  changed: "Changed",
  not_confirmed: "Not confirmed",
  new: "New",
};
