import { t } from "../lib/i18n";

/** columns: [{ h: "Header", f: (row) => cell }]; rows are plain objects; optional row click. */
export function DataTable({ columns, rows, onRow, empty = t("Nothing to show.") }) {
  if (!rows?.length) return <p className="muted">{empty}</p>;
  return (
    <table>
      <thead><tr>{columns.map((c) => <th key={c.h}>{c.h}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => (
        <tr key={r.id ?? i} className={onRow ? "click" : ""} onClick={onRow && (() => onRow(r))}>{columns.map((c) => <td key={c.h}>{c.f(r)}</td>)}</tr>))}
      </tbody>
    </table>
  );
}
