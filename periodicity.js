// periodicity.js — Calabria bus schedule validity logic
// Two orthogonal axes:
//   1. DAY axis    : cadenza (day-of-week mask) + holiday-as-Sunday rule
//   2. PERIOD axis : the Periodo code's date window
// A corsa is valid on date d  <=>  dayMatch(d) AND periodMatch(d).
// The day's timetable = UNION of all valid corse. No priority needed.

// ---------------------------------------------------------------------------
// 1. HOLIDAY CALENDAR (one central list of DATES, not per-rule)
// ---------------------------------------------------------------------------

// Gregorian Easter (Meeus/Butcher). Returns a Date (Easter Sunday).
function easterSunday(year) {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31); // 3=Mar, 4=Apr
  const day = ((h + l - 7 * m + 114) % 31) + 1;
  return new Date(year, month - 1, day);
}

const md = (dt) => `${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;

// Fixed national holidays. Add Cosenza's patron day here if you want it treated as festivo.
const FIXED_HOLIDAYS_MD = [
  "01-01", // Capodanno
  "01-06", // Epifania
  "04-25", // Liberazione
  "05-01", // Festa del Lavoro
  "06-02", // Repubblica
  "08-15", // Ferragosto
  "11-01", // Ognissanti
  "12-08", // Immacolata
  "12-25", // Natale
  "12-26", // Santo Stefano
  // "02-12", // (example) Madonna del Pilerio — Cosenza patron, enable if desired
];

// Returns a Set of "MM-DD" holiday keys for a given year (fixed + Easter-derived).
function holidaysForYear(year) {
  const s = new Set(FIXED_HOLIDAYS_MD);
  const easter = easterSunday(year);
  const pasquetta = new Date(easter);
  pasquetta.setDate(easter.getDate() + 1); // Easter Monday
  s.add(md(easter));      // Easter Sunday is already a Sunday, but harmless to include
  s.add(md(pasquetta));   // Pasquetta — the one that actually matters (falls on a Monday)
  return s;
}

function isHoliday(date) {
  return holidaysForYear(date.getFullYear()).has(md(date));
}

// ---------------------------------------------------------------------------
// 2. DAY AXIS — cadenza + holiday rule
// ---------------------------------------------------------------------------

// Cadenza string is 7 slots: Lun Mar mer Gio Ven Sab Dom.
// A slot is ACTIVE unless it is "_". e.g. "LMmGVS_" => Mon..Sat on, Sun off.
// Returns boolean[7] indexed Mon(0)..Sun(6).
function parseCadenza(cadenza) {
  const c = (cadenza || "").padEnd(7, "_").slice(0, 7);
  return Array.from(c, (ch) => ch !== "_");
}

// Effective weekday index Mon(0)..Sun(6). Holidays collapse to Sunday(6).
function effectiveDayIndex(date) {
  if (isHoliday(date)) return 6;          // festivo == domenica
  const js = date.getDay();               // 0=Sun..6=Sat
  return js === 0 ? 6 : js - 1;           // -> Mon(0)..Sun(6)
}

function dayMatch(corsa, date) {
  return parseCadenza(corsa.cadenza)[effectiveDayIndex(date)];
}

// ---------------------------------------------------------------------------
// 3. PERIOD AXIS — the Periodo code's date window
// ---------------------------------------------------------------------------

const ord = (date) => (date.getMonth() + 1) * 100 + date.getDate(); // MMDD as int

// Inclusive month/day range; supports year-wrap (start > end, e.g. Dec23->Jan06).
function inMD(date, startMMDD, endMMDD) {
  const o = ord(date);
  return startMMDD <= endMMDD
    ? o >= startMMDD && o <= endMMDD
    : o >= startMMDD || o <= endMMDD;
}

const isAugust = (d) => d.getMonth() === 7;

// Scol / Non Scol need a school calendar the admin defines. Shape:
//   { schoolTerm: [[startMMDD,endMMDD], ...],   // e.g. [[915,1231],[101,610]]
//     schoolBreaks: [[1223,106],[/*easter window*/], ...] }  // vacations (incl. summer)
// inSchoolTerm defaults to "in a term range and not in a break".
function inSchoolTerm(date, cal) {
  if (!cal) return false;
  const inBreak = (cal.schoolBreaks || []).some(([s, e]) => inMD(date, s, e));
  if (inBreak) return false;
  return (cal.schoolTerm || []).some(([s, e]) => inMD(date, s, e));
}
function inSchoolVacation(date, cal) {
  if (!cal) return false;
  return (cal.schoolBreaks || []).some(([s, e]) => inMD(date, s, e));
}

// One explicit predicate per code — DO NOT derive "*" as a shared modifier.
const PERIOD_WINDOWS = {
  Fer:        (d)      => true,
  "Fer*":     (d)      => !isAugust(d),
  Est:        (d)      => inMD(d, 801, 909),
  "Est*":     (d)      => inMD(d, 801, 831),
  Fest:       (d)      => true,               // day-type (Sunday cadenza) carries this
  "Fest*":    (d)      => !isAugust(d),
  "Non Scol": (d, cal) => inSchoolVacation(d, cal),
  "Non Scol*":(d, cal) => inSchoolVacation(d, cal) && !isAugust(d),
  Scol:       (d, cal) => inSchoolTerm(d, cal),
  Univ:       (d)      => inMD(d, 101, 731) || inMD(d, 910, 1231),
  "Univ*":    (d)      => inMD(d, 101, 630) || inMD(d, 910, 1231),
};

function periodMatch(corsa, date, calendar) {
  const fn = PERIOD_WINDOWS[corsa.periodo];
  return fn ? fn(date, calendar) : true; // unknown code => don't silently hide it
}

// ---------------------------------------------------------------------------
// 4. VALIDITY + SEARCH
// ---------------------------------------------------------------------------

function isCorsaValid(corsa, date, calendar) {
  return dayMatch(corsa, date) && periodMatch(corsa, date, calendar);
}

// Filter a list of corse to those valid on `date`, optionally departing at/after
// `afterHHMM` (e.g. "13:00"), sorted by first departure time. `corsa.departure`
// is the origin-stop time "HH:MM"; skip cells that are "-" or "00:00".
function findTrips(corse, date, calendar, afterHHMM) {
  return corse
    .filter((c) => isCorsaValid(c, date, calendar))
    .filter((c) => c.departure && c.departure !== "00:00" && c.departure !== "-")
    .filter((c) => !afterHHMM || c.departure >= afterHHMM)
    .sort((a, b) => a.departure.localeCompare(b.departure));
}

// ---------------------------------------------------------------------------
// Worked check:
//   May 1 2026 (Fri, Festa del Lavoro):
//     Univ + "LMmGVS_"  -> effectiveDayIndex = Sunday(6) -> cadenza[6]=false -> DROPPED ✓
//     Fest + "______D"  -> cadenza[6]=true, window Fest=true -> SHOWN ✓  (no zero-results)
//   Tue in October: Univ + "LMmGVS_" -> Tue on, Univ Sep10-Dec31 -> valid; Scol also valid -> union.
// ---------------------------------------------------------------------------

export {
  easterSunday, holidaysForYear, isHoliday,
  parseCadenza, effectiveDayIndex, dayMatch,
  inMD, inSchoolTerm, inSchoolVacation, PERIOD_WINDOWS, periodMatch,
  isCorsaValid, findTrips,
};
